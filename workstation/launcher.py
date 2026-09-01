"""启动官方 Cursor worker 的公共逻辑（CLI 与 GUI 共用）。

不实现文件/串口协议：只组装 `agent worker start`，并写入现成 MCP 配置。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Callable, TextIO

from workstation.agent_cli import ensure_uv, find_agent, install_agent
from workstation.config import save_config
from workstation.mcp_config import install_mcp_configs
from workstation.sandbox import normalize_root

LogFn = Callable[[str], None]


def default_worker_name() -> str:
    raw = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or ""
    if not raw and hasattr(os, "uname"):
        try:
            raw = os.uname().nodename  # type: ignore[attr-defined]
        except Exception:
            raw = ""
    fallback = "windows-workstation" if os.name == "nt" else "linux-workstation"
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(raw))
    return cleaned or fallback


def worker_command(agent: Path, worker_name: str, workspace: Path, api_key: str = "") -> list[str]:
    cmd = [
        str(agent),
        "worker",
        "start",
        "--name",
        worker_name,
        "--worker-dir",
        str(workspace),
    ]
    if api_key.strip():
        cmd.extend(["--api-key", api_key.strip()])
    return cmd


def display_command(cmd: list[str], api_key: str) -> str:
    shown = list(cmd)
    if api_key.strip() and shown:
        shown[-1] = "***"
    return " ".join(shown)


def prepare_session(
    workspace: str | os.PathLike[str],
    worker_name: str = "",
    api_key: str = "",
    python_exe: str = "",
    log: LogFn | None = None,
) -> dict:
    """保存配置、写入 MCP、确保 agent/uv，返回可 Popen 的命令。"""

    def _log(msg: str) -> None:
        if log:
            log(msg)

    name = (worker_name or default_worker_name()).strip() or default_worker_name()
    py = python_exe or sys.executable
    root = normalize_root(workspace)
    save_config(
        {
            "workspace": str(root),
            "worker_name": name,
            "api_key": api_key.strip(),
            "python": py,
        }
    )
    if os.name != "nt":
        uv = ensure_uv()
        _log(f"uv: {uv or '未安装（串口/拍照 MCP 需要 uvx）'}")
    written = install_mcp_configs(py, str(root))
    for path in written:
        _log(f"已写入 MCP: {path}")
    agent = find_agent() or install_agent()
    os.environ["PATH"] = str(agent.parent) + os.pathsep + os.environ.get("PATH", "")
    _log(f"agent: {agent}")
    cmd = worker_command(agent, name, root, api_key)
    return {
        "agent": agent,
        "workspace": root,
        "worker_name": name,
        "api_key": api_key.strip(),
        "command": cmd,
        "display": display_command(cmd, api_key),
    }


class WorkerProcess:
    """后台跑官方 worker，把输出送到回调。"""

    def __init__(self) -> None:
        self.proc: subprocess.Popen[str] | None = None

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, command: list[str], log: LogFn) -> None:
        if self.running:
            raise RuntimeError("worker 已在运行")
        kwargs: dict = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(command, **kwargs)
        log(f"已启动 pid={self.proc.pid}")

    def pump_output(self, log: LogFn) -> None:
        proc = self.proc
        if proc is None or proc.stdout is None:
            return
        stdout: TextIO = proc.stdout
        for line in stdout:
            log(line.rstrip("\n"))

    def stop(self, log: LogFn | None = None) -> None:
        proc = self.proc
        if proc is None or proc.poll() is not None:
            self.proc = None
            return
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            else:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        if log:
            log("已停止 worker")
        self.proc = None

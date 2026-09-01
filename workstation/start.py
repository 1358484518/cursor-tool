"""启动 Cursor worker，把当前 Windows 工位连到云端 Agent。"""

from __future__ import annotations

import os
import subprocess
import sys

from workstation.agent_cli import find_agent, install_agent
from workstation.config import load_config
from workstation.mcp_config import install_mcp_configs
from workstation.sandbox import normalize_root


def _print(msg: str = "") -> None:
    print(msg, flush=True)


def run_start() -> int:
    cfg = load_config()
    workspace_raw = str(cfg.get("workspace") or "")
    if not workspace_raw:
        _print("还没有配置工作文件夹。请先双击 一键配置.bat")
        return 1
    try:
        workspace = normalize_root(workspace_raw)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        _print(str(exc))
        _print("请重新运行 一键配置.bat")
        return 1

    python_exe = str(cfg.get("python") or sys.executable)
    worker_name = str(cfg.get("worker_name") or "windows-workstation")
    api_key = str(cfg.get("api_key") or "").strip()
    install_mcp_configs(python_exe, str(workspace))

    agent = find_agent() or install_agent()
    os.environ["PATH"] = str(agent.parent) + os.pathsep + os.environ.get("PATH", "")

    cmd = [
        str(agent),
        "worker",
        "start",
        "--name",
        worker_name,
        "--worker-dir",
        str(workspace),
    ]
    if api_key:
        cmd.extend(["--api-key", api_key])

    _print("========================================")
    _print("  正在连接 Cursor worker")
    _print("========================================")
    _print(f"工位名:   {worker_name}")
    _print(f"工作区:   {workspace}")
    _print("请保持本窗口不要关闭。")
    _print("然后打开 https://cursor.com/agents ，在环境列表里选择这台机器。")
    _print()
    display = list(cmd)
    if api_key:
        display[-1] = "***"
    _print("命令: " + " ".join(display))
    _print()

    try:
        completed = subprocess.run(cmd)
        return int(completed.returncode)
    except KeyboardInterrupt:
        _print("\n已停止 worker")
        return 0


def main() -> None:
    try:
        code = run_start()
    except KeyboardInterrupt:
        _print("\n已停止")
        code = 0
    except Exception as exc:  # noqa: BLE001
        _print(f"启动失败: {exc}")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()

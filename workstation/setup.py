"""一键配置：安装依赖、选定工作文件夹、登录并连接 Cursor worker。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workstation.agent_cli import ensure_uv, install_agent
from workstation.config import KIT_DIR, save_config
from workstation.mcp_config import (
    OFF_THE_SHELF_NAMES,
    SERVER_NAME,
    install_mcp_configs,
    off_the_shelf_servers,
)
from workstation.sandbox import normalize_root


def _print(msg: str = "") -> None:
    print(msg, flush=True)


def _prompt(message: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{message}{suffix}: ").strip()
    except EOFError:
        value = ""
    return value or default


def _ensure_python_packages() -> None:
    if os.name != "nt":
        _print("Linux/macOS：硬件用现成 MCP（uvx mcp-serial / framegrab-mcp-server），不装本仓库自研依赖。")
        uv = ensure_uv()
        if uv is None:
            _print("未找到 uv/uvx。可手动安装: curl -LsSf https://astral.sh/uv/install.sh | sh")
            _print("没有 uv 时仍可启动 worker（改代码/编译），但串口和拍照 MCP 不会就绪。")
        else:
            _print(f"已找到 uv: {uv}")
        return
    req = KIT_DIR / "requirements.txt"
    _print("正在安装 Python 依赖（官方 mcp SDK、pyserial、opencv-python）…")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        _print("pip 安装失败，尝试 python -m ensurepip …")
        subprocess.run([sys.executable, "-m", "ensurepip", "--upgrade"], check=False)
        result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("无法安装 Python 依赖，请手动运行: python -m pip install -r requirements.txt")


def _ask_workspace() -> Path:
    _print()
    _print("请指定 Cursor worker 的工作文件夹（官方参数 --worker-dir）。")
    _print("云端 Agent 的文件编辑和终端命令会在这个目录进行；本机编译器、烧录器走系统 PATH。")
    _print("串口和摄像头在 Linux 上用现成 MCP（mcp-serial / framegrab）；Windows 用本仓库 MCP。")
    raw = _prompt("工作文件夹完整路径", str(Path.home() / "CursorWork"))
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        create = _prompt(f"文件夹不存在，是否创建？ {path} （Y/n）", "Y")
        if create.lower() in {"y", "yes", "是", ""}:
            path.mkdir(parents=True, exist_ok=True)
        else:
            raise RuntimeError("未创建工作文件夹，配置中止")
    return normalize_root(path)


def _ask_worker_name() -> str:
    default = os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME") or ""
    if not default and hasattr(os, "uname"):
        try:
            default = os.uname().nodename  # type: ignore[attr-defined]
        except Exception:
            default = ""
    fallback = "windows-workstation" if os.name == "nt" else "linux-workstation"
    default = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(default)) or fallback
    name = _prompt("给这台工位起个名字（cursor.com/agents 里会显示）", default)
    return name.strip() or default


def _ask_api_key() -> str:
    _print()
    _print("登录方式：直接回车将打开浏览器执行 agent login（推荐）。")
    _print("如果这是无人值守工位，可粘贴 Cursor 个人 API Key。")
    return _prompt("个人 API Key（可留空）", "")


def run_setup() -> int:
    os.chdir(KIT_DIR)
    os_label = "Windows" if os.name == "nt" else "Linux/macOS"
    _print("========================================")
    _print(f"  Cursor {os_label} 工位一键配置")
    _print("========================================")
    _print(f"套件目录: {KIT_DIR}")
    _print(f"Python:   {sys.executable} ({sys.version.split()[0]})")

    _ensure_python_packages()
    workspace = _ask_workspace()
    worker_name = _ask_worker_name()
    api_key = _ask_api_key()

    save_config(
        {
            "workspace": str(workspace),
            "worker_name": worker_name,
            "api_key": api_key,
            "python": sys.executable,
        }
    )
    written = install_mcp_configs(sys.executable, str(workspace))
    _print()
    _print("已写入 MCP 配置:")
    for path in written:
        _print(f"  - {path}")

    _print()
    _print("正在安装 / 检查 Cursor CLI（agent）…")
    try:
        agent = install_agent()
    except RuntimeError as exc:
        _print(str(exc))
        return 1
    _print(f"已找到 agent: {agent}")

    if not api_key:
        _print()
        _print("即将打开浏览器登录 Cursor，请使用你的账号完成授权。")
        subprocess.run([str(agent), "login"])

    mcp_names = (SERVER_NAME,) if os.name == "nt" else OFF_THE_SHELF_NAMES
    for name in mcp_names:
        enable = subprocess.run(
            [str(agent), "mcp", "enable", name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if enable.returncode != 0:
            _print(f"提示: 如需手动启用 MCP，可运行: agent mcp enable {name}")
            if enable.stderr:
                _print(enable.stderr.strip()[:400])

    _print()
    _print("配置完成。")
    _print(f"  工作区: {workspace}")
    _print(f"  工位名: {worker_name}")
    _print("  文件 / 编译 / 烧录: Cursor 官方 worker（--worker-dir + 系统 PATH）")
    if os.name == "nt":
        _print("  硬件 MCP（本仓库 FastMCP，对齐 mcp-serial / videocapture-mcp）:")
        _print("    list_ports / query / serial_write / reset_device / take_photo")
    else:
        names = ", ".join(off_the_shelf_servers())
        _print(f"  硬件 MCP（现成 uvx，写入 ~/.cursor/mcp.json）: {names}")
        _print("    serial     mcp-serial：list_ports / query / reset_device")
        _print("    framegrab  framegrab-mcp-server：摄像头拍一帧")
        _print("  串口权限: sudo usermod -aG dialout \"$USER\"  然后重新登录")
        _print("  摄像头权限不足时可: sudo usermod -aG video \"$USER\"")
    _print()
    machine = "Windows" if os.name == "nt" else "这台 Linux"
    start_now = _prompt(f"现在启动连接，让云端 Agent 连到{machine}工位？ (Y/n)", "Y")
    if start_now.lower() in {"y", "yes", "是", ""}:
        from workstation.start import run_start

        return run_start()
    later = "connect.bat / launch.py" if os.name == "nt" else "bash connect.sh 或 python3 launch.py"
    _print(f"以后请运行 {later}")
    return 0


def main() -> None:
    try:
        code = run_setup()
    except KeyboardInterrupt:
        _print("\n已取消")
        code = 1
    except Exception as exc:  # noqa: BLE001
        _print(f"配置失败: {exc}")
        code = 1
    if os.name == "nt" and not sys.stdin.isatty():
        input("按回车键退出…")
    raise SystemExit(code)


if __name__ == "__main__":
    main()

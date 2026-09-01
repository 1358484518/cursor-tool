"""一键配置：安装依赖、选定工作文件夹、登录并连接 Cursor worker。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from workstation.agent_cli import install_agent
from workstation.config import KIT_DIR, save_config
from workstation.mcp_config import SERVER_NAME, install_mcp_configs
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
    req = KIT_DIR / "requirements.txt"
    _print("正在安装 Python 依赖（pyserial、opencv-python）…")
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
    _print("请指定本机唯一允许读写的工作文件夹。")
    _print("云端 Agent 只能通过 MCP 读写这个文件夹；系统里的编译器、烧录器仍可调用。")
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
    default = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in str(default)) or "windows-workstation"
    name = _prompt("给这台工位起个名字（cursor.com/agents 里会显示）", default)
    return name.strip() or default


def _ask_api_key() -> str:
    _print()
    _print("登录方式：直接回车将打开浏览器执行 agent login（推荐）。")
    _print("如果这是无人值守工位，可粘贴 Cursor 个人 API Key。")
    return _prompt("个人 API Key（可留空）", "")


def run_setup() -> int:
    os.chdir(KIT_DIR)
    _print("========================================")
    _print("  Cursor Windows 工位一键配置")
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

    enable = subprocess.run(
        [str(agent), "mcp", "enable", SERVER_NAME],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if enable.returncode != 0:
        _print("提示: 如需手动启用 MCP，可运行: agent mcp enable windows-workstation")
        if enable.stderr:
            _print(enable.stderr.strip()[:400])

    _print()
    _print("配置完成。")
    _print(f"  工作区: {workspace}")
    _print(f"  工位名: {worker_name}")
    _print("  MCP:    list_dir / read_file / write_file / run_command / serial_list / serial_send / take_photo")
    _print()
    start_now = _prompt("现在启动连接，让云端 Agent 连到这台 Windows 工位？ (Y/n)", "Y")
    if start_now.lower() in {"y", "yes", "是", ""}:
        from workstation.start import run_start

        return run_start()
    _print("以后请双击 启动连接.bat")
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

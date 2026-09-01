"""启动 Cursor worker，把当前工位连到云端 Agent。"""

from __future__ import annotations

import os
import subprocess
import sys

from workstation.launcher import prepare_session


def _print(msg: str = "") -> None:
    print(msg, flush=True)


def run_start() -> int:
    from workstation.config import load_config
    from workstation.sandbox import normalize_root

    cfg = load_config()
    workspace_raw = str(cfg.get("workspace") or "")
    if not workspace_raw:
        hint = "launch.py / setup.bat" if os.name == "nt" else "python3 launch.py"
        _print(f"还没有配置工作文件夹。请先运行 {hint}")
        return 1
    try:
        normalize_root(workspace_raw)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        _print(str(exc))
        return 1

    info = prepare_session(
        workspace_raw,
        str(cfg.get("worker_name") or ""),
        str(cfg.get("api_key") or ""),
        str(cfg.get("python") or sys.executable),
        str(cfg.get("https_proxy") or ""),
        log=_print,
    )
    _print("========================================")
    _print("  正在连接 Cursor worker")
    _print("========================================")
    _print(f"工位名:   {info['worker_name']}")
    _print(f"工作区:   {info['workspace']}")
    _print("请保持本窗口不要关闭。然后打开 https://cursor.com/agents")
    _print("命令: " + str(info["display"]))
    _print()
    try:
        completed = subprocess.run(info["command"], env=info["env"])
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

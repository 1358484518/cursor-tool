"""定位并调用 Cursor `agent` CLI。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


WINDOWS_INSTALL = "irm 'https://cursor.com/install?win32=true' | iex"


def candidate_agent_paths() -> list[Path]:
    home = Path.home()
    names = ["agent.exe", "agent"]
    dirs = [
        home / ".local" / "bin",
        home / ".cursor" / "bin",
        home / "AppData" / "Local" / "cursor-agent",
        home / "AppData" / "Local" / "Programs" / "cursor-agent",
        home / "AppData" / "Local" / "cursor",
        Path("C:/Program Files/Cursor"),
        Path("C:/Program Files/cursor-agent"),
    ]
    found: list[Path] = []
    which = shutil.which("agent")
    if which:
        found.append(Path(which))
    for directory in dirs:
        for name in names:
            path = directory / name
            if path.is_file():
                found.append(path)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = os.path.normcase(str(path.resolve())) if path.exists() else os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def find_agent() -> Path | None:
    paths = candidate_agent_paths()
    return paths[0] if paths else None


def _prepend_local_bin() -> None:
    local_bin = str(Path.home() / ".local" / "bin")
    os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")


def ensure_uv() -> Path | None:
    """定位或安装 Astral uv（Linux 上用 uvx 拉现成 MCP）。"""
    _prepend_local_bin()
    for name in ("uvx", "uv"):
        found = shutil.which(name)
        if found:
            return Path(found)
    if os.name == "nt":
        return None
    subprocess.run("curl -LsSf https://astral.sh/uv/install.sh | sh", shell=True, check=False)
    _prepend_local_bin()
    found = shutil.which("uvx") or shutil.which("uv")
    return Path(found) if found else None


def install_agent() -> Path:
    existing = find_agent()
    if existing:
        return existing
    if os.name != "nt":
        script = "curl https://cursor.com/install -fsS | bash"
        subprocess.run(script, shell=True, check=False)
    else:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                WINDOWS_INSTALL,
            ],
            check=False,
        )
    _prepend_local_bin()
    found = find_agent()
    if not found:
        hint = "agent" if os.name != "nt" else "agent.exe"
        raise RuntimeError(
            "Cursor CLI（agent）安装后仍找不到。请新开一个终端，确认能运行 agent --version，"
            f"或把 {hint} 所在目录加入 PATH。"
        )
    return found


def agent_cmd(agent: Path, *args: str, check: bool = False, **kwargs) -> subprocess.CompletedProcess[str]:
    command = [str(agent), *args]
    return subprocess.run(
        command,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        **kwargs,
    )

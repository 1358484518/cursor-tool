"""工作区内的列目录、读写文件、跑命令。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from workstation.sandbox import PathDeniedError, ensure_parent_in_root, resolve_in_root

MAX_READ_BYTES = 2 * 1024 * 1024
MAX_COMMAND_OUTPUT = 200_000
DEFAULT_COMMAND_TIMEOUT = 120
MAX_COMMAND_TIMEOUT = 3600


def list_dir(root: Path, path: str = ".", max_entries: int = 500) -> dict[str, Any]:
    target = resolve_in_root(path, root)
    if not target.exists():
        raise FileNotFoundError(f"路径不存在: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"不是文件夹: {target}")
    limit = max(1, min(int(max_entries), 5000))
    entries = []
    truncated = False
    try:
        children = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        raise OSError(f"无法列出目录: {target}: {exc}") from exc
    for child in children:
        if len(entries) >= limit:
            truncated = True
            break
        try:
            stat = child.stat()
            kind = "dir" if child.is_dir() else "file"
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(root)),
                    "type": kind,
                    "size": 0 if kind == "dir" else int(stat.st_size),
                }
            )
        except OSError:
            entries.append({"name": child.name, "path": str(child), "type": "unknown", "size": 0})
    rel = "." if target == root else str(target.relative_to(root))
    return {
        "root": str(root),
        "path": rel,
        "count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


def read_file(
    root: Path,
    path: str,
    encoding: str = "utf-8",
    max_bytes: int = MAX_READ_BYTES,
) -> dict[str, Any]:
    target = resolve_in_root(path, root)
    if not target.exists():
        raise FileNotFoundError(f"文件不存在: {target}")
    if not target.is_file():
        raise IsADirectoryError(f"不是文件: {target}")
    limit = max(1, min(int(max_bytes), MAX_READ_BYTES))
    data = target.read_bytes()[: limit + 1]
    truncated = len(data) > limit
    data = data[:limit]
    encoding = encoding or "utf-8"
    if encoding.lower() in ("binary", "hex"):
        return {
            "path": str(target.relative_to(root)),
            "encoding": "hex",
            "truncated": truncated,
            "size": target.stat().st_size,
            "content": data.hex(),
        }
    text = data.decode(encoding, errors="replace")
    return {
        "path": str(target.relative_to(root)),
        "encoding": encoding,
        "truncated": truncated,
        "size": target.stat().st_size,
        "content": text,
    }


def write_file(
    root: Path,
    path: str,
    content: str,
    encoding: str = "utf-8",
    append: bool = False,
) -> dict[str, Any]:
    target = resolve_in_root(path, root)
    ensure_parent_in_root(target, root)
    encoding = encoding or "utf-8"
    if encoding.lower() in ("binary", "hex"):
        payload = bytes.fromhex("".join((content or "").split()))
        mode = "ab" if append else "wb"
        with target.open(mode) as handle:
            handle.write(payload)
        n = len(payload)
    else:
        mode = "a" if append else "w"
        with target.open(mode, encoding=encoding, newline="\n") as handle:
            handle.write(content if content is not None else "")
        n = len((content or "").encode(encoding, errors="replace"))
    return {
        "path": str(Path(os.path.realpath(target)).relative_to(root)),
        "bytes": n,
        "append": bool(append),
    }


def run_command(
    root: Path,
    command: str,
    cwd: str = ".",
    timeout: int = DEFAULT_COMMAND_TIMEOUT,
) -> dict[str, Any]:
    if not command or not str(command).strip():
        raise ValueError("命令不能为空")
    workdir = resolve_in_root(cwd, root)
    if not workdir.exists() or not workdir.is_dir():
        raise NotADirectoryError(f"工作目录无效: {workdir}")
    seconds = int(timeout) if timeout else DEFAULT_COMMAND_TIMEOUT
    seconds = max(1, min(seconds, MAX_COMMAND_TIMEOUT))
    env = os.environ.copy()
    env["WORKSTATION_ROOT"] = str(root)
    # 允许调用系统编译器/烧录器：保留 PATH，不把可执行文件限制在工作区内。
    try:
        completed = subprocess.run(
            command,
            cwd=str(workdir),
            shell=True,
            capture_output=True,
            timeout=seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"命令超时（{seconds}s）: {command}") from exc
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"无法启动命令: {command}: {exc}") from exc

    def _clip(raw: bytes) -> tuple[str, bool]:
        text = (raw or b"").decode("utf-8", errors="replace")
        if os.name == "nt" and "\ufffd" in text[:200]:
            text = (raw or b"").decode("gbk", errors="replace")
        if len(text) > MAX_COMMAND_OUTPUT:
            return text[:MAX_COMMAND_OUTPUT] + "\n…(输出已截断)", True
        return text, False

    stdout, out_cut = _clip(completed.stdout)
    stderr, err_cut = _clip(completed.stderr)
    return {
        "command": command,
        "cwd": str(workdir.relative_to(root) if workdir != root else "."),
        "returncode": int(completed.returncode),
        "stdout": stdout,
        "stderr": stderr,
        "truncated": out_cut or err_cut,
        "note": "工作目录已锁定在指定文件夹内；系统 PATH 上的编译器、烧录器可以调用。",
    }

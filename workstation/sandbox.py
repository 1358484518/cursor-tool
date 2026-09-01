"""把文件读写限制在用户指定的一个工作文件夹内。"""

from __future__ import annotations

import os
from pathlib import Path


class PathDeniedError(PermissionError):
    """请求的路径落在工作区之外。"""


def normalize_root(root: str | os.PathLike[str]) -> Path:
    if not root:
        raise ValueError("未设置工作区路径（WORKSTATION_ROOT）")
    path = Path(root).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    resolved = Path(os.path.realpath(path))
    if not resolved.exists():
        raise FileNotFoundError(f"工作区不存在: {resolved}")
    if not resolved.is_dir():
        raise NotADirectoryError(f"工作区必须是文件夹: {resolved}")
    return resolved


def _casefold(path: Path) -> str:
    text = os.path.normcase(str(path))
    if os.name == "nt":
        text = text.replace("/", "\\")
    return text


def is_inside(path: Path, root: Path) -> bool:
    """判断 path 是否位于 root 之内（含 root 自身）。跟随真实路径，防止 .. 与符号链接逃逸。"""
    real_path = Path(os.path.realpath(path))
    real_root = Path(os.path.realpath(root))
    try:
        real_path.relative_to(real_root)
        return True
    except ValueError:
        path_key = _casefold(real_path)
        root_key = _casefold(real_root)
        if path_key == root_key:
            return True
        sep = "\\" if os.name == "nt" else os.sep
        return path_key.startswith(root_key.rstrip(sep) + sep)


def resolve_in_root(user_path: str | os.PathLike[str] | None, root: Path) -> Path:
    """把用户/模型传入的路径解析到工作区内。空路径表示工作区根目录。"""
    root = Path(os.path.realpath(root))
    raw = "" if user_path is None else str(user_path).strip()
    if not raw or raw in (".", "./", ".\\"):
        candidate = root
    else:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
    resolved = Path(os.path.realpath(candidate))
    if not is_inside(resolved, root):
        raise PathDeniedError(
            f"拒绝访问工作区以外的路径: {raw or '.'} -> {resolved}（工作区: {root}）"
        )
    return resolved


def ensure_parent_in_root(target: Path, root: Path) -> None:
    parent = target.parent
    if not is_inside(parent, root):
        raise PathDeniedError(f"拒绝在工作区外创建文件: {target}")
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)
        if not is_inside(Path(os.path.realpath(parent)), root):
            raise PathDeniedError(f"创建目录后路径逃出工作区: {parent}")

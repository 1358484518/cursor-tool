"""本地工位配置（不提交到 Git）。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


KIT_DIR = Path(__file__).resolve().parent.parent
CONFIG_NAME = "config.local.json"
USER_CONFIG_DIR = Path.home() / ".cursor-workstation"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def config_paths() -> list[Path]:
    return [KIT_DIR / CONFIG_NAME, USER_CONFIG_PATH]


def load_config() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in config_paths():
        merged.update(_read_json(path))
    env_root = os.environ.get("WORKSTATION_ROOT", "").strip()
    if env_root:
        merged["workspace"] = env_root
    env_python = os.environ.get("WORKSTATION_PYTHON", "").strip()
    if env_python:
        merged["python"] = env_python
    return merged


def save_config(config: dict[str, Any]) -> Path:
    payload = {
        "workspace": str(config.get("workspace") or ""),
        "worker_name": str(config.get("worker_name") or "windows-workstation"),
        "api_key": str(config.get("api_key") or ""),
        "python": str(config.get("python") or sys.executable),
    }
    local_path = KIT_DIR / CONFIG_NAME
    local_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    USER_CONFIG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return local_path


def workspace_root(config: dict[str, Any] | None = None) -> str:
    cfg = config if config is not None else load_config()
    return str(cfg.get("workspace") or os.environ.get("WORKSTATION_ROOT") or "")

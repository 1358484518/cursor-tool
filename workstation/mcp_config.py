"""把工位 MCP 写入 Cursor 的 mcp.json（用户级，必要时再写到工作区）。

Windows：继续用本仓库的 FastMCP（一键配置不依赖 uv）。
Linux/macOS：不启动自研 MCP，只写入现成服务器配置（mcp-serial、framegrab-mcp-server）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from workstation.config import KIT_DIR

SERVER_NAME = "windows-workstation"
OFF_THE_SHELF_PATH = KIT_DIR / "mcp.off-the-shelf.json"
OFF_THE_SHELF_NAMES = ("serial", "framegrab")


def mcp_server_config(python_exe: str, workspace: str) -> dict[str, Any]:
    return {
        "type": "stdio",
        "command": python_exe,
        "args": ["-m", "workstation.mcp_server"],
        "env": {
            "PYTHONPATH": str(KIT_DIR),
            "WORKSTATION_ROOT": workspace,
        },
    }


def off_the_shelf_servers() -> dict[str, Any]:
    """官方/开源 MCP 的现成启动方式，内容来自 mcp.off-the-shelf.json。"""
    data = json.loads(OFF_THE_SHELF_PATH.read_text(encoding="utf-8"))
    servers = data.get("mcpServers") or {}
    if not isinstance(servers, dict) or not servers:
        raise ValueError(f"无效的现成 MCP 配置: {OFF_THE_SHELF_PATH}")
    return servers


def _load_mcp_file(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {"mcpServers": {}}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {"mcpServers": {}}
    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
        data["mcpServers"] = servers
    return data


def upsert_mcp(path: Path, python_exe: str, workspace: str) -> None:
    data = _load_mcp_file(path)
    servers = data["mcpServers"]
    if os.name == "nt":
        servers[SERVER_NAME] = mcp_server_config(python_exe, workspace)
    else:
        servers.pop(SERVER_NAME, None)
        servers.update(off_the_shelf_servers())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def install_mcp_configs(python_exe: str, workspace: str) -> list[Path]:
    written: list[Path] = []
    user_mcp = Path.home() / ".cursor" / "mcp.json"
    upsert_mcp(user_mcp, python_exe, workspace)
    written.append(user_mcp)
    project_mcp = Path(workspace) / ".cursor" / "mcp.json"
    upsert_mcp(project_mcp, python_exe, workspace)
    written.append(project_mcp)
    return written

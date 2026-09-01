"""把工位 MCP 写入 Cursor 的 mcp.json（用户级，必要时再写到工作区）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from workstation.config import KIT_DIR

SERVER_NAME = "windows-workstation"


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


def upsert_mcp(path: Path, python_exe: str, workspace: str) -> None:
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
    servers[SERVER_NAME] = mcp_server_config(python_exe, workspace)
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

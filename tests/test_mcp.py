"""MCP 协议与工具用途：走官方 FastMCP，只暴露 worker 没有的硬件能力。"""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.mcp_config import mcp_server_config, off_the_shelf_servers, upsert_mcp
from workstation.mcp_server import SERVER_INSTRUCTIONS, mcp


def _tools_by_name() -> dict[str, object]:
    tools = asyncio.run(mcp.list_tools())
    return {item.name: item for item in tools}


class McpProtocolTests(unittest.TestCase):
    def test_initialize_instructions_point_at_worker(self) -> None:
        self.assertIn("worker", SERVER_INSTRUCTIONS)
        self.assertIn("mcp-serial", SERVER_INSTRUCTIONS)
        self.assertIn("videocapture-mcp", SERVER_INSTRUCTIONS)
        self.assertEqual(mcp.name, "windows-workstation")
        self.assertEqual(mcp.instructions, SERVER_INSTRUCTIONS)

    def test_tools_are_hardware_only(self) -> None:
        names = set(_tools_by_name())
        self.assertEqual(
            names,
            {"list_ports", "query", "serial_write", "reset_device", "take_photo"},
        )
        # 不再重复 worker 已有的文件/命令工具
        self.assertNotIn("list_dir", names)
        self.assertNotIn("read_file", names)
        self.assertNotIn("write_file", names)
        self.assertNotIn("run_command", names)

    def test_tool_descriptions_state_purpose(self) -> None:
        by_name = _tools_by_name()
        expected = {
            "list_ports": "COM",
            "query": "日志",
            "serial_write": "十六进制",
            "reset_device": "boot",
            "take_photo": "LED",
        }
        for name, hint in expected.items():
            desc = by_name[name].description or ""
            self.assertIn("用于", desc, msg=f"{name} 缺少用途说明")
            self.assertIn(hint, desc, msg=f"{name} 用途说明未覆盖「{hint}」")

    def test_query_loopback_via_mcp(self) -> None:
        result = asyncio.run(
            mcp.call_tool("query", {"port": "loop://", "data": "PING", "line_ending": ""})
        )
        text = str(result)
        self.assertIn("PING", text)

    def test_query_expect_via_mcp(self) -> None:
        result = asyncio.run(
            mcp.call_tool(
                "query",
                {
                    "port": "loop://",
                    "data": "OK\n",
                    "line_ending": "",
                    "expect": "OK",
                },
            )
        )
        text = str(result)
        self.assertIn("matched_expect", text)

    def test_unknown_tool(self) -> None:
        with self.assertRaises(Exception):
            asyncio.run(mcp.call_tool("rm_rf", {}))

    def test_mcp_config_points_at_module(self) -> None:
        cfg = mcp_server_config("/usr/bin/python3", "/tmp/ws")
        self.assertEqual(cfg["args"], ["-m", "workstation.mcp_server"])
        self.assertEqual(cfg["env"]["WORKSTATION_ROOT"], "/tmp/ws")

    def test_off_the_shelf_servers_match_vendored_json(self) -> None:
        servers = off_the_shelf_servers()
        self.assertEqual(set(servers), {"serial", "framegrab"})
        self.assertEqual(servers["serial"]["command"], "uvx")
        self.assertIn("mcp-serial", servers["serial"]["args"])
        self.assertEqual(servers["framegrab"]["args"], ["framegrab-mcp-server"])

    def test_linux_mcp_json_uses_off_the_shelf(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "mcp.json"
        upsert_mcp(path, "/usr/bin/python3", str(Path(tmp.name)))
        data = (path.read_text(encoding="utf-8"))
        self.assertIn("mcp-serial", data)
        self.assertIn("framegrab-mcp-server", data)
        self.assertNotIn("workstation.mcp_server", data)

    def test_take_photo_saves_and_returns_image(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "ws"
        root.mkdir()
        jpeg = b"\xff\xd8\xff\xdbfakejpeg"
        os.environ["WORKSTATION_ROOT"] = str(root)
        self.addCleanup(lambda: os.environ.pop("WORKSTATION_ROOT", None))

        def fake_save(dest, camera_index=0):
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(jpeg)
            return dest

        with patch("workstation.camera.save_photo", side_effect=fake_save):
            result = asyncio.run(mcp.call_tool("take_photo", {"path": "shot.jpg"}))
        self.assertTrue((root / "shot.jpg").is_file())
        blob = str(result)
        self.assertIn("shot.jpg", blob)
        self.assertTrue(any(getattr(item, "type", None) == "image" for item in result))


if __name__ == "__main__":
    unittest.main()

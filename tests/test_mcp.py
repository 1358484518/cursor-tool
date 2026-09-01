"""文件工具与 MCP 协议测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from workstation import fs_tools
from workstation.mcp_config import mcp_server_config
from workstation.mcp_server import (
    SERVER_INSTRUCTIONS,
    TOOLS,
    _read_message,
    _write_message,
    handle_request,
)
from workstation.sandbox import PathDeniedError


class FsToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "ws"
        self.root.mkdir()
        (self.root / "hello.txt").write_text("你好\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_list_and_read_write(self) -> None:
        listed = fs_tools.list_dir(self.root, ".")
        names = {item["name"] for item in listed["entries"]}
        self.assertIn("hello.txt", names)
        data = fs_tools.read_file(self.root, "hello.txt")
        self.assertIn("你好", data["content"])
        fs_tools.write_file(self.root, "out/note.txt", "ok")
        self.assertEqual((self.root / "out" / "note.txt").read_text(encoding="utf-8"), "ok")

    def test_write_outside_denied(self) -> None:
        with self.assertRaises(PathDeniedError):
            fs_tools.write_file(self.root, "../pwn.txt", "x")

    def test_run_command_cwd_locked(self) -> None:
        import sys

        quoted = sys.executable.replace("'", "\\'")
        result = fs_tools.run_command(self.root, f"'{quoted}' -c \"print('hi')\"", cwd=".")
        self.assertEqual(result["returncode"], 0)
        self.assertIn("hi", result["stdout"])
        with self.assertRaises(PathDeniedError):
            fs_tools.run_command(self.root, f"'{quoted}' -c \"print(1)\"", cwd="..")


class McpProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "ws"
        self.root.mkdir()
        (self.root / "a.txt").write_text("alpha", encoding="utf-8")
        os.environ["WORKSTATION_ROOT"] = str(self.root)

    def tearDown(self) -> None:
        os.environ.pop("WORKSTATION_ROOT", None)
        self._tmp.cleanup()

    def test_initialize_and_list_tools(self) -> None:
        init = handle_request("initialize", {"protocolVersion": "2024-11-05"})
        self.assertEqual(init["serverInfo"]["name"], "windows-workstation")
        self.assertIn("用途", init["instructions"])
        self.assertIn("编译", init["instructions"])
        tools = handle_request("tools/list", {})
        names = {t["name"] for t in tools["tools"]}
        self.assertEqual(
            names,
            {
                "list_dir",
                "read_file",
                "write_file",
                "run_command",
                "serial_list",
                "serial_send",
                "take_photo",
            },
        )

    def test_tool_descriptions_state_purpose(self) -> None:
        """每个工具说明必须写出「用于…」，方便云端 Agent 判断何时调用。"""
        self.assertIn("嵌入式", SERVER_INSTRUCTIONS)
        self.assertIn("典型流程", SERVER_INSTRUCTIONS)
        listed = handle_request("tools/list", {})
        by_name = {item["name"]: item["description"] for item in listed["tools"]}
        self.assertEqual(set(by_name), {item["name"] for item in TOOLS})
        expected_use = {
            "list_dir": "工程结构",
            "read_file": "源码",
            "write_file": "改源码",
            "run_command": "编译",
            "serial_list": "COM",
            "serial_send": "日志",
            "take_photo": "LED",
        }
        for name, hint in expected_use.items():
            desc = by_name[name]
            self.assertIn("用于", desc, msg=f"{name} 缺少用途说明")
            self.assertIn(hint, desc, msg=f"{name} 用途说明未覆盖「{hint}」")

    def test_read_and_denied_via_mcp(self) -> None:
        ok = handle_request("tools/call", {"name": "read_file", "arguments": {"path": "a.txt"}})
        self.assertFalse(ok["isError"])
        self.assertIn("alpha", ok["content"][0]["text"])
        denied = handle_request(
            "tools/call",
            {"name": "read_file", "arguments": {"path": "../a.txt"}},
        )
        self.assertTrue(denied["isError"])
        self.assertIn("拒绝", denied["content"][0]["text"])

    def test_write_via_mcp(self) -> None:
        result = handle_request(
            "tools/call",
            {"name": "write_file", "arguments": {"path": "b.txt", "content": "beta"}},
        )
        self.assertFalse(result["isError"])
        self.assertEqual((self.root / "b.txt").read_text(encoding="utf-8"), "beta")

    def test_unknown_tool(self) -> None:
        result = handle_request("tools/call", {"name": "rm_rf", "arguments": {}})
        self.assertTrue(result["isError"])

    def test_mcp_config_points_at_module(self) -> None:
        cfg = mcp_server_config("/usr/bin/python3", str(self.root))
        self.assertEqual(cfg["args"], ["-m", "workstation.mcp_server"])
        self.assertEqual(cfg["env"]["WORKSTATION_ROOT"], str(self.root))

    def test_list_dir_and_run_command_via_mcp(self) -> None:
        listed = handle_request("tools/call", {"name": "list_dir", "arguments": {"path": "."}})
        self.assertFalse(listed["isError"])
        self.assertIn("a.txt", listed["content"][0]["text"])
        import sys
        from shlex import quote

        cmd = f"{quote(sys.executable)} -c {quote('print(123)')}"
        ran = handle_request("tools/call", {"name": "run_command", "arguments": {"command": cmd}})
        self.assertFalse(ran["isError"])
        self.assertIn("123", ran["content"][0]["text"])

    def test_stdio_framing(self) -> None:
        import io

        payload = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        buf = io.BytesIO()
        _write_message(buf, payload)
        buf.seek(0)
        decoded = _read_message(buf)
        self.assertEqual(decoded, payload)


if __name__ == "__main__":
    unittest.main()

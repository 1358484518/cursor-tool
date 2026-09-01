"""串口工具测试：用 pyserial 的 loop://，不需要真硬件（同 mcp-serial）。"""

from __future__ import annotations

import os
import unittest

from workstation import serial_io


class SerialLoopbackTests(unittest.TestCase):
    def test_query_echoes_on_loop(self) -> None:
        result = serial_io.query("loop://", data="PING", line_ending="", timeout_s=0.5)
        self.assertEqual(result["wrote_bytes"], 4)
        self.assertIn("PING", result["text"])

    def test_query_hex_roundtrip(self) -> None:
        result = serial_io.query(
            "loop://",
            data="01 A0 FF",
            encoding="hex",
            timeout_s=0.5,
        )
        self.assertEqual(result["hex"], "01a0ff")

    def test_query_expect_match(self) -> None:
        result = serial_io.query(
            "loop://",
            data="hello OK",
            line_ending="",
            expect="OK",
            timeout_s=0.5,
        )
        self.assertTrue(result["matched_expect"])

    def test_reset_device_on_loop(self) -> None:
        result = serial_io.reset_device("loop://", timeout_s=0.3)
        self.assertEqual(result["port"], "loop://")
        self.assertIn("DTR", result["note"])

    def test_allowlist_denies_other_ports(self) -> None:
        old = os.environ.get("MCP_SERIAL_ALLOWED_PORTS")
        os.environ["MCP_SERIAL_ALLOWED_PORTS"] = "COM3"
        try:
            with self.assertRaises(PermissionError):
                serial_io.query("loop://", data="x", line_ending="")
        finally:
            if old is None:
                os.environ.pop("MCP_SERIAL_ALLOWED_PORTS", None)
            else:
                os.environ["MCP_SERIAL_ALLOWED_PORTS"] = old

    def test_list_ports_runs(self) -> None:
        ports = serial_io.list_ports()
        self.assertIsInstance(ports, list)


if __name__ == "__main__":
    unittest.main()

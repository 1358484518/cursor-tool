"""启动器逻辑测试（不依赖图形界面）。"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from workstation.launcher import (
    WorkerProcess,
    default_worker_name,
    display_command,
    prepare_session,
    worker_command,
)


class LauncherTests(unittest.TestCase):
    def test_default_worker_name_is_safe(self) -> None:
        name = default_worker_name()
        self.assertTrue(name)
        self.assertRegex(name, r"^[A-Za-z0-9_-]+$")

    def test_worker_command_matches_official_cli(self) -> None:
        cmd = worker_command(Path("/usr/bin/agent"), "desk", Path("/work"), "")
        self.assertEqual(
            cmd,
            ["/usr/bin/agent", "worker", "start", "--name", "desk", "--worker-dir", "/work"],
        )

    def test_api_key_hidden_in_display(self) -> None:
        cmd = worker_command(Path("agent"), "n", Path("/w"), "secret-key")
        self.assertIn("secret-key", cmd)
        self.assertNotIn("secret-key", display_command(cmd, "secret-key"))
        self.assertIn("***", display_command(cmd, "secret-key"))

    def test_prepare_session_writes_config(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name) / "ws"
        root.mkdir()
        fake_agent = Path(tmp.name) / "agent"
        fake_agent.write_text("", encoding="utf-8")
        logs: list[str] = []
        with (
            patch("workstation.launcher.find_agent", return_value=fake_agent),
            patch("workstation.launcher.install_mcp_configs", return_value=[Path("/tmp/mcp.json")]),
            patch("workstation.launcher.save_config") as saved,
            patch("workstation.launcher.ensure_uv", return_value=None),
        ):
            info = prepare_session(root, "my-box", "", log=logs.append)
        self.assertEqual(info["worker_name"], "my-box")
        self.assertEqual(info["workspace"], root.resolve())
        self.assertIn("worker", info["command"])
        self.assertIn("env", info)
        saved.assert_called_once()
        self.assertTrue(any("MCP" in line for line in logs))
        self.assertTrue(any("代理" in line for line in logs))

    def test_pump_output_explains_eproto_once(self) -> None:
        worker = WorkerProcess()
        worker._tls_hinted = False
        worker.proc = type("P", (), {})()
        worker.proc.stdout = io.StringIO(
            "Starting worker...\n"
            "Error: Failed to validate worker account settings: [internal] write EPROTO "
            "packet length too long\n"
            "more ssl routines noise\n"
        )
        logs: list[str] = []
        worker.pump_output(logs.append)
        hints = [line for line in logs if "HTTPS 代理" in line]
        self.assertEqual(len(hints), 1)


class GuiImportTests(unittest.TestCase):
    def test_gui_class_builds_or_skips_without_display(self) -> None:
        try:
            import tkinter as tk
        except ImportError:
            self.skipTest("tkinter 未安装")
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("没有显示器")
        root.withdraw()
        try:
            from workstation.gui import LauncherApp

            LauncherApp(root)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()

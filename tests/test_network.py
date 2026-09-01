"""TLS 探测与代理环境（不要求真连外网失败场景）。"""

from __future__ import annotations

import json
import os
import ssl
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from workstation.network import (
    configured_proxy,
    ensure_http1_for_agent,
    explain_tls_failure,
    looks_like_tls_failure,
    probe_url,
    probe_worker_hosts,
    worker_child_env,
)


class TlsHintTests(unittest.TestCase):
    def test_user_eproto_log_gets_hint(self) -> None:
        line = (
            "Error: Failed to validate worker account settings: [internal] write EPROTO "
            "C08C434F84780000:error:0A0000C6:SSL routines:tls_get_more_records:"
            "packet length too long:../deps/openssl/openssl/ssl/record/methods/tls_common.c:662:"
        )
        self.assertTrue(looks_like_tls_failure(line))
        hint = explain_tls_failure(line)
        self.assertIsNotNone(hint)
        self.assertIn("api2.cursor.sh", hint or "")
        self.assertIn("HTTPS 代理", hint or "")

    def test_unrelated_log_has_no_hint(self) -> None:
        self.assertIsNone(explain_tls_failure("Starting worker..."))


class ProxyEnvTests(unittest.TestCase):
    def test_explicit_proxy_sets_node_flag(self) -> None:
        with patch.dict(os.environ, {"HTTPS_PROXY": "", "https_proxy": "", "HTTP_PROXY": "", "http_proxy": ""}, clear=False):
            env = worker_child_env("http://127.0.0.1:7890")
        self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:7890")
        self.assertEqual(env["https_proxy"], "http://127.0.0.1:7890")
        self.assertEqual(env["NODE_USE_ENV_PROXY"], "1")

    def test_configured_proxy_prefers_explicit(self) -> None:
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://env:1"}, clear=False):
            self.assertEqual(configured_proxy("http://gui:7890"), "http://gui:7890")
            self.assertEqual(configured_proxy(""), "http://env:1")


class CliConfigTests(unittest.TestCase):
    def test_merges_http1_without_wiping_other_keys(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "cli-config.json"
        path.write_text(json.dumps({"version": 1, "editor": {"vimMode": True}}), encoding="utf-8")
        msg = ensure_http1_for_agent(path)
        self.assertIsNotNone(msg)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(data["network"]["useHttp1ForAgent"])
        self.assertTrue(data["editor"]["vimMode"])
        self.assertIsNone(ensure_http1_for_agent(path))


class ProbeTests(unittest.TestCase):
    def test_probe_url_reports_tls_error(self) -> None:
        class FakeOpener:
            def open(self, req, timeout=8.0):
                raise ssl.SSLError("packet length too long")

        with patch("workstation.network.urllib.request.build_opener", return_value=FakeOpener()):
            self.assertIn("TLS 失败", probe_url("https://api2.cursor.sh/"))

    def test_probe_url_treats_http_error_as_tls_ok(self) -> None:
        class FakeOpener:
            def open(self, req, timeout=8.0):
                raise HTTPError("https://x/", 404, "Not Found", hdrs={}, fp=None)

        with patch("workstation.network.urllib.request.build_opener", return_value=FakeOpener()):
            self.assertIn("OK TLS", probe_url("https://api2direct.cursor.sh/"))

    def test_probe_url_reports_url_error(self) -> None:
        class FakeOpener:
            def open(self, req, timeout=8.0):
                raise URLError("timed out")

        with patch("workstation.network.urllib.request.build_opener", return_value=FakeOpener()):
            self.assertIn("失败", probe_url("https://api2.cursor.sh/"))

    def test_probe_hosts_mentions_missing_proxy(self) -> None:
        with (
            patch.dict(os.environ, {"HTTPS_PROXY": "", "https_proxy": "", "HTTP_PROXY": "", "http_proxy": "", "ALL_PROXY": "", "all_proxy": ""}, clear=False),
            patch("workstation.network.probe_url", return_value="TLS 失败: boom"),
        ):
            lines = probe_worker_hosts("")
        self.assertTrue(any("直连" in line for line in lines))
        self.assertTrue(any("未设置代理" in line for line in lines))


if __name__ == "__main__":
    unittest.main()

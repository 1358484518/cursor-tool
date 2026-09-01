"""Worker 出站网络：代理环境、TLS 探测、SSL 失败说明。

官方 worker 要连 api2.cursor.sh；浏览器登录成功不代表 Node CLI 也能完成 TLS。
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

WORKER_TLS_HOSTS = (
    "https://api2.cursor.sh/",
    "https://api2direct.cursor.sh/",
)

CLI_CONFIG_PATH = Path.home() / ".cursor" / "cli-config.json"

SSL_HINT = """\
这是 TLS 握手失败，不是工位名或 MCP 写错。
官方 worker 在校验账号时要 HTTPS 访问 api2.cursor.sh；对端回了非 TLS 数据
（EPROTO / packet length too long），常见原因：
  · 网络拦截 / 需代理才能访问 *.cursor.sh（浏览器能开 cursor.com 也不够）
  · 桌面双击 launch.py 读不到 ~/.bashrc 里的 HTTP_PROXY
  · 代理地址写成了 https://，或本地 Clash/V2Ray 的 HTTP 端口没开
处理：
  1. 本窗口「HTTPS 代理」填 http://127.0.0.1:端口（Clash 常见 7890，v2rayN 常见 10809）
  2. 或在终端：export HTTPS_PROXY=http://127.0.0.1:7890 NODE_USE_ENV_PROXY=1
     然后 python3 launch.py
  3. 点「检查网络」，或终端执行: curl -vI https://api2.cursor.sh
     以及: agent worker debug
详见 README「排查」和官方文档：需要出站访问 api2.cursor.sh / api2direct.cursor.sh。
"""


def looks_like_tls_failure(text: str) -> bool:
    lower = text.lower()
    needles = (
        "eproto",
        "packet length too long",
        "tls_get_more_records",
        "ssl routines",
        "wrong version number",
        "certificate",
        "unable to verify",
        "self signed",
        "ssl_error",
    )
    return any(n in lower for n in needles)


def explain_tls_failure(text: str) -> str | None:
    if not looks_like_tls_failure(text):
        return None
    return SSL_HINT.strip()


def configured_proxy(explicit: str = "") -> str:
    return (
        (explicit or "").strip()
        or os.environ.get("HTTPS_PROXY", "").strip()
        or os.environ.get("https_proxy", "").strip()
        or os.environ.get("HTTP_PROXY", "").strip()
        or os.environ.get("http_proxy", "").strip()
        or os.environ.get("ALL_PROXY", "").strip()
        or os.environ.get("all_proxy", "").strip()
    )


def proxy_summary(explicit: str = "") -> str:
    keys = (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
        "NODE_USE_ENV_PROXY",
        "NO_PROXY",
    )
    parts = [f"{k}={os.environ.get(k) or '(空)'}" for k in keys]
    extra = (explicit or "").strip()
    if extra:
        parts.insert(0, f"窗口填写={extra}")
    return "代理环境: " + "  ".join(parts)


def worker_child_env(https_proxy: str = "") -> dict[str, str]:
    """给官方 agent 进程的环境：补齐代理变量，并让 Node 认 HTTP(S)_PROXY。"""
    env = os.environ.copy()
    proxy = configured_proxy(https_proxy)
    if proxy:
        env["HTTPS_PROXY"] = proxy
        env["https_proxy"] = proxy
        env.setdefault("HTTP_PROXY", proxy)
        env.setdefault("http_proxy", env["HTTP_PROXY"])
        env["NODE_USE_ENV_PROXY"] = "1"
    return env


def ensure_http1_for_agent(path: Path | None = None) -> str | None:
    """部分代理不能传 HTTP/2；与官方 CLI 文档一致，打开 useHttp1ForAgent。"""
    target = path or CLI_CONFIG_PATH
    data: dict[str, Any] = {}
    if target.is_file():
        try:
            loaded = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(loaded, dict):
            return None
        data = loaded
    network = data.get("network")
    if not isinstance(network, dict):
        network = {}
    if network.get("useHttp1ForAgent") is True:
        return None
    network["useHttp1ForAgent"] = True
    data["network"] = network
    data.setdefault("version", 1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"已写入 {target}：network.useHttp1ForAgent=true（代理对 HTTP/2 不友好时需要）"


def _opener(proxy: str) -> urllib.request.OpenerDirector:
    if proxy:
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    # 不用环境变量里的代理，单独测「直连」
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def probe_url(url: str, proxy: str = "", timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, method="GET")
    try:
        opener = _opener(proxy)
        with opener.open(req, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            return f"OK HTTP {code}"
    except urllib.error.HTTPError as exc:
        return f"OK TLS（HTTP {exc.code}）"
    except ssl.SSLError as exc:
        return f"TLS 失败: {exc}"
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, ssl.SSLError):
            return f"TLS 失败: {reason}"
        return f"失败: {reason if reason is not None else exc}"
    except OSError as exc:
        return f"失败: {exc}"


def probe_worker_hosts(https_proxy: str = "") -> list[str]:
    """探测 worker 需要的主机；同时测直连和（若有）代理。"""
    lines: list[str] = []
    proxy = configured_proxy(https_proxy)
    lines.append(proxy_summary(https_proxy))
    for url in WORKER_TLS_HOSTS:
        direct = probe_url(url, proxy="")
        lines.append(f"直连 {url} → {direct}")
        if proxy:
            via = probe_url(url, proxy=proxy)
            lines.append(f"经代理 {url} → {via}")
    if https_proxy.strip():
        hint = ensure_http1_for_agent()
        if hint:
            lines.append(hint)
    elif not proxy:
        lines.append(
            "未设置代理。若直连 TLS 失败，请在窗口填写 HTTP 代理，"
            "或从已 export HTTPS_PROXY 的终端再开 launch.py。"
        )
    return lines

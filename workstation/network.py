"""Worker 出站网络：代理环境、TLS 探测、SSL 失败说明。

官方 worker 要连 api2.cursor.sh；浏览器登录成功不代表 Node CLI 也能完成 TLS。
系统里只有 HTTP_PROXY、没有 HTTPS_PROXY 时，Node 容易把 TLS 直接打到 HTTP 代理上（EPROTO）。
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

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "NODE_USE_ENV_PROXY",
)

SSL_HINT = """\
这是 TLS 握手失败，不是工位名或 MCP 写错。
官方 worker 在校验账号时要 HTTPS 访问 api2.cursor.sh；对端回了非 TLS 数据
（EPROTO / packet length too long），常见原因：
  · 系统只设置了 HTTP_PROXY、没有 HTTPS_PROXY，Node 把 TLS 打到了 HTTP 代理上
  · 网络拦截 / 需代理才能访问 *.cursor.sh（浏览器能开 cursor.com 也不够）
  · 桌面双击 launch.py 读不到 ~/.bashrc 里的代理变量
处理：
  1. 若「检查网络」显示直连 api2.cursor.sh 已通：窗口代理留空，直接启动
     （本工具会忽略系统 HTTP_PROXY，让 worker 直连）
  2. 直连失败时，在「HTTPS 代理」填 http://host:port（不要写成 https://，末尾不要 /）
  3. 终端：curl -vI https://api2.cursor.sh  以及  agent worker debug
详见 README「排查」。
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


def normalize_proxy(url: str) -> str:
    return (url or "").strip().rstrip("/")


def tls_ok(result: str) -> bool:
    return result.startswith("OK")


def configured_proxy(explicit: str = "") -> str:
    return normalize_proxy(
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
    extra = normalize_proxy(explicit)
    if extra:
        parts.insert(0, f"窗口填写={extra}")
    return "代理环境: " + "  ".join(parts)


def _apply_proxy(env: dict[str, str], proxy: str) -> dict[str, str]:
    proxy = normalize_proxy(proxy)
    env["HTTPS_PROXY"] = proxy
    env["https_proxy"] = proxy
    env["HTTP_PROXY"] = proxy
    env["http_proxy"] = proxy
    env["NODE_USE_ENV_PROXY"] = "1"
    return env


def worker_child_env(https_proxy: str = "", prefer_direct: bool = False) -> dict[str, str]:
    """给官方 agent 进程的环境。

    窗口填了代理 → 始终走代理（并设置 NODE_USE_ENV_PROXY=1）。
    prefer_direct=True → 清掉继承来的 HTTP_PROXY，让 Node 直连。
    否则把仅有的 HTTP_PROXY 补成 HTTPS_PROXY，避免 Node 对 HTTP 代理做 TLS。
    """
    env = os.environ.copy()
    explicit = normalize_proxy(https_proxy)
    if explicit:
        return _apply_proxy(env, explicit)
    if prefer_direct:
        for key in PROXY_ENV_KEYS:
            env.pop(key, None)
        return env
    inherited = configured_proxy("")
    if inherited:
        return _apply_proxy(env, inherited)
    return env


def describe_child_env(env: dict[str, str]) -> str:
    keys = ("HTTPS_PROXY", "HTTP_PROXY", "NODE_USE_ENV_PROXY")
    parts = [f"{k}={env.get(k) or '(空)'}" for k in keys]
    return "worker 进程环境: " + "  ".join(parts)


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


def probe_session(https_proxy: str = "") -> dict[str, Any]:
    """探测出站 TLS，并决定 worker 进程该直连还是走代理。"""
    lines: list[str] = []
    explicit = normalize_proxy(https_proxy)
    inherited = configured_proxy("")
    proxy_to_test = explicit or inherited
    lines.append(proxy_summary(explicit))
    http_only = bool(
        (os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or "").strip()
        and not (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "").strip()
    )
    if http_only and not explicit:
        lines.append(
            "注意: 系统只设置了 HTTP_PROXY、没有 HTTPS_PROXY。"
            "官方 worker 是 Node，容易把 TLS 打到 HTTP 代理上（EPROTO）。"
        )
    direct_api2 = ""
    for url in WORKER_TLS_HOSTS:
        direct = probe_url(url, proxy="")
        lines.append(f"直连 {url} → {direct}")
        if url.startswith("https://api2.cursor.sh"):
            direct_api2 = direct
        if proxy_to_test:
            via = probe_url(url, proxy=proxy_to_test)
            lines.append(f"经代理 {url} → {via}")
    prefer_direct = not explicit and tls_ok(direct_api2)
    env = worker_child_env(explicit, prefer_direct=prefer_direct)
    if prefer_direct and inherited:
        lines.append(
            f"直连 api2.cursor.sh 已通。启动 worker 时将忽略系统代理 {inherited}，"
            "避免 Node 误用 HTTP_PROXY 导致 EPROTO。"
            "若必须走代理，请在窗口「HTTPS 代理」填写完整地址（末尾不要 /）。"
        )
    elif explicit:
        hint = ensure_http1_for_agent()
        if hint:
            lines.append(hint)
    elif not proxy_to_test:
        lines.append(
            "未设置代理。若直连 TLS 失败，请在窗口填写 HTTP 代理，"
            "或从已 export HTTPS_PROXY 的终端再开 launch.py。"
        )
    elif not tls_ok(direct_api2):
        lines.append(f"直连失败，将使用代理 {proxy_to_test}，并设置 NODE_USE_ENV_PROXY=1。")
        hint = ensure_http1_for_agent()
        if hint:
            lines.append(hint)
    lines.append(describe_child_env(env))
    return {"lines": lines, "env": env, "prefer_direct": prefer_direct}


def probe_worker_hosts(https_proxy: str = "") -> list[str]:
    return probe_session(https_proxy)["lines"]

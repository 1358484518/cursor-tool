"""串口工具，接口对齐 mcp-serial 的常用子集。

参考：https://github.com/HumbertoBernal/mcp-serial
（list_ports / query / write / reset_device；测试用 pyserial 的 loop://）

本模块只搬运字节，不烧录、不碰工作区文件。
可用环境变量 MCP_SERIAL_ALLOWED_PORTS（逗号分隔 glob，例如 COM*,loop://*）限制端口。
"""

from __future__ import annotations

import fnmatch
import os
import time
from typing import Any

MAX_TIMEOUT_S = float(os.environ.get("MCP_SERIAL_MAX_TIMEOUT", "120"))
MAX_READ_BYTES = 1_000_000


def _require_serial():
    try:
        import serial  # noqa: F401
        from serial.tools import list_ports  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "未安装 pyserial。请在本套件目录运行: python -m pip install -r requirements.txt"
        ) from exc


def _port_allowed(port: str) -> bool:
    raw = os.environ.get("MCP_SERIAL_ALLOWED_PORTS", "").strip()
    if not raw:
        return True
    return any(fnmatch.fnmatch(port, pat.strip()) for pat in raw.split(",") if pat.strip())


def _encode(data: str, encoding: str, line_ending: str) -> bytes:
    if not data:
        return b""
    encoding = (encoding or "utf-8").lower()
    if encoding in ("hex", "raw-hex"):
        return bytes.fromhex("".join(data.split()))
    payload = data.encode(encoding)
    ending = line_ending.encode(encoding) if line_ending else b""
    if ending and not payload.endswith(ending):
        payload += ending
    return payload


def _open_serial(port: str, baudrate: int, timeout: float, bytesize: int, parity: str, stopbits: float):
    _require_serial()
    import serial
    from serial import serial_for_url

    kwargs = {
        "baudrate": int(baudrate),
        "bytesize": int(bytesize),
        "parity": str(parity or "N")[:1].upper(),
        "stopbits": float(stopbits),
        "timeout": max(0.05, float(timeout)),
        "write_timeout": max(0.05, float(timeout)),
    }
    if "://" in port:
        return serial_for_url(port, **kwargs)
    return serial.Serial(port=port, **kwargs)


def list_ports() -> list[dict[str, Any]]:
    """列出本机串口及 USB VID/PID（mcp-serial 的 list_ports）。"""
    _require_serial()
    from serial.tools import list_ports

    ports = []
    for item in list_ports.comports():
        vid = f"{item.vid:04X}" if item.vid is not None else ""
        pid = f"{item.pid:04X}" if item.pid is not None else ""
        ports.append(
            {
                "device": item.device or "",
                "name": item.name or "",
                "description": item.description or "",
                "hwid": item.hwid or "",
                "vid": vid,
                "pid": pid,
                "manufacturer": item.manufacturer or "",
                "product": item.product or "",
                "serial_number": item.serial_number or "",
            }
        )
    return ports


def query(
    port: str,
    data: str = "",
    baudrate: int = 115200,
    encoding: str = "utf-8",
    line_ending: str = "\n",
    expect: str = "",
    timeout_s: float = 1.0,
    settle_ms: float = 80,
    bytes_to_read: int = 4096,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1,
) -> dict[str, Any]:
    """发送一帧并等待应答：有 expect 则等到该子串，否则等到线路安静（mcp-serial 的 query）。"""
    if not port:
        raise ValueError("必须指定串口，例如 COM3、/dev/ttyUSB0，或测试用 loop://")
    if not _port_allowed(port):
        raise PermissionError(f"端口不在 MCP_SERIAL_ALLOWED_PORTS 允许列表中: {port}")

    timeout_s = min(max(0.05, float(timeout_s)), MAX_TIMEOUT_S)
    to_read = min(max(0, int(bytes_to_read)), MAX_READ_BYTES)
    payload = _encode(data, encoding, line_ending if (encoding or "utf-8").lower() not in ("hex", "raw-hex") else "")
    expect_b = expect.encode("utf-8") if expect else b""

    with _open_serial(port, baudrate, timeout_s, bytesize, parity, stopbits) as ser:
        if payload:
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            ser.write(payload)
            ser.flush()
        received = _read_until(ser, to_read, timeout_s, settle_ms, expect_b)

    try:
        text = received.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return {
        "port": port,
        "baudrate": int(baudrate),
        "wrote_bytes": len(payload),
        "read_bytes": len(received),
        "text": text,
        "hex": received.hex(),
        "matched_expect": bool(expect_b) and expect_b in received,
    }


def serial_write(
    port: str,
    data: str,
    baudrate: int = 115200,
    encoding: str = "utf-8",
    line_ending: str = "\n",
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1,
) -> dict[str, Any]:
    """只发送、不等待（mcp-serial 的 write）。encoding=hex 时按十六进制发。"""
    result = query(
        port=port,
        data=data,
        baudrate=baudrate,
        encoding=encoding,
        line_ending=line_ending,
        timeout_s=0.05,
        settle_ms=0,
        bytes_to_read=0,
        bytesize=bytesize,
        parity=parity,
        stopbits=stopbits,
    )
    return {"port": result["port"], "wrote_bytes": result["wrote_bytes"]}


def reset_device(
    port: str,
    baudrate: int = 115200,
    pulse_s: float = 0.1,
    timeout_s: float = 2.0,
    bytes_to_read: int = 4096,
) -> dict[str, Any]:
    """脉冲 DTR 复位 Arduino/ESP32 风格板子，并读取启动输出（mcp-serial 的 reset_device）。"""
    if not port:
        raise ValueError("必须指定串口")
    if not _port_allowed(port):
        raise PermissionError(f"端口不在 MCP_SERIAL_ALLOWED_PORTS 允许列表中: {port}")
    timeout_s = min(max(0.05, float(timeout_s)), MAX_TIMEOUT_S)
    pulse_s = min(max(0.02, float(pulse_s)), 2.0)
    to_read = min(max(0, int(bytes_to_read)), MAX_READ_BYTES)

    with _open_serial(port, baudrate, timeout_s, 8, "N", 1) as ser:
        ser.dtr = False
        time.sleep(pulse_s)
        ser.dtr = True
        received = _read_until(ser, to_read, timeout_s, 80, b"")

    try:
        text = received.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return {
        "port": port,
        "baudrate": int(baudrate),
        "read_bytes": len(received),
        "text": text,
        "hex": received.hex(),
        "note": "已脉冲 DTR；若板子没有自动复位电路，这条命令不会重启芯片。",
    }


def _read_until(ser, to_read: int, timeout_s: float, settle_ms: float, expect_b: bytes) -> bytes:
    if to_read <= 0:
        return b""
    buf = bytearray()
    deadline = time.monotonic() + timeout_s
    settle = max(0.0, float(settle_ms) / 1000.0)
    last = time.monotonic()
    while time.monotonic() < deadline and len(buf) < to_read:
        remaining = deadline - time.monotonic()
        ser.timeout = min(0.05, max(0.01, remaining))
        waiting = 0
        try:
            waiting = int(ser.in_waiting or 0)
        except Exception:
            waiting = 0
        chunk = ser.read(max(1, min(waiting or 1, to_read - len(buf))))
        if chunk:
            buf.extend(chunk)
            last = time.monotonic()
            if expect_b and expect_b in buf:
                break
        elif buf and (time.monotonic() - last) >= settle:
            break
    return bytes(buf)


# 旧名：上一版 MCP 叫 serial_exchange
serial_exchange = query
list_serial_ports = list_ports

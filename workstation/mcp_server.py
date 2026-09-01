"""工位硬件 MCP：串口 + 拍照。协议走官方 Python MCP SDK（FastMCP）。

文件编辑和终端命令不要在这里重复实现——Cursor My Machines worker
（agent worker start --worker-dir）已经提供：
https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines

串口工具对齐 mcp-serial 的常用子集：
https://github.com/HumbertoBernal/mcp-serial

拍照对齐 videocapture-mcp 的 quick_capture（开摄像头 → 拍一帧 → 关闭）：
https://github.com/13rac1/videocapture-mcp
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from workstation.sandbox import normalize_root, resolve_in_root

SERVER_NAME = "windows-workstation"
SERVER_VERSION = "1.1.0"
WEBSITE_URL = "https://github.com/1358484518/cursor-tool"

SERVER_INSTRUCTIONS = (
    "这是 Windows 工位的硬件 MCP，不是文件系统。"
    "改代码、列目录、编译、烧录请用 Cursor worker 自带的文件编辑和终端"
    "（工作区就是启动时的 --worker-dir；Keil / gcc / J-Link 走系统 PATH）。"
    "本服务只补充 worker 没有的本机硬件："
    "list_ports / query / serial_write / reset_device 用于串口调试"
    "（对齐 mcp-serial：发现 COM 口、发 AT/日志、DTR 复位）；"
    "take_photo 用于拍板子核对 LED/屏幕/接线（对齐 videocapture-mcp 的 quick_capture）。"
    "照片会存进工作区，并把图像直接返回给 Agent。"
    "典型流程：worker 改代码并编译烧录 → list_ports → reset_device 或 query 看日志 → take_photo 核对现象。"
)


def _kit_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_sys_path() -> None:
    root = str(_kit_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def workspace_root() -> Path:
    raw = os.environ.get("WORKSTATION_ROOT", "").strip()
    if not raw:
        from workstation.config import load_config

        raw = str(load_config().get("workspace") or "")
    return normalize_root(raw)


mcp = FastMCP(
    SERVER_NAME,
    instructions=SERVER_INSTRUCTIONS,
    website_url=WEBSITE_URL,
)


@mcp.tool()
def list_ports() -> dict:
    """列出本机串口（COM3 等）及 USB VID/PID。

    用于：确认开发板插在哪个口、按芯片厂家识别适配器、给 query / reset_device 选 port。
    对齐 mcp-serial 的 list_ports。
    """
    from workstation.serial_io import list_ports as _list

    return {"ports": _list()}


@mcp.tool()
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
) -> dict:
    """向串口发送数据并读取应答。

    用于：MCU 调试日志、AT 命令、bootloader 交互、确认烧录后设备是否起来。
    对齐 mcp-serial 的 query：有 expect 则等到该子串出现，否则等到线路安静。
    data 默认 utf-8 并补换行；encoding=hex 时按十六进制发（如 \"01 A0 FF\"）。
    不传 data 则只读。测试可用 port=loop://。
    """
    from workstation.serial_io import query as _query

    return _query(
        port=port,
        data=data,
        baudrate=baudrate,
        encoding=encoding,
        line_ending=line_ending,
        expect=expect,
        timeout_s=timeout_s,
        settle_ms=settle_ms,
        bytes_to_read=bytes_to_read,
    )


@mcp.tool()
def serial_write(
    port: str,
    data: str,
    baudrate: int = 115200,
    encoding: str = "utf-8",
    line_ending: str = "\n",
) -> dict:
    """只向串口发送、不等待应答。

    用于：发复位命令、二进制帧、不需要立刻读回的场景。
    对齐 mcp-serial 的 write。encoding=hex 发十六进制。
    """
    from workstation.serial_io import serial_write as _write

    return _write(
        port=port,
        data=data,
        baudrate=baudrate,
        encoding=encoding,
        line_ending=line_ending,
    )


@mcp.tool()
def reset_device(
    port: str,
    baudrate: int = 115200,
    pulse_s: float = 0.1,
    timeout_s: float = 2.0,
) -> dict:
    """脉冲 DTR 复位 Arduino / ESP32 风格板子，并读取启动输出。

    用于：抓 boot log、看 Guru Meditation / HardFault、烧录后确认是否起来。
    对齐 mcp-serial 的 reset_device。没有自动复位电路的板子不会因此重启。
    """
    from workstation.serial_io import reset_device as _reset

    return _reset(port=port, baudrate=baudrate, pulse_s=pulse_s, timeout_s=timeout_s)


@mcp.tool()
def take_photo(path: str = "capture.jpg", camera_index: int = 0):
    """用本机摄像头拍一张照片（开摄像头 → 拍一帧 → 关闭）。

    用于：核对 LED / 屏幕 / 接线等硬件现象，把现场画面直接交给云端 Agent。
    对齐 videocapture-mcp 的 quick_capture；照片同时存进 worker 工作区（默认 capture.jpg）。
    """
    from workstation.camera import save_photo

    dest = resolve_in_root(path or "capture.jpg", workspace_root())
    if dest.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        dest = dest.with_suffix(".jpg")
    saved = save_photo(dest, camera_index=int(camera_index or 0))
    data = saved.read_bytes()
    root = workspace_root()
    rel = str(saved.relative_to(root))
    fmt = "jpeg" if saved.suffix.lower() in {".jpg", ".jpeg"} else saved.suffix.lstrip(".").lower() or "jpeg"
    return [
        f"已保存到工作区 {rel}（{len(data)} 字节）。",
        Image(data=data, format=fmt),
    ]


def main() -> None:
    _ensure_sys_path()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

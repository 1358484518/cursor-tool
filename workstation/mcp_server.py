"""MCP stdio 服务：列目录、读写工作区、跑命令、串口、拍照。

协议使用 LSP 风格的 Content-Length 帧，供 Cursor worker / 编辑器以 command 方式拉起。
文件类工具全部经过 sandbox，无法读写用户指定文件夹以外的路径。
跑命令时工作目录锁定在该文件夹，系统 PATH 上的编译器、烧录器可以调用。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from workstation.sandbox import PathDeniedError, normalize_root, resolve_in_root

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "windows-workstation"
SERVER_VERSION = "1.0.0"


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


ToolFn = Callable[[dict[str, Any], Path], Any]


def _text_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": text}],
        "isError": bool(is_error),
    }


def _tool_list_dir(args: dict[str, Any], root: Path) -> Any:
    from workstation.fs_tools import list_dir

    return list_dir(root, str(args.get("path") or "."), int(args.get("max_entries") or 500))


def _tool_read_file(args: dict[str, Any], root: Path) -> Any:
    from workstation.fs_tools import read_file

    path = str(args.get("path") or "")
    if not path:
        raise ValueError("path 不能为空")
    return read_file(
        root,
        path,
        encoding=str(args.get("encoding") or "utf-8"),
        max_bytes=int(args.get("max_bytes") or 0) or 2 * 1024 * 1024,
    )


def _tool_write_file(args: dict[str, Any], root: Path) -> Any:
    from workstation.fs_tools import write_file

    path = str(args.get("path") or "")
    if not path:
        raise ValueError("path 不能为空")
    return write_file(
        root,
        path,
        str(args.get("content") or ""),
        encoding=str(args.get("encoding") or "utf-8"),
        append=bool(args.get("append") or False),
    )


def _tool_run_command(args: dict[str, Any], root: Path) -> Any:
    from workstation.fs_tools import run_command

    return run_command(
        root,
        str(args.get("command") or ""),
        cwd=str(args.get("cwd") or "."),
        timeout=int(args.get("timeout") or 120),
    )


def _tool_serial_list(_args: dict[str, Any], _root: Path) -> Any:
    from workstation.serial_io import list_serial_ports

    return {"ports": list_serial_ports()}


def _tool_serial_send(args: dict[str, Any], _root: Path) -> Any:
    from workstation.serial_io import serial_exchange

    return serial_exchange(
        port=str(args.get("port") or ""),
        baudrate=int(args.get("baudrate") or 115200),
        write_data=str(args.get("data") or ""),
        encoding=str(args.get("encoding") or "utf-8"),
        read_timeout=float(args.get("read_timeout") or 1.0),
        bytes_to_read=int(args.get("bytes_to_read") or 1024),
    )


def _tool_take_photo(args: dict[str, Any], root: Path) -> Any:
    from workstation.camera import save_photo

    rel = str(args.get("path") or "capture.jpg")
    dest = resolve_in_root(rel, root)
    if dest.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
        dest = dest.with_suffix(".jpg")
    saved = save_photo(dest, camera_index=int(args.get("camera_index") or 0))
    return {
        "path": str(saved.relative_to(root)),
        "bytes": saved.stat().st_size,
        "camera_index": int(args.get("camera_index") or 0),
    }


TOOL_IMPL: dict[str, ToolFn] = {
    "list_dir": _tool_list_dir,
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "run_command": _tool_run_command,
    "serial_list": _tool_serial_list,
    "serial_send": _tool_serial_send,
    "take_photo": _tool_take_photo,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_dir",
        "description": "列出用户指定工作文件夹内的目录。path 相对工作区根目录，禁止访问其外的路径。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作区的目录，默认 ."},
                "max_entries": {"type": "integer", "description": "最多返回多少项，默认 500"},
            },
        },
    },
    {
        "name": "read_file",
        "description": "读取工作文件夹内的文件。encoding 用 utf-8；二进制可设为 hex。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string", "description": "utf-8 或 hex"},
                "max_bytes": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "写入工作文件夹内的文件。不能写到工作区以外。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "encoding": {"type": "string", "description": "utf-8 或 hex"},
                "append": {"type": "boolean"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": (
            "在工作文件夹内执行命令。cwd 必须位于工作区内。"
            "可以调用系统里已安装的编译器、烧录器（通过 PATH），"
            "但不要用命令去读写工作区以外的工程文件。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "例如 arm-none-eabi-gcc --version 或 STM32_Programmer_CLI -l"},
                "cwd": {"type": "string", "description": "相对工作区的工作目录，默认 ."},
                "timeout": {"type": "integer", "description": "超时秒数，默认 120，最大 3600"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "serial_list",
        "description": "列出本机串口（COM3、COM4 等），用于烧录或日志。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "serial_send",
        "description": "向串口发送数据并读取应答。data 默认按 utf-8；encoding=hex 时按十六进制发送。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "port": {"type": "string", "description": "例如 COM3"},
                "baudrate": {"type": "integer", "description": "默认 115200"},
                "data": {"type": "string"},
                "encoding": {"type": "string", "description": "utf-8 或 hex"},
                "read_timeout": {"type": "number", "description": "秒，默认 1"},
                "bytes_to_read": {"type": "integer", "description": "最多读多少字节，默认 1024"},
            },
            "required": ["port"],
        },
    },
    {
        "name": "take_photo",
        "description": "用本机摄像头拍一张照片，保存到工作文件夹内（默认 capture.jpg）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对工作区的保存路径，默认 capture.jpg"},
                "camera_index": {"type": "integer", "description": "摄像头编号，默认 0"},
            },
        },
    },
]


def handle_request(method: str, params: dict[str, Any] | None) -> Any:
    params = params or {}
    if method == "initialize":
        client_version = str(params.get("protocolVersion") or PROTOCOL_VERSION)
        return {
            "protocolVersion": client_version or PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "这是 Windows 工位 MCP。文件只能读写用户指定的一个工作文件夹；"
                "编译器、烧录器可通过 run_command 从系统 PATH 调用；"
                "串口与拍照走 serial_* / take_photo。"
            ),
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        impl = TOOL_IMPL.get(name)
        if impl is None:
            return _text_result(f"未知工具: {name}", is_error=True)
        try:
            root = workspace_root()
            result = impl(args, root)
            return _text_result(result)
        except PathDeniedError as exc:
            return _text_result(str(exc), is_error=True)
        except Exception as exc:  # noqa: BLE001 - 工具错误通过 MCP isError 返回
            return _text_result(f"{type(exc).__name__}: {exc}", is_error=True)
    raise KeyError(method)


def _read_message(stdin) -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = stdin.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        decoded = line.decode("utf-8", errors="replace").strip()
        if not decoded:
            break
        if ":" in decoded:
            key, value = decoded.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length") or 0)
    if length <= 0:
        return None
    body = stdin.read(length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _write_message(stdout, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii")
    stdout.write(header + raw)
    stdout.flush()


def serve_stdio() -> None:
    _ensure_sys_path()
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        try:
            message = _read_message(stdin)
        except Exception:
            traceback.print_exc(file=sys.stderr)
            return
        if message is None:
            return
        method = str(message.get("method") or "")
        msg_id = message.get("id")
        if not method:
            continue
        if msg_id is None:
            # notification，例如 notifications/initialized
            continue
        try:
            result = handle_request(method, message.get("params") or {})
            _write_message(stdout, {"jsonrpc": "2.0", "id": msg_id, "result": result})
        except KeyError:
            _write_message(
                stdout,
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                },
            )
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            _write_message(
                stdout,
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": str(exc)},
                },
            )


def main() -> None:
    _ensure_sys_path()
    serve_stdio()


if __name__ == "__main__":
    main()

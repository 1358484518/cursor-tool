"""串口工具：列出端口、收发数据。不访问工作区以外的文件。"""

from __future__ import annotations

from typing import Any


def _require_serial():
    try:
        import serial  # noqa: F401
        from serial.tools import list_ports  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "未安装 pyserial。请在本套件目录运行: python -m pip install -r requirements.txt"
        ) from exc


def list_serial_ports() -> list[dict[str, str]]:
    _require_serial()
    from serial.tools import list_ports

    ports = []
    for item in list_ports.comports():
        ports.append(
            {
                "device": item.device or "",
                "name": item.name or "",
                "description": item.description or "",
                "hwid": item.hwid or "",
            }
        )
    return ports


def serial_exchange(
    port: str,
    baudrate: int = 115200,
    write_data: str = "",
    encoding: str = "utf-8",
    read_timeout: float = 1.0,
    bytes_to_read: int = 1024,
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1,
) -> dict[str, Any]:
    _require_serial()
    import serial

    if not port:
        raise ValueError("必须指定串口，例如 COM3 或 /dev/ttyUSB0")
    encoding = (encoding or "utf-8").lower()
    payload = b""
    if write_data:
        if encoding in ("hex", "raw-hex"):
            hex_str = "".join(write_data.split())
            payload = bytes.fromhex(hex_str)
        else:
            payload = write_data.encode(encoding)

    timeout = max(0.05, float(read_timeout))
    to_read = max(0, int(bytes_to_read))
    with serial.Serial(
        port=port,
        baudrate=int(baudrate),
        bytesize=int(bytesize),
        parity=str(parity or "N")[:1].upper(),
        stopbits=float(stopbits),
        timeout=timeout,
        write_timeout=timeout,
    ) as ser:
        if payload:
            ser.write(payload)
            ser.flush()
        received = ser.read(to_read) if to_read else b""

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
    }

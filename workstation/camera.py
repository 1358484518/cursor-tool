"""摄像头拍照。对齐 videocapture-mcp 的 quick_capture：打开 → 拍一帧 → 关闭。

参考：https://github.com/13rac1/videocapture-mcp
照片必须保存到 worker 工作区内（官方 filesystem MCP 同样限制 allowed directories）。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _grab_with_opencv(camera_index: int) -> bytes:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("opencv-python 未安装") from exc

    cap = cv2.VideoCapture(int(camera_index))
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"打不开摄像头 index={camera_index}")
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("摄像头已打开但没有读到画面")
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("JPEG 编码失败")
    return buf.tobytes()


def _grab_with_ffmpeg(camera_index: int) -> bytes:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("系统里没有 ffmpeg")
    if os.name == "nt":
        list_cmd = [ffmpeg, "-list_devices", "true", "-f", "dshow", "-i", "dummy"]
        listed = subprocess.run(
            list_cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
        names = []
        blob = (listed.stderr or "") + "\n" + (listed.stdout or "")
        for line in blob.splitlines():
            if "\"" in line and ("video" in line.lower() or "camera" in line.lower() or "webcam" in line.lower()):
                start = line.find('"')
                end = line.find('"', start + 1)
                if start >= 0 and end > start:
                    names.append(line[start + 1 : end])
        if not names:
            # 回退：常见默认名
            names = ["Integrated Camera"]
        index = max(0, int(camera_index))
        if index >= len(names):
            index = 0
        source = f"video={names[index]}"
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "dshow",
            "-i",
            source,
            "-frames:v",
            "1",
            "-f",
            "image2",
            "pipe:1",
        ]
    else:
        cmd = [
            ffmpeg,
            "-y",
            "-f",
            "v4l2",
            "-i",
            f"/dev/video{int(camera_index)}",
            "-frames:v",
            "1",
            "-f",
            "image2",
            "pipe:1",
        ]
    proc = subprocess.run(cmd, capture_output=True, timeout=25)
    if proc.returncode != 0 or not proc.stdout:
        err = (proc.stderr or b"").decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(f"ffmpeg 拍照失败: {err}")
    return proc.stdout


def capture_jpeg(camera_index: int = 0) -> bytes:
    errors: list[str] = []
    for grabber in (_grab_with_opencv, _grab_with_ffmpeg):
        try:
            data = grabber(camera_index)
            if data:
                return data
        except Exception as exc:  # noqa: BLE001 - 尝试下一个后端
            errors.append(f"{grabber.__name__}: {exc}")
    detail = "；".join(errors) or "未知错误"
    raise RuntimeError(
        "拍照失败。请确认摄像头已连接，并已安装 opencv-python 或 ffmpeg。"
        f" 详情: {detail} (python={sys.executable})"
    )


def save_photo(dest: Path, camera_index: int = 0) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = capture_jpeg(camera_index)
    dest.write_bytes(data)
    return dest

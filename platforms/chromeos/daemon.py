#!/usr/bin/env python3
"""ChromeOS daemon for yep-anywhere device-bridge.

Binary framing protocol over stdin/stdout:
- Handshake (daemon -> sidecar): [width u16 LE][height u16 LE]
- Frame request (sidecar -> daemon): [0x01]
- Frame response (daemon -> sidecar): [0x02][len u32 LE][JPEG bytes]
- Control (sidecar -> daemon): [0x03][len u32 LE][JSON bytes]
"""

import base64
import json
import struct
import sys
from typing import Optional, Tuple

import client

TYPE_FRAME_REQUEST = 0x01
TYPE_FRAME_RESPONSE = 0x02
TYPE_CONTROL = 0x03


def read_exact(stream, n: int) -> bytes:
    data = bytearray()
    while len(data) < n:
        chunk = stream.read(n - len(data))
        if not chunk:
            raise EOFError("unexpected EOF")
        data.extend(chunk)
    return bytes(data)


def png_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 24:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    if data[12:16] != b"IHDR":
        return None
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width <= 0 or height <= 0:
        return None
    return width, height


def jpeg_size(data: bytes) -> Optional[Tuple[int, int]]:
    if len(data) < 4 or data[0] != 0xFF or data[1] != 0xD8:
        return None

    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        i += 2

        if marker in (0xD8, 0xD9):
            continue
        if i + 2 > len(data):
            return None

        seg_len = (data[i] << 8) | data[i + 1]
        if seg_len < 2 or i + seg_len > len(data):
            return None

        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            if i + 7 > len(data):
                return None
            height = (data[i + 3] << 8) | data[i + 4]
            width = (data[i + 5] << 8) | data[i + 6]
            if width <= 0 or height <= 0:
                return None
            return width, height

        i += seg_len

    return None


def image_size(data: bytes, image_format: str) -> Tuple[int, int]:
    if image_format == "png":
        size = png_size(data)
    else:
        size = jpeg_size(data)

    if size:
        return size

    info = client.cmd_info({})
    touch_max = info.get("touch_max") if isinstance(info, dict) else None
    if isinstance(touch_max, list) and len(touch_max) == 2:
        width, height = int(touch_max[0]), int(touch_max[1])
        if width > 0 and height > 0:
            return width, height

    # conservative fallback
    return 1920, 1080


def capture_frame() -> Tuple[bytes, int, int]:
    result = client.cmd_screenshot({"method": "egl", "format": "jpeg", "quality": 70})
    if result.get("error"):
        result = client.cmd_screenshot({"method": "gbm", "format": "jpeg", "quality": 70})
        if result.get("error"):
            raise RuntimeError(result["error"])

    b64 = result.get("image")
    if not b64:
        raise RuntimeError("missing screenshot image data")

    frame = base64.b64decode(b64)
    fmt = result.get("format", "jpeg")
    if str(fmt).lower() != "jpeg":
        raise RuntimeError(f"unexpected non-jpeg frame format: {fmt}")
    width, height = image_size(frame, fmt)
    return frame, width, height


def run_control(payload: bytes, width: int, height: int) -> None:
    try:
        msg = json.loads(payload.decode("utf-8"))
    except Exception:
        return

    cmd = msg.get("cmd")
    if cmd == "touch":
        touches = msg.get("touches") or []
        if not touches:
            return
        t = touches[0]
        try:
            x = float(t.get("x", 0.0))
            y = float(t.get("y", 0.0))
        except Exception:
            return

        px = max(0, min(width - 1, int(round(x * width))))
        py = max(0, min(height - 1, int(round(y * height))))
        try:
            client.tap(px, py)
        except Exception:
            return
        return

    if cmd == "key":
        key = str(msg.get("key", "")).lower()
        try:
            if key == "back":
                client.shortcut(["alt"], "left")
            elif key in ("left", "right", "up", "down"):
                client.shortcut([], key)
            elif key == "enter":
                client.shortcut([], "enter")
            elif key == "tab":
                client.shortcut([], "tab")
            elif key == "escape":
                client.shortcut([], "escape")
            elif key == "space":
                client.shortcut([], "space")
        except Exception:
            return


def main() -> int:
    sys.stdout = sys.stdout.detach()
    stdin = sys.stdin.buffer
    stdout = sys.stdout

    frame, width, height = capture_frame()
    stdout.write(struct.pack("<HH", width, height))
    stdout.flush()

    while True:
        b = stdin.read(1)
        if not b:
            return 0
        msg_type = b[0]

        if msg_type == TYPE_FRAME_REQUEST:
            frame, width, height = capture_frame()
            stdout.write(bytes([TYPE_FRAME_RESPONSE]))
            stdout.write(struct.pack("<I", len(frame)))
            stdout.write(frame)
            stdout.flush()
            continue

        if msg_type == TYPE_CONTROL:
            raw_len = read_exact(stdin, 4)
            payload_len = struct.unpack("<I", raw_len)[0]
            payload = read_exact(stdin, payload_len)
            run_control(payload, width, height)
            continue

        raise RuntimeError(f"unknown message type: 0x{msg_type:02x}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except EOFError:
        raise SystemExit(0)

#!/usr/bin/env python3
"""Dedicated-appliance virtual input broker for a GNOME Wayland session."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pwd
import subprocess
import time
from pathlib import Path
from typing import Any

from evdev import AbsInfo, UInput, ecodes


MAX_ABSOLUTE = 32767
BUTTONS = {
    "left": ecodes.BTN_LEFT,
    "right": ecodes.BTN_RIGHT,
    "middle": ecodes.BTN_MIDDLE,
}
ALIASES = {
    "alt": "KEY_LEFTALT",
    "backspace": "KEY_BACKSPACE",
    "ctrl": "KEY_LEFTCTRL",
    "delete": "KEY_DELETE",
    "down": "KEY_DOWN",
    "end": "KEY_END",
    "enter": "KEY_ENTER",
    "esc": "KEY_ESC",
    "escape": "KEY_ESC",
    "home": "KEY_HOME",
    "left": "KEY_LEFT",
    "meta": "KEY_LEFTMETA",
    "pagedown": "KEY_PAGEDOWN",
    "pageup": "KEY_PAGEUP",
    "right": "KEY_RIGHT",
    "shift": "KEY_LEFTSHIFT",
    "space": "KEY_SPACE",
    "super": "KEY_LEFTMETA",
    "tab": "KEY_TAB",
    "up": "KEY_UP",
}


class InputFailure(RuntimeError):
    pass


def active_user() -> pwd.struct_passwd:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["/usr/bin/loginctl", "list-sessions", "--no-legend", "--no-pager"],
            check=False,
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            fields = line.split()
            if "active" in fields and len(fields) >= 3:
                try:
                    return pwd.getpwnam(fields[2])
                except KeyError:
                    continue
        time.sleep(1)
    raise InputFailure("No active desktop user became available")


def key_code(name: str) -> int:
    normalized = name.strip().casefold().replace("-", "")
    constant = ALIASES.get(normalized)
    if constant is None:
        if len(normalized) == 1 and normalized.isalnum():
            constant = f"KEY_{normalized.upper()}"
        else:
            constant = f"KEY_{normalized.upper()}"
    value = ecodes.ecodes.get(constant)
    if not isinstance(value, int):
        raise InputFailure(f"Unknown key: {name}")
    return value


def pointer_capabilities() -> dict[int, Any]:
    keyboard_codes = sorted(
        code
        for code, name in ecodes.keys.items()
        if isinstance(code, int) and str(name).startswith("KEY_")
    )
    return {
        ecodes.EV_KEY: keyboard_codes + list(BUTTONS.values()),
        ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y, ecodes.REL_WHEEL,
                        ecodes.REL_HWHEEL],
        ecodes.EV_ABS: [
            (
                ecodes.ABS_X,
                AbsInfo(0, 0, MAX_ABSOLUTE, 0, 0, 100),
            ),
            (
                ecodes.ABS_Y,
                AbsInfo(0, 0, MAX_ABSOLUTE, 0, 0, 100),
            ),
        ],
    }


class Broker:
    def __init__(self) -> None:
        self.device = UInput(
            pointer_capabilities(),
            name="LinuxVM Target-Native Control",
            version=0x0001,
        )

    def emit_absolute(self, x: int, y: int, width: int, height: int) -> None:
        if width <= 1 or height <= 1:
            raise InputFailure("Coordinate space must be at least 2 by 2")
        if not 0 <= x < width or not 0 <= y < height:
            raise InputFailure("Point lies outside the coordinate space")
        self.device.write(
            ecodes.EV_ABS,
            ecodes.ABS_X,
            round(x * MAX_ABSOLUTE / (width - 1)),
        )
        self.device.write(
            ecodes.EV_ABS,
            ecodes.ABS_Y,
            round(y * MAX_ABSOLUTE / (height - 1)),
        )
        self.device.syn()

    def click(self, button: str, count: int) -> None:
        code = BUTTONS.get(button)
        if code is None or count not in range(1, 4):
            raise InputFailure("Click needs a known button and count from 1 to 3")
        for _ in range(count):
            self.device.write(ecodes.EV_KEY, code, 1)
            self.device.syn()
            self.device.write(ecodes.EV_KEY, code, 0)
            self.device.syn()
            time.sleep(0.04)

    def chord(self, value: str) -> None:
        codes = [key_code(part) for part in value.split("+") if part]
        if not codes:
            raise InputFailure("Key chord is empty")
        for code in codes:
            self.device.write(ecodes.EV_KEY, code, 1)
        self.device.syn()
        for code in reversed(codes):
            self.device.write(ecodes.EV_KEY, code, 0)
        self.device.syn()

    def handle(self, request: dict[str, Any]) -> dict[str, Any]:
        operation = str(request.get("operation") or "")
        if operation == "status":
            return {"accepted": True, "state": "ready"}
        if operation == "move":
            self.emit_absolute(
                int(request["x"]),
                int(request["y"]),
                int(request["width"]),
                int(request["height"]),
            )
        elif operation == "move_relative":
            self.device.write(ecodes.EV_REL, ecodes.REL_X, int(request["dx"]))
            self.device.write(ecodes.EV_REL, ecodes.REL_Y, int(request["dy"]))
            self.device.syn()
        elif operation == "click":
            self.click(str(request.get("button") or "left"), int(request.get("count", 1)))
        elif operation == "drag":
            self.emit_absolute(
                int(request["x1"]),
                int(request["y1"]),
                int(request["width"]),
                int(request["height"]),
            )
            self.device.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
            self.device.syn()
            steps = max(2, min(int(request.get("steps", 12)), 120))
            duration = max(0, min(int(request.get("durationMs", 240)), 5000))
            for step in range(1, steps + 1):
                ratio = step / steps
                self.emit_absolute(
                    round(int(request["x1"]) +
                          (int(request["x2"]) - int(request["x1"])) * ratio),
                    round(int(request["y1"]) +
                          (int(request["y2"]) - int(request["y1"])) * ratio),
                    int(request["width"]),
                    int(request["height"]),
                )
                time.sleep(duration / steps / 1000)
            self.device.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
            self.device.syn()
        elif operation == "scroll":
            self.device.write(ecodes.EV_REL, ecodes.REL_HWHEEL, int(request.get("dx", 0)))
            self.device.write(ecodes.EV_REL, ecodes.REL_WHEEL, int(request.get("dy", 0)))
            self.device.syn()
        elif operation == "key":
            self.chord(str(request.get("key") or ""))
        else:
            raise InputFailure(f"Unsupported input operation: {operation}")
        return {"accepted": True, "state": "delivered"}


async def serve_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    broker: Broker,
) -> None:
    try:
        line = await reader.readline()
        request = json.loads(line.decode("utf-8"))
        if not isinstance(request, dict):
            raise InputFailure("Request must be an object")
        response = broker.handle(request)
    except (InputFailure, KeyError, TypeError, ValueError) as error:
        response = {"accepted": False, "error": str(error)}
    except Exception as error:
        response = {"accepted": False, "error": f"Input provider failed: {error}"}
    writer.write(json.dumps(response, separators=(",", ":")).encode() + b"\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def run_server(socket_path: Path) -> None:
    owner = active_user()
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists():
        socket_path.unlink()
    broker = Broker()
    server = await asyncio.start_unix_server(
        lambda reader, writer: serve_client(reader, writer, broker),
        path=str(socket_path),
    )
    os.chown(socket_path, owner.pw_uid, owner.pw_gid)
    os.chmod(socket_path, 0o600)
    async with server:
        await server.serve_forever()


def main() -> int:
    parser = argparse.ArgumentParser(prog="linuxinputd")
    parser.add_argument("--socket", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(run_server(args.socket))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

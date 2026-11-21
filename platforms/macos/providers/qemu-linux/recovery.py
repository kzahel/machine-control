"""Typed framebuffer and keyboard recovery shared by Mac QEMU adapters."""

import os
from pathlib import Path
import struct
import tempfile
import time

from vnc import KEYS, Keyboard, observed_frame


class ConsoleFrameChanged(ValueError):
    """The recovery guard refused before opening the credential file."""


class RecoveryConsole:
    """The caller first binds the active backend to an exact appliance."""

    def recovery_keyboard(self, action, *values):
        with Keyboard(self) as keyboard:
            if action == "key":
                keyboard.chord(KEYS[values[0]])
                return
            observations = {observed_frame(value): value for value in values}
            with tempfile.TemporaryDirectory(prefix="macvm-qemu-") as directory:
                output = Path(directory) / "console.png"
                deadline = time.monotonic() + 12
                # A blinking insertion point can repeatedly land in the
                # opposite phase when grabs are spaced at a fixed interval.
                for delay in (0.12, 0.21, 0.30, 0.39) * 5:
                    self.screenshot(output)
                    frame = output.read_bytes()
                    if frame in observations:
                        break
                    if time.monotonic() >= deadline:
                        raise ConsoleFrameChanged(
                            "The observed password field frame changed before credential entry"
                        )
                    time.sleep(delay)
                else:
                    raise ConsoleFrameChanged(
                        "The observed password field frame changed before credential entry"
                    )
            if observed_frame(observations[frame]) != frame:
                raise ConsoleFrameChanged(
                    "The observed password field screenshot changed before credential entry"
                )
            keyboard.verify_exclusive_client(self)
            keyboard.type_password(os.environ["MACVM_QEMU_LOGIN_SECRET_FILE"])

    def click(self, x, y):
        if not any(mouse.get("current") and mouse.get("absolute")
                   for mouse in self.request("query-mice")):
            raise ValueError("QEMU has no active absolute pointer")
        with tempfile.TemporaryDirectory(prefix="macvm-qemu-") as directory:
            output = Path(directory) / "geometry.png"
            self.screenshot(output)
            with output.open("rb") as image:
                header = image.read(24)
        if header[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" or len(header) != 24:
            raise ValueError("The current framebuffer geometry is unavailable")
        width, height = struct.unpack("!II", header[16:24])
        if not (1 < width and 1 < height and 0 <= x < width and 0 <= y < height):
            raise ValueError("Point is outside the current framebuffer")
        self.request("input-send-event", events=[
            {"type": "abs", "data": {"axis": axis, "value": round(value * 32767 / (extent - 1))}}
            for axis, value, extent in (("x", x, width), ("y", y, height))
        ])
        event = {"type": "btn", "data": {"button": "left", "down": True}}
        self.request("input-send-event", events=[event])
        time.sleep(0.09)
        event["data"]["down"] = False
        self.request("input-send-event", events=[event])


def private_screenshot_path(value):
    output = Path(value)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("Provide a new absolute screenshot path")
    parent = output.parent.stat()
    if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
        raise ValueError("Screenshot destination must be owner-only")
    return output


def recover(console, arguments):
    if os.environ.get("MACVM_QEMU_FORBID_OUTER_UI") == "true":
        raise ValueError("Outer recovery is disabled for this target")
    if len(arguments) == 2 and arguments[0] == "screenshot":
        console.screenshot(private_screenshot_path(arguments[1]))
    elif len(arguments) == 3 and arguments[0] == "click":
        console.click(int(arguments[1]), int(arguments[2]))
    elif len(arguments) == 2 and arguments[0] == "key":
        console.recovery_keyboard(*arguments)
    elif len(arguments) in {2, 3} and arguments[0] == "type-secret":
        console.recovery_keyboard(*arguments)
    else:
        return 2
    return 0

#!/usr/bin/env python3
"""Identify a local QEMU process by its open OpenCore and system disks."""

import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import tempfile
import time


class QemuOffline(ConnectionError):
    """The configured QMP socket has no listener."""


class QemuIdentity:
    def __init__(self):
        self.directory = Path(os.environ["MACVM_QEMU_DIRECTORY"]).resolve(strict=True)
        info = self.directory.stat()
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("QEMU directory must be owner-only")
        self.endpoint = self.directory / "qmp.sock"
        self.disks = {}
        for role, device in (("OPENCORE", "BootLoader"), ("SYSTEM", "SystemDisk")):
            path = Path(os.environ[f"MACVM_QEMU_{role}_DISK"])
            if not path.is_absolute() or path.is_symlink():
                raise ValueError("A pinned disk must be an absolute local file")
            path = path.resolve(strict=True)
            if not path.is_relative_to(self.directory):
                raise ValueError("A pinned disk is outside the QEMU directory")
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError("A pinned disk is not an owned regular file")
            pinned = os.environ[f"MACVM_QEMU_{role}_DISK_ID"]
            if pinned != f"{info.st_dev}:{info.st_ino}":
                raise ValueError("A disk does not match its private identity pin")
            self.disks[device] = pinned
        if self.disks["BootLoader"] == self.disks["SystemDisk"]:
            raise ValueError("OpenCore and system disks must be distinct")

    @property
    def resource(self):
        return self.disks["SystemDisk"]

    def __enter__(self):
        self.peer = socket.socket(socket.AF_UNIX)
        try:
            self.peer.settimeout(5)
            try:
                endpoint = self.endpoint.lstat()
                if not stat.S_ISSOCK(endpoint.st_mode) or endpoint.st_uid != os.getuid():
                    raise ValueError("QMP endpoint is not an owner-controlled Unix socket")
                self.peer.connect(str(self.endpoint))
            except (FileNotFoundError, ConnectionRefusedError) as error:
                raise QemuOffline from error
            pid, uid, _ = struct.unpack(
                "3i", self.peer.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            process = Path("/proc") / str(pid)
            if uid != os.getuid() or not (process / "exe").resolve().name.startswith(
                "qemu-system-x86_64"
            ):
                raise ValueError("QMP peer is not the expected local QEMU executable")
            opened = set()
            for descriptor in (process / "fd").iterdir():
                try:
                    info = descriptor.stat()
                except FileNotFoundError:
                    continue
                if stat.S_ISREG(info.st_mode):
                    opened.add(f"{info.st_dev}:{info.st_ino}")
            if not set(self.disks.values()).issubset(opened):
                raise ValueError("QMP peer does not hold both pinned disks")
            self.stream = self.peer.makefile("rwb")
            if "QMP" not in self.receive():
                raise ValueError("Expected a QMP greeting")
            self.request("qmp_capabilities")
            kvm = self.request("query-kvm")
            if kvm.get("enabled") is not True or kvm.get("present") is not True:
                raise ValueError("QMP peer is not running with KVM")
            self.verify_block_devices(process / "cwd")
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *_):
        if hasattr(self, "stream"):
            self.stream.close()
        self.peer.close()

    def verify_block_devices(self, working_directory):
        actual = {}
        for block in self.request("query-block"):
            name = block.get("device")
            if name not in self.disks:
                continue
            disk = block.get("inserted") or {}
            path = disk.get("file")
            if name in actual or not path or disk.get("drv") != "qcow2":
                raise ValueError("Unexpected QMP block device")
            info = (working_directory / path).stat()
            actual[name] = f"{info.st_dev}:{info.st_ino}"
        if actual != self.disks:
            raise ValueError("QMP block roles do not match both pinned disks")

    def receive(self):
        return json.loads(self.stream.readline(1024 * 1024))

    def request(self, operation, **arguments):
        payload = {"execute": operation, "arguments": arguments}
        self.stream.write(json.dumps(payload).encode() + b"\n")
        self.stream.flush()
        while True:
            response = self.receive()
            if "error" in response:
                raise ValueError("QMP rejected the operation")
            if "return" in response:
                return response["return"]

    def state(self):
        try:
            with self:
                status = self.request("query-status").get("status")
        except QemuOffline:
            return "off"
        return {"running": "running", "paused": "suspended",
                "prelaunch": "starting"}.get(status, "unknown")

    def screenshot(self, output):
        self.request("screendump", filename=str(output), format="png")

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


def main(arguments):
    identity = QemuIdentity()
    if arguments == ["identity"]:
        print(identity.resource)
    elif arguments == ["status"]:
        print(identity.state())
    elif len(arguments) == 2 and arguments[0] == "screenshot":
        output = Path(arguments[1])
        if not output.is_absolute() or output.exists() or output.is_symlink():
            raise ValueError("Provide a new absolute screenshot path")
        if os.environ.get("MACVM_QEMU_FORBID_OUTER_UI") == "true":
            raise ValueError("Outer recovery is disabled for this target")
        parent = output.parent.stat()
        if parent.st_uid != os.getuid() or parent.st_mode & 0o077:
            raise ValueError("Screenshot destination must be owner-only")
        with identity:
            identity.screenshot(output)
    elif len(arguments) == 3 and arguments[0] == "click":
        if os.environ.get("MACVM_QEMU_FORBID_OUTER_UI") == "true":
            raise ValueError("Outer recovery is disabled for this target")
        with identity:
            identity.click(int(arguments[1]), int(arguments[2]))
    elif arguments == ["shutdown"]:
        with identity:
            identity.request("system_powerdown")
    else:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError):
        print("Could not verify or operate the pinned QEMU target", file=sys.stderr)
        raise SystemExit(1)

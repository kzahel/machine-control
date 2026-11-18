"""Bounded RFB keyboard input for an exact QEMU appliance's recovery console."""

import os
from pathlib import Path
import socket
import stat
import struct
import time

KEYS = {
    "wake": (0xFFE1,),
    "enter": (0xFF0D,),
    "escape": (0xFF1B,),
    "tab": (0xFF09,),
    "lock": (0xFFEB, 0xFFE3, ord("q")),
    "cmd-shift-g": (0xFFEB, 0xFFE1, ord("g")),
}
SHIFTED = dict(zip(b'!@#$%^&*()_+{}|:"<>?~', b"1234567890-=[]\\;',./`"))
SHIFTED.update({value: value + 32 for value in range(ord("A"), ord("Z") + 1)})
SCREEN_MAX_AGE = 30


class Keyboard:
    """Use an owner-checked loopback display supplied by the active QMP peer."""

    def __init__(self, qmp):
        display = qmp.request("query-vnc")
        port = display.get("service")
        if (display.get("enabled") is not True or display.get("host") != "127.0.0.1"
                or display.get("auth") != "none" or not isinstance(port, str)
                or not port.isascii() or not port.isdecimal()
                or not 1 <= int(port) <= 65535 or display.get("clients")):
            raise ValueError("An exclusive loopback VNC display is required")
        self.endpoint = ("127.0.0.1", int(port))

    def __enter__(self):
        self.peer = socket.create_connection(self.endpoint, timeout=4)
        self.stream = self.peer.makefile("rb")
        try:
            if self.read(12) != b"RFB 003.008\n":
                raise ValueError("Unexpected RFB protocol")
            self.peer.sendall(b"RFB 003.008\n")
            if 1 not in self.read(self.read(1)[0]):
                raise ValueError("Unexpected RFB security types")
            self.peer.sendall(b"\x01")
            if self.read(4) != bytes(4):
                raise ValueError("RFB connection refused")
            # Shared connection. The caller must not displace an operator.
            self.peer.sendall(b"\x01")
            self.read(20)
            size = struct.unpack("!I", self.read(4))[0]
            if size > 4096:
                raise ValueError("Unexpected RFB desktop name length")
            self.read(size)
        except BaseException:
            self.__exit__()
            raise
        return self

    def __exit__(self, *_):
        self.stream.close()
        self.peer.close()

    def read(self, size):
        value = self.stream.read(size)
        if len(value) != size:
            raise ValueError("RFB connection ended during negotiation")
        return value

    def event(self, symbol, down):
        self.peer.sendall(struct.pack("!BBHI", 4, down, 0, symbol))

    def chord(self, keys):
        pressed = []
        try:
            for symbol in keys:
                self.event(symbol, True)
                pressed.append(symbol)
                time.sleep(0.025)
        finally:
            for symbol in reversed(pressed):
                self.event(symbol, False)
        time.sleep(0.015)

    def type_password(self, secret_file):
        payload = stored_password(secret_file)
        if any(not 32 <= value <= 126 for value in payload):
            raise ValueError("Credential cannot be entered with the U.S. keyboard map")
        for value in payload:
            self.chord((0xFFE1, SHIFTED[value]) if value in SHIFTED else (value,))
        self.chord(KEYS["enter"])

    def verify_exclusive_client(self, qmp):
        clients = qmp.request("query-vnc").get("clients")
        host, port = self.peer.getsockname()
        if not isinstance(clients, list) or len(clients) != 1 or (
            clients[0].get("host"), clients[0].get("service")
        ) != (host, str(port)):
            raise ValueError("The recovery console no longer has the exclusive client")


def stored_password(secret_file):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(secret_file, flags), "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError("Refused an unsafe credential file")
        payload = source.read(513).removesuffix(b"\n")
    if not 0 < len(payload) <= 512 or b"\n" in payload or b"\r" in payload or b"\0" in payload:
        raise ValueError("Invalid credential file framing")
    return payload


def observed_frame(path):
    """Read a recent private recovery observation without following a symlink."""
    path = Path(path)
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or not 0 <= time.time() - info.st_mtime <= SCREEN_MAX_AGE
                or not 24 <= info.st_size <= 32 * 1024 * 1024):
            raise ValueError("A recent owner-only recovery screenshot is required")
        return source.read(32 * 1024 * 1024 + 1)

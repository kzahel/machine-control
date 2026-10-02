#!/usr/bin/python3
"""Chrome native messaging bridge. No grant or approval authority."""

import json
import os
from pathlib import Path
import socket
import struct
import sys
import threading

ORIGIN = "chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/"
LIMIT = 1024 * 1024


def exact(stream, count):
    data = bytearray()
    while len(data) < count:
        value = stream.read(count - len(data))
        if not value:
            raise EOFError()
        data.extend(value)
    return bytes(data)


def main():
    if len(sys.argv) < 2 or sys.argv[1] != ORIGIN:
        raise SystemExit("Machine Control extension origin required")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(str(Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop/desktop.sock"))
        client.sendall(b'{"operation":"browser.register"}\n')

        def incoming():
            try:
                with client.makefile("rb") as stream:
                    while True:
                        frame = stream.readline(LIMIT + 1)
                        if not frame or len(frame) > LIMIT or not frame.endswith(b"\n"):
                            break
                        json.loads(frame)
                        sys.stdout.buffer.write(struct.pack("<I", len(frame)) + frame)
                        sys.stdout.buffer.flush()
            except (OSError, ValueError):
                pass
            # Closing Chrome's host must close both halves, including a blocked
            # native stdin read. The extension reconnects through the new owner.
            os._exit(0)

        threading.Thread(target=incoming, daemon=True).start()
        try:
            while True:
                size = struct.unpack("<I", exact(sys.stdin.buffer, 4))[0]
                if not 0 < size <= LIMIT:
                    break
                value = json.loads(exact(sys.stdin.buffer, size))
                if not isinstance(value, dict):
                    break
                client.sendall(json.dumps(value, separators=(",", ":")).encode() + b"\n")
        except (EOFError, OSError, ValueError):
            pass


if __name__ == "__main__":
    main()

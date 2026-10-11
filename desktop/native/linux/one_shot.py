"""Bound one-shot native UI reads and retain capacity through kernel reaping."""
import os
import select
import subprocess
import time


def read_reply(process, cancelled, deadline, limit=65536):
    frame = bytearray()
    descriptor = process.stdout.fileno()
    os.set_blocking(descriptor, False)
    try:
        while not cancelled.is_set() and time.monotonic() < deadline:
            if not select.select([descriptor], [], [], .1)[0]:
                continue
            chunk = os.read(descriptor, min(4096, limit + 1 - len(frame)))
            if not chunk:
                break
            frame.extend(chunk)
            if len(frame) > limit:
                break
            if b"\n" in frame:
                return bytes(frame.split(b"\n", 1)[0])
        return b""
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=.3)
        except subprocess.TimeoutExpired:
            process.kill()
            # The physical slot stays occupied until the OS reaps this child.
            process.wait()

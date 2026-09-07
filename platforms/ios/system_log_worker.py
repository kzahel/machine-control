#!/usr/bin/env python3
"""Private bounded spool worker for one idevicesyslog capture."""

from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import signal
import subprocess
import sys


MAXIMUM_BYTES = 16 * 1024 * 1024


def require_environment(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise RuntimeError(f"missing {name}")
    return value


def append_bounded(
    chunks: deque[bytes], total: int, payload: bytes, maximum: int
) -> int:
    if len(payload) >= maximum:
        chunks.clear()
        chunks.append(payload[-maximum:])
        return maximum
    chunks.append(payload)
    total += len(payload)
    while total > maximum:
        excess = total - maximum
        first = chunks[0]
        if len(first) <= excess:
            chunks.popleft()
            total -= len(first)
        else:
            chunks[0] = first[excess:]
            total -= excess
    return total


def main() -> int:
    binary = require_environment("IOS_DEVICE_SYSTEM_LOG_BINARY")
    device = require_environment("IOS_DEVICE_SYSTEM_LOG_DEVICE")
    output = Path(require_environment("IOS_DEVICE_SYSTEM_LOG_OUTPUT"))
    ready = Path(require_environment("IOS_DEVICE_SYSTEM_LOG_READY"))
    child = subprocess.Popen(
        [binary, "--udid", device, "--no-colors"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )

    def stop(_signum: int, _frame: object) -> None:
        if child.poll() is None:
            child.send_signal(signal.SIGINT)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    chunks: deque[bytes] = deque()
    total = 0
    assert child.stdout is not None
    ready_descriptor = os.open(
        ready, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(ready_descriptor, "w", encoding="utf-8") as ready_handle:
        ready_handle.write("ready\n")
    try:
        while True:
            payload = child.stdout.read(64 * 1024)
            if not payload:
                break
            total = append_bounded(chunks, total, payload, MAXIMUM_BYTES)
    finally:
        if child.poll() is None:
            child.send_signal(signal.SIGINT)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
        output_descriptor = os.open(
            output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600
        )
        with os.fdopen(output_descriptor, "wb") as output_handle:
            output_handle.write(b"".join(chunks))
        ready.unlink(missing_ok=True)
    return 0 if child.returncode in {0, -signal.SIGINT} else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"system log worker failed: {error}", file=sys.stderr)
        raise SystemExit(1)

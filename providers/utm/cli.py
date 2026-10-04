#!/usr/bin/env python3
"""Run UTM's CLI with bounded, content-free controller diagnostics.

Keep stdin/stdout unchanged. Drain and forward stderr, retaining only closed
failure categories. Never persist arguments, environment, or stream contents.
"""
from __future__ import annotations

import datetime
import fcntl
import json
import os
from pathlib import Path
import plistlib
import platform
import re
import signal
import stat
import subprocess
import sys
import time
import uuid

MAX_BYTES = 1024 * 1024
SEGMENTS = 3
OPERATIONS = frozenset({
    "list", "status", "version", "start", "stop", "suspend", "clone",
    "delete", "ip-address", "exec", "file", "usb", "--help", "--version",
})
MARKERS = {
    "scripting_definition_unavailable": b"failed to get scripting definition",
    "unrecognized_selector": b"unrecognized selector",
    "objc_exception": b"NSInvalidArgumentException",
    "apple_events_not_permitted": b"(-1743)",
}


def log_directory() -> Path:
    override = os.environ.get("MACHINE_CONTROL_UTM_DIAGNOSTICS_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library/Logs/MachineControl/providers/utm"
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/utm"


def private_open(path: Path) -> int:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
        os.close(fd)
        raise OSError("unsafe diagnostic file")
    os.fchmod(fd, 0o600)
    return fd


def append_event(event: dict) -> None:
    directory = log_directory()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise OSError("unsafe diagnostic directory")
    directory.chmod(0o700)
    lock = private_open(directory / ".lock")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / "calls.jsonl"
        fd = private_open(path)
        try:
            if os.fstat(fd).st_size >= MAX_BYTES:
                os.close(fd)
                fd = -1
                for index in range(SEGMENTS - 1, 0, -1):
                    previous = directory / ("calls.jsonl" if index == 1 else f"calls.{index - 1}.jsonl")
                    if previous.exists():
                        previous.replace(directory / f"calls.{index}.jsonl")
                fd = private_open(path)
            row = {"schema": "machine-control-utm-diagnostic/v0", **event,
                   "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
            with os.fdopen(os.dup(fd), "a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, separators=(",", ":")) + "\n")
                stream.flush()
        finally:
            if fd >= 0:
                os.close(fd)
    finally:
        os.close(lock)


def bundle_metadata(executable: str) -> dict:
    try:
        # Read bundle metadata; never launch a second utmctl for diagnostics.
        path = Path(executable).resolve().parent.parent / "Info.plist"
        info = plistlib.loads(path.read_bytes())
        result = {}
        for key, field in (("utmVersion", "CFBundleShortVersionString"), ("utmBuild", "CFBundleVersion")):
            value = info.get(field, "")
            result[key] = value if isinstance(value, str) and re.fullmatch(r"[0-9.]{1,32}", value) else None
        return result
    except (OSError, ValueError, plistlib.InvalidFileException):
        return {"utmVersion": None, "utmBuild": None}


def run(source: str, executable: str, arguments: list[str]) -> int:
    operation = arguments[0] if arguments and arguments[0] in OPERATIONS else "other"
    if operation == "file" and len(arguments) > 1 and arguments[1] in {"push", "pull"}:
        operation += "." + arguments[1]
    context = {"id": uuid.uuid4().hex, "source": source, "operation": operation,
               "wrapperPid": os.getpid(), "callerPid": os.getppid(),
               "macOSVersion": platform.mac_ver()[0] if sys.platform == "darwin" else None,
               **bundle_metadata(executable)}
    logging_ok = True

    def record(**fields: object) -> None:
        nonlocal logging_ok
        if logging_ok:
            try:
                append_event({**context, **fields})
            except (OSError, ValueError):
                logging_ok = False
                print("machine-control: UTM diagnostics unavailable", file=sys.stderr)

    started = time.monotonic()
    record(event="intent")
    child = None
    pending_signals: list[int] = []
    old_handlers = {}

    def forward(signum: int, _frame: object) -> None:
        pending_signals.append(signum)
        if child is not None and child.poll() is None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        old_handlers[signum] = signal.signal(signum, forward)
    try:
        try:
            child = subprocess.Popen([executable, *arguments], stderr=subprocess.PIPE)
        except OSError:
            record(event="result", outcome="launch_failed", elapsedMs=round((time.monotonic() - started) * 1000))
            print("machine-control: unable to launch UTM CLI", file=sys.stderr)
            return 127
        record(event="spawn", pid=child.pid)
        for signum in tuple(pending_signals):
            forward(signum, None)
        categories: set[str] = set()
        tail = b""
        assert child.stderr is not None
        forwarding = True
        with child.stderr:
            while chunk := os.read(child.stderr.fileno(), 8192):
                scan = tail + chunk
                categories.update(code for code, marker in MARKERS.items() if marker in scan)
                tail = scan[-256:]
                if forwarding:
                    try:
                        sys.stderr.buffer.write(chunk)
                        sys.stderr.buffer.flush()
                    except (BrokenPipeError, OSError):
                        forwarding = False
        code = child.wait()
        record(event="result", pid=child.pid, returnCode=code,
               signal=-code if code < 0 else None,
               outcome="crashed" if code < 0 else ("success" if code == 0 else "failed"),
               failureCategories=sorted(categories),
               elapsedMs=round((time.monotonic() - started) * 1000))
        return 128 - code if code < 0 else code
    finally:
        for signum, handler in old_handlers.items():
            signal.signal(signum, handler)


def main() -> int:
    if len(sys.argv) < 4 or sys.argv[1] not in {"windows", "linux", "workspace", "diagnostic"}:
        print("Usage: cli.py windows|linux|workspace|diagnostic UTMCTL COMMAND [ARG...]", file=sys.stderr)
        return 2
    return run(sys.argv[1], sys.argv[2], sys.argv[3:])


if __name__ == "__main__":
    raise SystemExit(main())

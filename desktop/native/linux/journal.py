"""Private bounded durable history. Never serialize requests or result payloads."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time
import uuid

KNOWN = set("applications windows snapshot capture screenshot action focus set_value app.launch app.activate application.launch application.activate application.terminate invoke set.value click key type input.move input.click input.key input.text input.scroll input.drag window.state browser.tabs browser.wait browser.navigate browser.snapshot browser.click browser.type browser.key browser.capture browser.release browser.upload browser.cdp browser.eval browser.provider browser.register grant.request grant.revoke runtime.stop server.stop session.control session.control.end session.unlock authorization.begin authorization.cancel authorization.submit permissions.request update.check".split())
DISCOVERY = {"status", "capabilities", "grant.status", "update.status", "browser.endpoint"}


def token(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-zA-Z0-9_./:-]{1,160}", value) else "unknown"


def correlation(value):
    return hashlib.sha256(str(value or "").encode()).hexdigest()[:24]


class Journal:
    def __init__(self, root=None, segment_bytes=1048576, audit_bytes=104857600,
                 diagnostic_bytes=52428800):
        self.root = Path(root) if root else Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "machine-control/logs"
        self.segment_bytes = segment_bytes
        self.caps = {"audit": audit_bytes, "diagnostics": diagnostic_bytes}
        self.runtime = uuid.uuid4().hex
        self.sequence = 0
        self.error = None
        self.history_gap = False
        self.diagnostics_available = True
        self.debug_until = 0
        self.files = {}
        self.lock = threading.RLock()
        self.event("resident.start")

    @staticmethod
    def tracked(operation):
        return operation not in DISCOVERY

    def private_directory(self, path):
        if path.is_symlink():
            raise OSError("Unsafe log directory")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = path.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
            raise OSError("Unsafe log owner")
        path.chmod(0o700)

    def prune(self, directory, stream):
        files = sorted(directory.glob("*.jsonl"))
        total = sum(p.lstat().st_size for p in files)
        cutoff = time.time() - (30 if stream == "audit" else 7) * 86400
        for path in files:
            st = path.lstat()
            if st.st_mtime >= cutoff and total <= self.caps[stream]:
                break
            total -= st.st_size
            path.unlink()

    def append(self, stream, value):
        with self.lock:
            try:
                self.private_directory(self.root.parent)
                self.private_directory(self.root)
                directory = self.root / stream
                self.private_directory(directory)
                self.prune(directory, stream)
                path = self.files.get(stream)
                if path is None or not path.exists() or path.lstat().st_size >= self.segment_bytes:
                    path = directory / (f"{time.time_ns() // 1000:020d}" + "-" + self.runtime + ".jsonl")
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    os.close(fd)
                    self.files[stream] = path
                self.sequence += 1
                value = {**value, "schema": "machine-control-desktop-event/v0", "stream": stream,
                         "eventId": uuid.uuid4().hex, "runtimeId": self.runtime,
                         "sequence": self.sequence, "at": datetime.now(timezone.utc).isoformat(),
                         "component": "linux.resident"}
                data = (json.dumps(value, separators=(",", ":")) + "\n").encode()
                fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
                try:
                    st = os.fstat(fd)
                    if st.st_uid != os.getuid() or not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                        raise OSError("Unsafe log file")
                    os.fchmod(fd, 0o600)
                    while data:
                        count = os.write(fd, data)
                        if count <= 0:
                            raise OSError("Incomplete write")
                        data = data[count:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self.prune(directory, stream)
                if stream == "audit":
                    self.error = None
                else:
                    self.diagnostics_available = True
                return True
            except (OSError, ValueError):
                if stream == "audit":
                    self.error = "audit_storage_unavailable"
                else:
                    self.diagnostics_available = False
                return False

    def event(self, operation, accepted=True):
        return self.append("audit", {"phase": "event", "operation": token(operation), "accepted": accepted})

    def diagnostic(self, operation, code):
        return self.append("diagnostics", {"phase": "event", "operation": token(operation), "errorCode": token(code)})

    def begin(self, operation, request_id, generation=None, caller_pid=None):
        return not self.tracked(operation) or self.append("audit", {
            "phase": "intent", "operation": operation if operation in KNOWN else "unknown",
            "requestId": correlation(request_id), "generation": token(generation),
            "callerPid": caller_pid if type(caller_pid) is int else None,
            "effect": "unknown", "uncertainty": "outcome_pending"})

    def record(self, result):
        operation = result.get("operation", "")
        if not self.tracked(operation):
            return True
        value = {"phase": "result", "operation": operation if operation in KNOWN else "unknown",
                 "requestId": correlation(result.get("requestId")), "accepted": result.get("accepted") is True,
                 "elapsedMs": result.get("elapsedMs") if type(result.get("elapsedMs")) is int else 0}
        for key in ["generation", "actualRoute", "delivery", "effect", "uncertainty", "errorCode"]:
            value[key] = token(result.get(key)) if result.get(key) is not None else None
        if value["errorCode"] is not None or self.debug_until > time.monotonic():
            self.append("diagnostics", dict(value))
        return self.append("audit", value)

    def debug(self, enabled):
        self.debug_until = time.monotonic() + 900 if enabled else 0
        self.event("diagnostics.debug.enabled" if enabled else "diagnostics.debug.disabled")

    @property
    def health(self):
        return {"available": self.error is None, "errorCode": self.error,
                "diagnosticsAvailable": self.diagnostics_available, "historyGap": self.history_gap, "debugRemainingSeconds": max(0, int(self.debug_until - time.monotonic())),
                "auditDays": 30, "diagnosticDays": 7,
                "auditBytes": self.caps["audit"], "diagnosticBytes": self.caps["diagnostics"]}

    def read(self, stream):
        directory = self.root / ("diagnostics" if stream == "diagnostics" else "audit")
        if directory.is_symlink():
            raise OSError("Unsafe history directory")
        for path in sorted(directory.glob("*.jsonl"), reverse=True):
            st = path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or st.st_size > self.segment_bytes + 8192:
                continue
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as file:
                lines = file.read().splitlines(keepends=True)
            for line in reversed(lines):
                try:
                    if not line.endswith(b"\n"):
                        raise ValueError("Partial record")
                    value = json.loads(line)
                    if not isinstance(value, dict) or value.get("schema") != "machine-control-desktop-event/v0" or not all(isinstance(value.get(key), str) for key in ("eventId", "operation", "at", "phase")):
                        raise ValueError("Invalid event")
                    if "accepted" in value and type(value["accepted"]) is not bool:
                        raise ValueError("Invalid outcome")
                    yield value
                except (ValueError, AttributeError):
                    self.history_gap = True

    def earliest(self, stream):
        directory = self.root / ("diagnostics" if stream == "diagnostics" else "audit")
        paths = sorted(directory.glob("*.jsonl"))
        if not paths or directory.is_symlink():
            return None
        try:
            fd = os.open(paths[0], os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as file:
                row = json.loads(file.readline(8192))
                if not isinstance(row, dict) or not isinstance(row.get("at"), str):
                    raise ValueError("Invalid retained timestamp")
                return row["at"]
        except (OSError, ValueError):
            self.history_gap = True
            return None

    def query(self, offset=0, operation="", outcome="", stream="audit"):
        with self.lock:
            if type(offset) is not int or not 0 <= offset <= 1_000_000:
                raise ValueError("Invalid history page")
            entries = []
            skipped = 0
            for entry in self.read(stream):
                if operation and operation.lower() not in entry["operation"].lower():
                    continue
                if outcome and entry.get("accepted") is not (outcome == "accepted"):
                    continue
                if skipped < offset:
                    skipped += 1
                    continue
                entries.append(entry)
                if len(entries) == 51:
                    break
            return {"entries": entries[:50], "hasMore": len(entries) > 50, "offset": offset, "earliestAt": self.earliest(stream), "health": self.health}

    def preview(self):
        import itertools
        with self.lock:
            return {"schema": "machine-control-diagnostics-export/v0", "health": self.health,
                    "audit": list(itertools.islice(self.read("audit"), 500)),
                    "diagnostics": list(itertools.islice(self.read("diagnostics"), 500))}

    def export(self):
        with self.lock:
            directory = self.root / "exports"
            self.private_directory(directory)
            path = directory / "diagnostics.json"
            temporary = directory / (uuid.uuid4().hex + ".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "w") as file:
                json.dump(self.preview(), file, separators=(",", ":"))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
            return str(path)

"""Serial native grant authority, independent of the WebView and agent socket."""

from collections import deque
from datetime import datetime, timezone
import math
import time
import uuid

SCOPES = {"observe", "control", "browser", "devtools"}
OBSERVE = {"applications", "windows", "snapshot", "capture"}
CONTROL = {"action", "focus", "set_value", "application.launch", "application.activate",
           "application.terminate", "input.move", "input.click", "input.key", "input.text",
           "input.scroll", "input.drag"}
BROWSER = {"browser.tabs", "browser.wait", "browser.navigate", "browser.snapshot",
           "browser.click", "browser.type", "browser.key", "browser.capture", "browser.release"}
BROWSER_READ = {"browser.tabs", "browser.wait", "browser.snapshot", "browser.capture"}


def scope_for(operation):
    if operation in OBSERVE:
        return "observe"
    if operation in CONTROL:
        return "control"
    if operation in BROWSER:
        return "browser"
    if operation in {"browser.eval", "browser.cdp"}:
        return "devtools"
    return None


def scopes(value):
    if not isinstance(value, list) or not value or len(value) > 4 or any(
            not isinstance(v, str) or v not in SCOPES for v in value):
        raise ValueError("Choose available access scopes")
    return set(value)


def duration(value, maximum=3600, minimum=1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Duration must be {minimum}-{maximum} seconds")
    return value


class Grants:
    def __init__(self, changed=lambda: None, clock=time.monotonic):
        self.clock = clock
        self.changed = changed
        self.generation = uuid.uuid4().hex
        self.grant = self.pending = None
        self.updating = False
        self.ready = False
        self.last_ended = None
        self.activity = deque(maxlen=100)

    def refresh(self):
        if self.grant and self.clock() >= self.grant["expires"]:
            self.stop("expired")
        if self.pending and self.clock() >= self.pending["expires"]:
            self.finish_pending(False, "approval_timeout")

    def set_ready(self, value):
        lost = self.ready and not value
        self.ready = value
        if lost:
            self.stop("desktop_unavailable")

    def authorize(self, operation, expected=None):
        self.refresh()
        if expected is not None and expected != self.generation:
            return "stale_generation"
        scope = scope_for(operation)
        if not scope:
            return "unsupported_operation"
        if not self.ready:
            return "desktop_unavailable"
        if self.updating:
            return "update_in_progress"
        if self.pending and (scope in {"control", "devtools"} or
                             scope == "browser" and operation not in BROWSER_READ):
            return "approval_prompt_visible"
        allowed = self.grant["scopes"] if self.grant else set()
        if scope not in allowed and not (scope == "browser" and "devtools" in allowed):
            return "approval_required"
        return None

    def issue(self, selected, seconds, reason, caller):
        self.generation = uuid.uuid4().hex
        self.grant = {"scopes": selected, "expires": self.clock() + seconds,
                      "reason": reason, "requester": caller}
        self.last_ended = None
        self.changed()

    def arm(self, selected, seconds):
        self.refresh()
        if not self.ready or self.updating or self.pending:
            raise ValueError("Finish approval and use an unlocked desktop")
        self.issue(scopes(selected), duration(seconds), "Enabled by the person", "local operator")

    def request(self, request, caller, complete):
        self.refresh()
        selected = scopes(request.get("scopes"))
        seconds = duration(request.get("durationSeconds", 900))
        timeout = duration(request.get("timeoutSeconds", 120), 600, 5)
        reason = request.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
            raise ValueError("Choose a reason (1-240 characters)")
        if not self.ready or self.updating:
            complete(False, "desktop_unavailable" if not self.ready else "update_in_progress")
            return
        if self.pending:
            complete(False, "approval_pending")
            return
        if self.grant and selected <= self.grant["scopes"]:
            complete(True, None)
            return
        self.pending = {"id": uuid.uuid4().hex, "scopes": selected, "duration": seconds,
                        "reason": reason.strip(), "caller": caller,
                        "expires": self.clock() + timeout, "complete": complete}
        self.changed()

    def finish_pending(self, accepted, error=None):
        pending, self.pending = self.pending, None
        if pending:
            pending["complete"](accepted, error)
            self.changed()

    def decide(self, identifier, allow, selected, seconds):
        self.refresh()
        pending = self.pending
        if not pending or pending["id"] != identifier:
            raise ValueError("Approval request changed")
        if not allow:
            self.finish_pending(False, "approval_denied")
            return
        chosen = scopes(selected)
        duration(seconds)
        if not chosen <= pending["scopes"] or seconds > pending["duration"]:
            raise ValueError("Approval may only narrow scope and duration")
        if not self.ready or self.updating:
            raise ValueError("Desktop is unavailable")
        self.pending = None
        self.issue(chosen, seconds, pending["reason"], pending["caller"])
        pending["complete"](True, None)

    def stop(self, reason="stopped_by_person"):
        self.generation = uuid.uuid4().hex
        self.grant = None
        self.last_ended = reason
        self.finish_pending(False, reason)
        self.changed()

    def prepare_update(self):
        self.refresh()
        if self.updating or self.grant or self.pending:
            raise ValueError("Stop access and finish approval before updating")
        self.updating = True
        self.stop("update_in_progress")

    def record(self, result):
        self.activity.append({"at": datetime.now(timezone.utc).isoformat(),
                              "operation": result.get("operation", ""),
                              "accepted": result.get("accepted", False),
                              "errorCode": result.get("errorCode")})

    def state(self):
        self.refresh()
        grant = None
        if self.grant:
            grant = {**self.grant, "scopes": sorted(self.grant["scopes"]),
                     "remainingSeconds": max(0, math.ceil(self.grant["expires"] - self.clock()))}
            del grant["expires"]
        pending = None
        if self.pending:
            pending = {k: self.pending[k] for k in ["id", "reason", "caller", "duration"]}
            pending["scopes"] = sorted(self.pending["scopes"])
        return {"generation": self.generation,
                "deployment": {"policy": {"preset": "workstation", "grantMode": "approval"},
                               "grant": grant, "pendingRequest": pending},
                "pending": pending, "activity": list(reversed(self.activity)),
                "lastEnded": self.last_ended}

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
    def __init__(self, changed=lambda: None, clock=time.monotonic, journal=None):
        self.journal = journal
        self.clock = clock
        self.changed = changed
        self.generation = uuid.uuid4().hex
        self.grant = self.pending = self.armed = None
        self.updating = False
        self.ready = False
        self.paused = False
        self.notice_ready = True
        self.browser_while_locked = False
        self.locked = False
        self.session = None
        self.last_ended = None
        self.activity = deque(maxlen=100)

    def refresh(self):
        if self.grant and self.grant["expires"] is not None and self.clock() >= self.grant["expires"]:
            self.stop("expired")
        if self.pending and self.clock() >= self.pending["expires"]:
            self.finish_pending(False, "approval_timeout")

    @property
    def browser_only_while_locked(self):
        return (not self.ready and self.locked and self.browser_while_locked and self.grant is not None
                and self.session is not None and self.grant.get("session") == self.session
                and bool(self.grant["scopes"] & {"browser", "devtools"}))

    def configure_browser_while_locked(self, enabled, loading=False):
        if type(enabled) is not bool or (enabled and not loading and (not self.ready or self.session is None)):
            raise ValueError("Enable browser access on the current unlocked console")
        self.browser_while_locked = enabled
        if not enabled and self.locked and self.grant:
            self.stop("browser_locked_access_disabled")
        self.changed()

    def set_ready(self, value, locked=False, session=None):
        changed = self.ready != value
        lost = self.ready and not value
        self.ready = value
        self.locked, self.session = locked, session
        if self.browser_while_locked and self.grant and (session is None or self.grant.get("session") != session):
            self.stop("console_session_changed")
        elif (lost or self.grant and not value) and not self.browser_only_while_locked:
            self.stop("desktop_unavailable")
        elif changed:
            self.generation = uuid.uuid4().hex
            self.changed()

    def authorize(self, operation, expected=None):
        self.refresh()
        if self.journal and not self.journal.health["available"]:
            return "audit_storage_unavailable"
        if expected is not None and expected != self.generation:
            return "stale_generation"
        scope = scope_for(operation)
        if not scope:
            return "unsupported_operation"
        if not self.ready and not (self.browser_only_while_locked and scope in {"browser", "devtools"}):
            return "desktop_locked_browser_only" if self.browser_only_while_locked else "desktop_unavailable"
        if self.updating:
            return "update_in_progress"
        if self.paused:
            return "access_paused"
        if self.pending and (scope in {"control", "devtools"} or
                             scope == "browser" and operation not in BROWSER_READ):
            return "approval_prompt_visible"
        if self.grant and not self.notice_ready:
            return "safety_notice_pending"
        allowed = self.grant["scopes"] if self.grant else set()
        if scope not in allowed and not (scope == "browser" and "devtools" in allowed):
            return "approval_required"
        return None

    def issue(self, selected, seconds, reason, caller, origin="request"):
        if self.journal and not self.journal.event("access.enabled"):
            raise ValueError("Audit storage unavailable")
        self.generation = uuid.uuid4().hex
        # Person-armed access an approved agent request replaces returns when
        # that request grant expires or its caller revokes it.
        if origin == "person":
            self.armed = None
        elif self.grant and self.grant.get("origin") == "person":
            self.armed = self.grant
        self.grant = {"scopes": selected, "expires": self.clock() + seconds if seconds is not None else None,
                      "grantId": uuid.uuid4().hex, "session": self.session,
                      "lifetime": "timed" if seconds is not None else "until_stopped",
                      "reason": reason, "requester": caller, "origin": origin}
        self.last_ended = None
        self.paused = False
        self.changed()

    def arm(self, selected, seconds, lifetime="timed"):
        self.refresh()
        if not self.ready or self.updating or self.pending:
            raise ValueError("Finish approval and use an unlocked desktop")
        if lifetime not in ("timed", "until_stopped"):
            raise ValueError("Choose a supported access lifetime")
        self.issue(scopes(selected), duration(seconds) if lifetime == "timed" else None,
                   "Enabled by the person", "local operator", "person")

    def request(self, request, caller, complete):
        self.refresh()
        selected = scopes(request.get("scopes"))
        seconds = duration(request.get("durationSeconds", 900))
        timeout = duration(request.get("timeoutSeconds", 120), 600, 5)
        reason = request.get("reason")
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 240:
            raise ValueError("Choose a reason (1-240 characters)")
        if self.updating:
            complete(False, "update_in_progress")
            return
        if self.pending:
            complete(False, "approval_pending")
            return
        if self.grant and selected <= self.grant["scopes"] and (self.ready or
                self.browser_only_while_locked and selected <= {"browser", "devtools"}):
            complete(True, None)
            return
        if not self.ready:
            complete(False, "approval_unavailable_while_locked" if self.locked else "desktop_unavailable")
            return
        if self.journal and not self.journal.event("access.requested"):
            complete(False, "audit_storage_unavailable")
            return
        self.pending = {"id": uuid.uuid4().hex, "requestId": request.get("requestId"), "scopes": selected, "duration": seconds,
                        "reason": reason.strip(), "caller": caller,
                        "expires": self.clock() + timeout, "complete": complete}
        self.changed()

    def finish_pending(self, accepted, error=None):
        pending, self.pending = self.pending, None
        if pending:
            if self.journal:
                self.journal.event("access.approved" if accepted else "access." + (error or "denied"), accepted)
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
        if self.journal:
            self.journal.event("access." + reason)
        ending, armed = self.grant, self.armed
        self.generation = uuid.uuid4().hex
        self.grant = None
        self.armed = None
        self.last_ended = reason
        # Only an agent grant's own end returns the person's access; the
        # person's Stop, desktop loss and updates clear it too.
        if (ending and ending.get("origin") == "request" and reason in {"expired", "revoked_by_caller"}
                and armed and (armed["expires"] is None or armed["expires"] > self.clock())):
            self.grant = armed
            self.last_ended = None
            if self.journal:
                self.journal.event("access.restored")
        self.finish_pending(False, reason)
        self.changed()

    def revoke_from_caller(self):
        """End only agent-requested access; person-armed access is retained."""
        self.refresh()
        if not self.grant:
            return False, False
        if self.grant.get("origin") == "person":
            if self.journal:
                self.journal.event("access.revoke_retained")
            return False, True
        self.stop("revoked_by_caller")
        return True, False

    def pause(self, value):
        if not self.grant or self.pending or not (self.ready or self.browser_only_while_locked) or self.updating:
            raise ValueError("Active access and an available desktop required")
        self.paused = value
        self.generation = uuid.uuid4().hex
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
                     "remainingSeconds": max(0, math.ceil(self.grant["expires"] - self.clock()))
                     if self.grant["expires"] is not None else None}
            del grant["expires"]
            del grant["session"]
        pending = None
        if self.pending:
            pending = {k: self.pending[k] for k in ["id", "reason", "caller", "duration"]}
            pending["scopes"] = sorted(self.pending["scopes"])
        return {"generation": self.generation, "manualUntilStoppedSupported": True,
                "deployment": {"policy": {"preset": "workstation", "grantMode": "approval"},
                               "grant": grant, "pendingRequest": pending,
                               "browserOnlyWhileLocked": self.browser_only_while_locked,
                               "effectiveScopes": sorted(scope for scope in self.grant["scopes"]
                                   if self.ready or self.browser_only_while_locked and scope in {"browser", "devtools"}) if self.grant else []},
                "browserWhileLocked": {"supported": True, "enabled": self.browser_while_locked,
                                       "active": self.browser_only_while_locked,
                                       "requiresUnlockedApproval": True, "route": "chrome.extension/cdp"},
                "paused": self.paused, "pending": pending, "activity": list(reversed(self.activity)),
                "lastEnded": self.last_ended, "logging": self.journal.health if self.journal else None}

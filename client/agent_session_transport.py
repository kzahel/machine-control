"""Retained session transport using the existing claim/admission/audit owners."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from typing import Callable, Protocol, cast

import audit_history
from claim_session import ClaimSession
from control_session import ControlSession
import machine_control as mc
from agent_session import JSON, SessionError, Stopped, ClaimLost, refusal


class ClaimOwner(Protocol):
    def wait(self) -> JSON: ...
    def bound_target(self) -> JSON: ...
    def renew(self, duration: int | None = None) -> JSON: ...
    def close(self) -> None: ...


class ControlOwner(Protocol):
    def wait(self) -> JSON: ...
    def call(self, request: JSON) -> JSON: ...
    def close(self) -> None: ...


class Audit(Protocol):
    def observe(self, result: JSON) -> None: ...
    def finish(self, exit_code: int | None = None, error_code: str | None = None) -> object: ...


class RetainedTransport:
    """One exact target, one live claim and one admitted owner; never replay.

    The owner has a bounded 15-minute admission. Claim renewal preserves only
    the target lease, not operator approval. An expired/revoked owner requires
    an explicitly new session, rather than silently requesting fresh access.
    """
    def __init__(self, alias: str, target: JSON, *, reason: str,
                 claimant_authority: str, claimant_id: str,
                 session_id: str | None = None,
                 claim_factory: Callable[..., ClaimOwner] = cast(Callable[..., ClaimOwner], ClaimSession),
                 control_factory: Callable[..., ControlOwner] = cast(Callable[..., ControlOwner], ControlSession),
                 audit_factory: Callable[..., Audit] = cast(Callable[..., Audit], audit_history.Command)) -> None:
        self.alias, self.target = alias, target
        self.session_id = session_id
        self.audit_factory = audit_factory
        self.claim: ClaimOwner | None = None
        self.owner: ControlOwner | None = None
        self.failure: SessionError | None = None
        self.stopped = threading.Event()
        self.lock = threading.RLock()
        self.renewal: threading.Thread | None = None
        self.owner_deadline = time.monotonic() + 900
        try:
            def inspect() -> JSON:
                value, _ = mc.doctor(alias, target)
                # Identity readiness is mandatory; admission may still await approval.
                if not value.get("ready"):
                    raise SessionError("target_not_ready", "Repair target doctor findings before starting a session")
                return value
            self._audit(["target", "doctor"], inspect)

            def acquire() -> JSON:
                self.claim = claim_factory(target, reason=reason, claimant_authority=claimant_authority,
                    claimant_id=claimant_id, session_id=session_id, duration=900, wait=300)
                self.claim.wait()
                self.target = self.claim.bound_target()
                return {"accepted": True, "operation": "acquire",
                        "data": {"claim": {"claimId": self.target["_claimId"]}}}
            self._audit(["claim", "acquire"], acquire)

            def admit() -> JSON:
                self.owner = control_factory(self.target, reason=reason, scopes=("observe", "control"),
                                             duration=900, wait=300)
                return self.owner.wait()
            self._audit(["control", "open"], admit)
            self.owner_deadline = time.monotonic() + 900
            self.renewal = threading.Thread(target=self._renew, name="mc-agent-claim-renewal", daemon=True)
            self.renewal.start()
        except BaseException:
            self.close()
            raise

    def _audit(self, words: list[str], operation: Callable[[], JSON]) -> JSON:
        try:
            command = self.audit_factory(self.alias, self.target["platform"], words, self.target.get("_claimId"),
                                         session_id=self.session_id)
        except (audit_history.AuditError, OSError, sqlite3.Error) as error:
            raise SessionError("audit_unavailable", "Could not persist audit intent; nothing dispatched") from error
        value: JSON | None = None
        try:
            value = operation()
            command.observe(value)
        except BaseException as error:
            command.finish(1, getattr(error, "code", "session_aborted"))
            raise
        if command.finish(0 if value.get("accepted", True) else 1) is None:
            self.failure = SessionError("audit_result_unavailable", "Operation may have completed; session stopped",
                                        delivered="unknown", result=value)
            raise self.failure
        return value

    def _renew(self) -> None:
        next_renewal = time.monotonic() + 60
        while not self.stopped.wait(1):
            try:
                with self.lock:
                    if time.monotonic() >= self.owner_deadline:
                        self.failure = Stopped("admission_expired", "Bounded admission ended; start a new session")
                        self.close()
                        return
                    if time.monotonic() < next_renewal:
                        continue
                    if self.claim is None:
                        return
                    duration = max(60, min(900, int(self.owner_deadline - time.monotonic())))
                    self._audit(["claim", "renew"], lambda: self.claim.renew(duration) if self.claim else {})
                    next_renewal = time.monotonic() + 60
            except Exception as error:
                self.failure = ClaimLost("claim_renewal_failed", "Claim renewal failed; start a new session", result={"reason": type(error).__name__})
                self.close()
                return

    def call(self, request: JSON) -> JSON:
        with self.lock:
            if self.failure:
                raise self.failure
            if self.stopped.is_set() or self.owner is None:
                raise Stopped("session_closed", "Start a new session")
            translated = mc.translate_request(self.target["platform"], request)
            # Mac's one-shot socket entry normalizes chords, but nested control
            # dispatch reaches the native provider directly. Preserve literal +.
            if self.target["platform"] == "macos" and translated.get("operation") == "input.key":
                chord = translated.get("key")
                if isinstance(chord, str) and len(chord) > 1 and "+" in chord:
                    parts = chord.split("+")
                    if parts[-1] == "":
                        parts.pop()
                        parts[-1] += "+"
                    translated["key"] = "-".join(parts)
            operation = str(request.get("operation", "unknown"))
            try:
                # ControlSession rechecks the live claim and owner generation per
                # operation. Its adapter channel also checks the exact resource.
                return self._audit(["desktop", *operation.split(".")],
                    lambda: mc.validate_resident(self.owner.call(translated), self.target["platform"]) if self.owner else {})
            except mc.ClientError as error:
                self.close()
                raise refusal({"accepted": False, "errorCode": error.code,
                               "message": str(error), "delivery": "unknown"}) from error
            except SessionError:
                self.close()
                raise

    def image(self, result: JSON) -> bytes:
        with self.lock:
            if self.failure or self.stopped.is_set():
                raise self.failure or Stopped("session_closed", "Start a new session")
            data = result.get("data", {})
            handle = data.get("artifactPath") or data.get("artifactId")
            if not isinstance(handle, str) or not handle:
                raise SessionError("capture_artifact_missing", "Capture returned no supported artifact handle")
            image = b""
            def fetch() -> JSON:
                nonlocal image
                mc.require_selected_claim(self.target)
                with tempfile.TemporaryDirectory(prefix="mc-session-capture-") as directory:
                    path = Path(directory) / "capture.png"
                    command = "artifact-fetch" if self.target["platform"] == "macos" else "artifact"
                    mc.run_adapter(self.target, [command, handle, str(path)])
                    if path.stat().st_size > 8 * 1024 * 1024:
                        raise SessionError("capture_too_large", "Inline capture exceeds 8 MiB")
                    image = path.read_bytes()
                    if not image.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise SessionError("invalid_capture", "Capture is not a PNG")
                return {"accepted": True, "operation": "artifact"}
            self._audit(["desktop", "artifact"], fetch)
            return image

    def close(self) -> None:
        with self.lock:
            if self.stopped.is_set():
                return
            self.stopped.set()
            # Cleanup cannot depend on healthy audit storage. Each live channel's
            # EOF is authoritative ownership release, including after a timeout.
            try:
                if self.owner:
                    self.owner.close()
            finally:
                if self.claim:
                    self.claim.close()
                self.owner = None
                self.claim = None
            cast(Callable[..., object], audit_history.best_effort)(
                "session.closed", logicalTarget=self.alias, claimId=self.target.get("_claimId"),
                sessionRef=cast(Callable[..., JSON | None], audit_history.session_ref)(self.session_id))


def connect(alias: str, *, reason: str, registry: str | None = None,
            claimant_authority: str | None = None, claimant_id: str | None = None) -> RetainedTransport:
    targets, _ = mc.load_registry(registry)
    alias, target = mc.select_target(targets, alias)
    target = {**target, "environment": {**target.get("environment", {}),
              "MACHINE_CONTROL_CLAIM_POLICY": target.get("claimPolicy", "required"),
              "MACHINE_CONTROL_AUDIT_TARGET": alias}}
    reference = cast(Callable[[], JSON | None], audit_history.session_ref)()
    if claimant_authority is None and claimant_id is None and reference:
        claimant_authority = mc.CLAIMANT_AUTHORITIES[reference["source"]]
        claimant_id = str(reference["id"])
    if not claimant_authority or not claimant_id:
        raise SessionError("claimant_required", "Supply a truthful claimant authority and ID outside an agent host")
    return RetainedTransport(alias, target, reason=reason,
                             claimant_authority=claimant_authority, claimant_id=claimant_id,
                             session_id=str(reference['id']) if reference else None)

"""Live, cancellable queued target claims for the cooperative v1 profile."""
import os
import math
import threading
import time

import machine_control as mc
from control_session import ControlSession

SCHEMA = "machine-control-claim-admission/v1"
CHANNEL_SCHEMA = "machine-control-claim-channel/v1"


def validate_capabilities(value):
    if not isinstance(value, dict) or value.get("schema") != "machine-control-claim-capabilities/v1" \
            or value.get("queueing") is not True or value.get("queue") != {
                "transport": "live_adapter_channel", "ownership": "connection", "assurance": "self_asserted",
                "maximumEntries": 256, "waitingHeartbeatSeconds": 60, "offerSeconds": 15,
                "activeHeartbeatSeconds": 5, "maximumWaitSeconds": 14400}:
        raise mc.ClientError("invalid_claim_capabilities", "Compatible live claim queue v1 is required")
    legacy = {k:v for k,v in value.items() if k != "queue"}
    legacy.update(schema="machine-control-claim-capabilities/v0", queueing=False)
    mc.validate_claim_capabilities(legacy)
    return value


def validate_view(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA \
            or value.get("state") not in {"waiting_for_resource", "offered", "active", "ended"} \
            or value.get("assurance") != "self_asserted" \
            or any(type(value.get(key)) is not int or value[key] < 0 for key in ("revision", "offerGeneration")):
        raise mc.ClientError("invalid_claim_admission", "Invalid queued claim state")
    if any(type(value.get(key)) not in (int, float) or not math.isfinite(value[key]) or value[key] < 0
           for key in ("waitRemainingSeconds", "heartbeatRemainingSeconds", "offerRemainingSeconds")) \
            or value.get("terminalReason") is not None and not isinstance(value["terminalReason"], str):
        raise mc.ClientError("invalid_claim_admission", "Invalid queued claim deadlines")
    if value["state"] == "active":
        mc.validate_claim_result({"schema": "machine-control-claim/v0", "operation": "acquire",
            "accepted": True, "uncertainty": "none", "data": {"state": "held", "claim": value.get("claim")}}, "acquire")
    return value


class ClaimSession(ControlSession):
    """A claim lasts only while this context is live and its lease remains valid.

    Heartbeats retain queue/session liveness, never extend the claim's authority
    deadline. Call renew explicitly for long work, subject to the existing
    maximum continuous lifetime. bound_target supplies the existing adapter's
    exact claim selector for ordinary operations and resident ControlSession.
    """
    def __init__(self, target, *, reason, claimant_authority, claimant_id,
                 wait=300, duration=None, disruptive=False, metadata=None,
                 session_id=None, label=None):
        if target.get("_claimId") is not None or target.get("claimPolicy") == "unsupported" \
                or target.get("environment", {}).get("MACHINE_CONTROL_CLAIM_ID") or os.environ.get("MACHINE_CONTROL_CLAIM_ID"):
            raise mc.ClientError("claim_selection_conflict", "Queued acquisition requires an unclaimed supported target")
        if type(wait) is not int or not 1 <= wait <= 14400 \
                or duration is not None and (type(duration) is not int or duration <= 0) \
                or type(disruptive) is not bool:
            raise mc.ClientError("invalid_claim_request", "Invalid queued claim timings")
        self._start_transport(target, "claim-channel", CHANNEL_SCHEMA, "claim.cancel")
        self.sequenced = True
        self.deadline = time.monotonic() + wait
        try:
            self.view = validate_view(self._rpc(dict(operation="claim.open", schema=SCHEMA,
                reason=reason, claimantAuthority=claimant_authority, claimantId=claimant_id,
                waitSeconds=wait, durationSeconds=duration, useClass="disruptive" if disruptive else "ordinary",
                metadata={} if metadata is None else metadata, sessionId=session_id, label=label), timeout=10))
        except BaseException:
            self.close(cancel=False)
            raise
        threading.Thread(target=self._keepalive, daemon=True).start()

    def _keepalive(self):
        while not self.stopped.wait(1):
            try:
                if os.getppid() != self.parent:
                    raise mc.ClientError("owner_disconnected", "Claim owner exited")
                self.view = validate_view(self._rpc({"operation": "claim.heartbeat"}))
            except mc.ClientError as error:
                self._fail(error)
                self.close(cancel=False)
                return

    def status(self):
        self.view = validate_view(self._rpc({"operation": "claim.status"}))
        return self.view

    def wait(self, *, cancelled=None):
        while True:
            if cancelled is not None and cancelled():
                self.cancel()
                raise mc.ClientError("cancelled", "Queued claim cancelled")
            view = self.status()
            if view["state"] == "active":
                return view
            if view["state"] == "ended":
                raise mc.ClientError(view.get("terminalReason") or "claim_ended", "Queued claim ended")
            if view["state"] == "offered":
                try:
                    self.view = validate_view(self._rpc({"operation": "claim.accept",
                                                        "offerGeneration": view["offerGeneration"]}))
                    return self.view
                except mc.ClientError as error:
                    if error.code != "stale_claim_offer":
                        raise
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise mc.ClientError("wait_deadline_exceeded", "Claim wait deadline exceeded")
            self.stopped.wait(min(.25, remaining))

    def bound_target(self):
        view = self.status()
        if view["state"] != "active":
            raise mc.ClientError("claim_not_held", "Queued claim is not active")
        identifier = view["claim"]["claimId"]
        return {**self.target, "_claimId": identifier, "environment": {
            **self.target.get("environment", {}), "MACHINE_CONTROL_CLAIM_ID": identifier}}

    def renew(self, duration=None):
        target = self.bound_target()
        arguments = ["claim-renew", "--claim-id", target["_claimId"], "--json"]
        if duration is not None:
            if type(duration) is not int or duration <= 0:
                raise mc.ClientError("invalid_claim_request", "Claim renewal duration is invalid")
            arguments += ["--duration-seconds", str(duration)]
        result, _ = mc._claim_adapter_call(target, arguments)
        value = mc.validate_claim_result(result, "renew")
        if not value["accepted"]:
            raise mc.ClientError(value.get("errorCode") or "claim_renewal_refused", "Claim renewal refused")
        return value

    def cancel(self):
        return validate_view(self._rpc({"operation": "claim.cancel"}))

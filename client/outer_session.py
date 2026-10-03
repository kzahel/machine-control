"""Controller-local outer recovery borrowing one existing disruptive VM claim."""
import threading
import time

import machine_control as mc
from control_session import ControlSession, validate_view, SCHEMA, CHANNEL_SCHEMA


class OuterSession(ControlSession):
    """Reserve the native host desktop without acquiring another VM lease.

    binding is privately derived by the authoritative VM adapter. IDs and this
    same-user channel remain coordination, not authenticated caller isolation.
    Every native effect rechecks its VM lease under the claim-store operation
    lock and the native desktop ownership fence. No action is replayed.
    """
    def __init__(self, host, binding, *, reason, wait=300, duration=300):
        if not reason or len(reason) > 240 or type(wait) is not int or not 1 <= wait <= 14400 \
                or type(duration) is not int or not 1 <= duration <= 900:
            raise mc.ClientError("invalid_admission_request", "Invalid outer admission timings")
        self._start_transport(host, "channel", CHANNEL_SCHEMA, "control.cancel")
        try:
            self.view = validate_view(self._rpc(dict(operation="control.open", schema=SCHEMA,
                scopes=["observe", "control"], reason=reason, waitSeconds=wait,
                durationSeconds=duration, outerRecovery=binding), timeout=10))
            if self.view.get("outerRecovery") != "borrowed_exact_claim/v1":
                raise mc.ClientError("outer_admission_unsupported", "Native borrowed-claim admission is required")
            self.sequenced = self.view.get("requestSequencing") == "strict"
        except BaseException:
            self.close(cancel=False)
            raise
        self.deadline = time.monotonic() + wait
        self.heartbeat = threading.Thread(target=self._keepalive, daemon=True)
        self.heartbeat.start()
        self.reference = None

    def prepare(self):
        self.wait()
        result = self.call({"operation": "outer.prepare"})
        if not result.get("accepted"):
            raise mc.ClientError(result.get("errorCode") or "outer_prepare_refused", "Outer geometry discovery refused")
        self.reference = result["data"]["reference"]
        return result["data"]

    def begin(self):
        if self.reference is None:
            raise mc.ClientError("outer_reference_required", "Discover current exact geometry first")
        result = self.call({"operation": "outer.begin", "reference": self.reference})
        if not result.get("accepted"):
            raise mc.ClientError(result.get("errorCode") or "outer_focus_refused", "Outer focus refused")
        # A focus request is asynchronous at the OS boundary. No claim lock is
        # held during this delay; the next native primitive rechecks everything.
        self.stopped.wait(.2)
        return result

    def step(self, kind, **fields):
        if kind not in {"key", "click", "dragStart", "dragMove", "dragEnd"} or self.reference is None:
            raise mc.ClientError("invalid_outer_input", "Invalid outer input primitive")
        result = self.call(dict(operation="outer.step", reference=self.reference, kind=kind, **fields))
        if not result.get("accepted"):
            raise mc.ClientError(result.get("errorCode") or "outer_input_refused",
                                 "Outer input refused; any possible effect was not replayed")
        return result

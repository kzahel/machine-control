"""Cancellable owner-bound admission over an adapter's live byte channel.

The transport process belongs to this context. It never restores sessions,
replays actions, or carries owner authority in a public ID or environment value.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import threading
import time
import uuid

import machine_control as mc

SCHEMA = "machine-control-admission/v1"
CHANNEL_SCHEMA = "machine-control-admission-channel/v1"


def validate_view(value):
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise mc.ClientError("invalid_admission_status", "Invalid admission status")
    states = {"waiting_for_approval", "waiting_for_resource", "paused", "announcing", "offered", "active", "ended"}
    if value.get("state") not in states or not isinstance(value.get("intentId"), str) \
            or not value["intentId"] or not isinstance(value.get("blockingReasons"), list) \
            or any(not isinstance(reason, str) for reason in value["blockingReasons"]):
        raise mc.ClientError("invalid_admission_status", "Invalid admission state")
    for key in ("revision", "offerGeneration"):
        if type(value.get(key)) is not int or value[key] < 0:
            raise mc.ClientError("invalid_admission_status", "Invalid admission generation")
    generations = value.get("resourceGenerations")
    if not isinstance(generations, dict) or any(not isinstance(key, str) or type(number) is not int or number < 0 for key, number in generations.items()):
        raise mc.ClientError("invalid_admission_status", "Invalid resource generations")
    if value["state"] == "active" and (not isinstance(value.get("sessionId"), str) or not value["sessionId"] or not generations):
        raise mc.ClientError("invalid_admission_status", "Active admission has no fence")
    if value.get("requestSequencing") not in (None, "strict"):
        raise mc.ClientError("admission_unsupported", "Unsupported admission request ordering")
    return value


class ControlSession:
    def __init__(self, target, *, reason, scopes=("observe", "control"), wait=300, duration=300, prepared_console=False):
        if type(prepared_console) is not bool:
            raise mc.ClientError("invalid_admission_request", "Invalid prepared console option")
        if not reason or len(reason) > 240 or type(wait) is not int or not 1 <= wait <= 14400 \
                or type(duration) is not int or not 1 <= duration <= 900 \
                or not scopes or len(set(scopes)) != len(scopes) \
                or any(scope not in {"observe", "control", "browser", "devtools"} for scope in scopes):
            raise mc.ClientError("invalid_admission_request", "Invalid control admission options")
        if prepared_console and set(scopes) != {"observe", "control"}:
            raise mc.ClientError("invalid_admission_request", "Prepared console requires observation and control scopes")
        mc.require_selected_claim(target)
        self._start_transport(target, "channel", CHANNEL_SCHEMA, "control.cancel")
        try:
            request = dict(operation="control.open", schema=SCHEMA, reason=reason, scopes=list(scopes),
                           waitSeconds=wait, durationSeconds=duration)
            if prepared_console:
                request["preparedConsole"] = True
            if target.get("_claimId"):
                request["claimId"] = target["_claimId"]
            self.view = validate_view(self._rpc(request, timeout=10))
            self.sequenced = self.view.get("requestSequencing") == "strict"
        except BaseException:
            self.close(cancel=False)
            raise
        self.deadline = time.monotonic() + wait
        self.heartbeat = threading.Thread(target=self._keepalive, daemon=True)
        self.heartbeat.start()

    def _start_transport(self, target, operation, response_schema, cancel_operation):
        """Shared bounded byte transport; subclasses retain their own authority."""
        self.target = {**target}
        self.response_schema = response_schema
        self.cancel_operation = cancel_operation
        self.sequenced = False
        self.request_sequence = 0
        command = mc.resolved_adapter_command(target)
        if command is None:
            raise mc.ClientError("adapter_unavailable", "Control adapter unavailable")
        try:
            self.process = subprocess.Popen([*command, operation], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env={**os.environ, **target.get("environment", {})})
        except OSError:
            raise mc.ClientError("control_transport_unavailable", "Control transport unavailable")
        self.pending = {}
        self.lock = threading.Lock()
        self.writes = threading.Lock()
        self.stopped = threading.Event()
        self.failure = None
        self.view = None
        self.parent = os.getppid()
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _fail(self, error):
        with self.lock:
            if self.failure is None:
                self.failure = error
            entries = list(self.pending.values())
            self.pending.clear()
        for entry in entries:
            entry.put(error)

    def _read(self):
        try:
            while not self.stopped.is_set():
                line = self.process.stdout.readline(4 * 1024 * 1024 + 1)
                if not line or not line.endswith(b"\n") or len(line) > 4 * 1024 * 1024:
                    raise mc.ClientError("control_transport_closed", "Control transport closed or exceeded its frame limit")
                value = json.loads(line)
                if not isinstance(value, dict) or value.get("schema") != self.response_schema \
                        or type(value.get("accepted")) is not bool or not isinstance(value.get("requestId"), str):
                    raise mc.ClientError("admission_unsupported", "This route does not expose a compatible admission channel")
                with self.lock:
                    entry = self.pending.pop(value["requestId"], None)
                if entry is None:
                    raise mc.ClientError("invalid_control_response", "Unexpected control response")
                entry.put(value)
        except (OSError, ValueError, mc.ClientError) as error:
            self._fail(error if isinstance(error, mc.ClientError) else mc.ClientError("invalid_control_response", "Invalid control response"))

    def _rpc(self, request, *, timeout=5):
        identifier = uuid.uuid4().hex
        response = queue.Queue(maxsize=1)
        with self.lock:
            if self.failure:
                raise self.failure
            if self.stopped.is_set():
                raise mc.ClientError("control_session_closed", "Control session is closed")
            self.pending[identifier] = response
        value = dict(request, requestId=identifier)
        try:
            with self.writes:
                if self.sequenced:
                    value["requestSequence"] = self.request_sequence + 1
                encoded = json.dumps(value, separators=(",", ":")).encode() + b"\n"
                if len(encoded) > 65536:
                    with self.lock:
                        self.pending.pop(identifier, None)
                    raise mc.ClientError("invalid_control_request", "Control request exceeds 64 KiB")
                if self.sequenced:
                    self.request_sequence += 1
                self.process.stdin.write(encoded)
                self.process.stdin.flush()
            reply = response.get(timeout=timeout)
        except (OSError, ValueError, queue.Empty):
            error = mc.ClientError("control_transport_timeout", "Control response unavailable; action was not replayed")
            self._fail(error)
            raise error
        if isinstance(reply, BaseException):
            raise reply
        if reply["accepted"] is not True:
            raise mc.ClientError(reply.get("errorCode") or "control_refused", "Control request refused")
        return reply.get("data")

    def _keepalive(self):
        while not self.stopped.wait(1):
            if os.getppid() != self.parent:
                self._fail(mc.ClientError("owner_disconnected", "Control owner exited"))
                self.close(cancel=False)
                return
            try:
                mc.require_selected_claim(self.target)
                self.view = validate_view(self._rpc({"operation": "control.heartbeat"}))
            except mc.ClientError as error:
                self._fail(error)
                self.close(cancel=False)
                return

    def status(self):
        self.view = validate_view(self._rpc({"operation": "control.status"}))
        return self.view

    def wait(self):
        """Accept only a currently offered activation; never replay old work."""
        while True:
            view = self.status()
            if view["state"] == "ended":
                raise mc.ClientError(view.get("terminalReason") or "control_ended", "Control intent ended")
            if view["state"] == "active":
                return view
            if view["state"] == "offered":
                mc.require_selected_claim(self.target)
                try:
                    self.view = validate_view(self._rpc({"operation":"control.accept", "offerGeneration":view["offerGeneration"]}))
                    return self.view
                except mc.ClientError as error:
                    if error.code not in {"stale_activation_offer", "admission_changed"}:
                        raise
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise mc.ClientError("wait_deadline_exceeded", "Control wait deadline exceeded")
            self.stopped.wait(min(0.25, remaining))

    def call(self, request):
        """Dispatch once with the current owner and resource fence."""
        mc.require_selected_claim(self.target)
        view = self.status()
        if view["state"] != "active":
            raise mc.ClientError("control_interrupted", "Control is paused or ended; wait for a fresh session before issuing new work", view)
        result = self._rpc({"operation":"control.dispatch", "sessionId":view["sessionId"],
                           "resourceGenerations":view["resourceGenerations"], "request":request}, timeout=60)
        if not isinstance(result, dict) or type(result.get("accepted")) is not bool:
            raise mc.ClientError("invalid_control_response", "Invalid controlled operation result")
        return result

    def cancel(self):
        return validate_view(self._rpc({"operation":"control.cancel"}))

    def close(self, *, cancel=True):
        if self.stopped.is_set():
            return
        if cancel and self.view is not None and self.failure is None:
            try:
                self._rpc({"operation":self.cancel_operation}, timeout=1)
            except mc.ClientError:
                pass
        self.stopped.set()
        self._fail(mc.ClientError("control_session_closed", "Control session closed"))
        # Closing stdin releases the live adapter connection; bounded reaping
        # prevents an abandoned local proxy from extending ownership.
        try:
            self.process.stdin.close()
        except OSError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
        self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.close()


def handle_control(alias, target, arguments):
    if arguments == ["status"]:
        return mc.send_resident_request(alias, target, {"operation":"status"})
    parser = argparse.ArgumentParser(prog="machine-control control call")
    parser.add_argument("command", choices=["call"])
    parser.add_argument("json")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--scope", action="append", choices=["observe", "control", "browser", "devtools"])
    parser.add_argument("--wait", default="5m")
    parser.add_argument("--duration", default="5m")
    parser.add_argument("--prepared-console", action="store_true")
    options = parser.parse_args(arguments)
    try:
        request = json.loads(options.json)
        if not isinstance(request, dict) or not isinstance(request.get("operation"), str):
            raise mc.ClientError("invalid_control_request", "Control action must be an object with an operation")
        translated = mc.translate_request(target["platform"], request)
        scopes = options.scope or ["observe", "control"]
        with ControlSession(target, reason=options.reason, scopes=scopes,
                wait=mc.parse_duration_seconds(options.wait), duration=mc.parse_duration_seconds(options.duration),
                prepared_console=options.prepared_console) as session:
            session.wait()
            value = session.call(translated)
            mc.emit(value)
            return 0 if value["accepted"] else 1
    except KeyboardInterrupt:
        raise mc.ClientError("cancelled", "Control request cancelled", exit_code=130)

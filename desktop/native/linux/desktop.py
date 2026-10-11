#!/usr/bin/env python3
"""Supervised ordinary-user Linux desktop companion and private operator pipe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import select
import socket
import stat
import struct
import subprocess
import sys
import threading
import time

# The resident has no operator window. Exporting its GTK invisible clipboard
# surface into the AT-SPI bus creates an in-process accessibility recursion.
# Visible approvals run in their own accessible process below.
os.environ["NO_AT_BRIDGE"] = "1"
os.environ.pop("GTK_MODULES", None)

import gi

from gi.repository import Gio, GLib

from grants import Grants, OBSERVE, CONTROL
from work import Work, Ticket, Cancelled
from presentation import Presentation, runtime_directory
from coordinator import Coordinator
from one_shot import read_reply
from journal import Journal
import uuid
from portal import Portal
from provider import Provider
from shortcut import Shortcut
from startup import Startup
from browser import Browser
from updates import Updates
import linuxui

FRAME_LIMIT = 65536


def read_frame(stream):
    line = stream.readline(FRAME_LIMIT + 1)
    if not line:
        return None
    if len(line) > FRAME_LIMIT or not line.endswith(b"\n"):
        raise ValueError("Frame exceeds 64 KiB")
    value = json.loads(line)
    if not isinstance(value, dict):
        raise ValueError("Object required")
    return value


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode() + b"\n"


class SocketFrames:
    def __init__(self, client):
        self.client = client
        self.buffer = bytearray()

    def readline(self, limit):
        while b"\n" not in self.buffer:
            if len(self.buffer) >= limit:
                raise ValueError("Frame too large")
            chunk = self.client.recv(min(65536, limit - len(self.buffer)))
            if not chunk:
                return b""
            self.buffer.extend(chunk)
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = rest
        if len(line) + 1 > limit:
            raise ValueError("Frame too large")
        return bytes(line) + b"\n"


class Desktop:
    def __init__(self, operator_pid, executable, instance="desktop", override=None):
        self.scheduler = Coordinator()
        self.loop = self.scheduler.loop
        self.operator_pid = operator_pid
        self.instance = instance
        self.executable = executable
        self.presentation = Presentation(instance, override)
        self.safety_available = False
        self.safety_condition = threading.Condition()
        self.safety_state = None
        self.journal = Journal()
        def pump():
            context = GLib.MainContext.default()
            # One bounded event batch keeps queued provider admission progressing.
            for _ in range(16):
                if not context.pending():
                    break
                context.iteration(False)
        self.work = Work(self.scheduler.post, linuxui.Atspi.init, pump)
        self.grants = Grants(self.changed, journal=self.journal)
        self.session_pending = False
        self.session_observed = 0.0
        self.updates = Updates()
        self.provider = Provider(self)
        self.last_portal_state = "off"
        self.portal = Portal(self.changed, self.scheduler)
        self.shortcut = Shortcut(executable)
        self.startup = Startup(executable)
        self.browser = Browser(self)
        self.browser.refresh_owned_installation()
        self.dialog = None
        self.dialog_id = None
        self.unlocked = False
        self.stopped = False
        self.directory = runtime_directory(instance)
        identity = Path(__file__).with_name("desktop-runtime.json")
        self.identity = json.loads(identity.read_text()) if identity.exists() else {}
        self.endpoint = self.directory / "desktop.sock"
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # A live socket is never unlinked; Tauri's single-instance gate owns normal launches.
        if self.endpoint.exists():
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as check:
                try:
                    check.connect(str(self.endpoint))
                except ConnectionRefusedError:
                    self.endpoint.unlink()
                else:
                    raise RuntimeError("Desktop resident is already running")
        self.socket.bind(str(self.endpoint))
        os.chmod(self.endpoint, 0o600)
        self.socket.listen(16)
        self.slots = threading.BoundedSemaphore(16)
        self.recovery = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.recovery_endpoint = self.directory / "operator.sock"
        self.recovery_endpoint.unlink(missing_ok=True)
        self.recovery.bind(str(self.recovery_endpoint))
        os.chmod(self.recovery_endpoint, 0o600)
        self.recovery.listen(4)
        self.recovery_slots = threading.BoundedSemaphore(4)
        threading.Thread(target=self.accept_recovery, daemon=True).start()
        self.start_safety()
        self.monitor()
        self.scheduler.timer(1000, self.monitor)

    def changed(self):
        if hasattr(self, "provider"):
            self.work.cancel()
        if hasattr(self, "portal"):
            previous, self.last_portal_state = self.last_portal_state, self.portal.state
            if previous == "ready" and self.portal.state != "ready":
                self.grants.stop("sharing_ended")
            self.grants.set_ready(self.unlocked and self.safety_available and self.portal.state != "pending")
        if hasattr(self, "dialog"):
            self.approval()
        if hasattr(self, "browser"):
            self.browser.sync()
        if hasattr(self, "safety"):
            self.grants.notice_ready = self.grants.grant is None
            with self.safety_condition:
                self.safety_state = {"generation": self.grants.generation, "grant": self.grants.state()["deployment"]["grant"],
                                     "paused": self.grants.paused}
                self.safety_condition.notify()

    def monitor(self):
        if time.monotonic() - self.session_observed > 2:
            self.unlocked = False
            self.grants.set_ready(False)
        if not self.session_pending:
            self.session_pending = True
            bus = self.portal.bus

            def observed(connection, result, _data):
                self.session_pending = False
                try:
                    locked = connection.call_finish(result).unpack()[0]
                    self.unlocked = not locked and os.environ.get("XDG_SESSION_TYPE") == "wayland" and (
                        "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", ""))
                    self.session_observed = time.monotonic()
                except GLib.Error:
                    self.unlocked = False
                self.grants.set_ready(self.unlocked and self.safety_available and self.portal.state != "pending")
                if not self.unlocked and self.portal.state != "off":
                    self.portal.close()
            bus.call("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
                     "org.gnome.ScreenSaver", "GetActive", None,
                     GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 500, None, observed, None)
        self.grants.refresh()
        self.approval()
        self.browser.sync()
        return not self.stopped

    def approval(self):
        pending = self.grants.pending
        identifier = pending["id"] if pending else None
        if identifier == self.dialog_id:
            return
        if self.dialog:
            self.dialog_cancelled.set()
            self.dialog.terminate()
            # Keep the one physical UI slot until its reader reaps the child.
            return
        self.dialog_id = identifier
        if not pending:
            return
        # GTK approval lives separately from the synchronous AT-SPI provider;
        # querying an in-process GTK accessible can deadlock its own main loop.
        environment = dict(os.environ)
        environment.pop("NO_AT_BRIDGE", None)
        process = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).with_name("approval.py"))],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=sys.stderr, env=environment)
        self.dialog = process
        self.dialog_cancelled = threading.Event()
        cancelled = self.dialog_cancelled
        value = {k: pending[k] for k in ["id", "reason", "caller", "duration"]}
        value["parentId"] = os.getpid()
        value["scopes"] = sorted(pending["scopes"])
        process.stdin.write(encode(value))
        process.stdin.close()

        def wait():
            line = read_reply(process, cancelled, pending["expires"])
            def decision():
                if self.dialog != process:
                    return False
                self.dialog = None
                self.dialog_id = None
                if self.grants.pending and self.grants.pending["id"] == identifier:
                    try:
                        reply = json.loads(line)
                        self.grants.decide(identifier, reply.get("allow") is True,
                                           reply.get("scopes"), reply.get("duration", 0))
                    except (ValueError, TypeError):
                        self.grants.finish_pending(False, "approval_unavailable")
                self.approval()
                return False
            self.scheduler.post(decision)
        threading.Thread(target=wait, daemon=True).start()

    def state(self):
        return {**self.grants.state(), "nativeApproval": True, "presentation": self.presentation.state(),
                "providerWork": {"busy": self.work.active is not None},
                "sessionObservation": {"ageSeconds": time.monotonic() - self.session_observed,
                                       "refreshing": self.session_pending},
                "safetyAvailable": self.safety_available, "safetyNoticeReady": self.grants.notice_ready, "platform": "linux", "supportedScopes": ["observe", "control", "browser", "devtools"],
                "permissions": {"accessibility": self.unlocked, "screenRecording": self.portal.ready},
                "portal": {"state": self.portal.state, "error": self.portal.error,
                           "pointer": bool(self.portal.devices & 2), "keyboard": bool(self.portal.devices & 1)},
                "browser": {"connected": self.browser.provider is not None, "available": True},
                "socket": str(self.endpoint), "startOnLogin": self.startup.enabled,
                "stopShortcutAvailable": self.shortcut.available,
                "stopShortcut": "Ctrl+Alt+Shift+."}

    def operator(self, command):
        method = command.get("method")
        expected = command.get("expectedGeneration")
        if expected is not None and expected != self.grants.generation:
            raise ValueError("Operator authority changed before dispatch")
        if method == "presentation.status":
            return {"ok": True, "presentation": self.presentation.state(), "runtimeId": os.getpid()}
        if method == "presentation":
            if self.grants.pending:
                raise ValueError("Finish pending approval before changing presentation")
            return {"ok": True, "presentation": self.presentation.set(command.get("profile")), "runtimeId": os.getpid()}
        if method == "update_sync":
            return {"ok": True, "checkRequested": self.updates.sync(command.get("state"))}
        if method == "state":
            return {"ok": True, "state": self.state()}
        if method == "logs.query":
            return {"ok": True, "history": self.journal.query(command.get("offset", 0), command.get("operation", ""), command.get("outcome", ""), command.get("stream", "audit"))}
        if method == "logs.debug":
            self.journal.debug(command.get("enabled") is True)
            return {"ok": True}
        if method == "logs.preview":
            return {"ok": True, "preview": self.journal.preview()}
        if method == "logs.export":
            return {"ok": True, "path": self.journal.export()}
        if method == "logs.location":
            return {"ok": True, "path": str(self.journal.root)}
        if method == "logs.diagnostic":
            self.journal.diagnostic("desktop.supervisor", command.get("code", "unknown"))
            return {"ok": True}
        if method == "arm":
            self.grants.arm(command.get("scopes"), command.get("duration", 900),
                            command.get("lifetime", "timed"))
        elif method == "decision":
            self.grants.decide(command.get("id"), command.get("allow") is True,
                               command.get("scopes"), command.get("duration", 0))
        elif method == "stop":
            self.grants.stop()
            if self.portal.state == "pending":
                self.portal.close()
        elif method in {"pause", "resume"}:
            self.grants.pause(method == "pause")
        elif method == "shortcut":
            self.shortcut.set(command.get("enabled"))
        elif method == "startup":
            self.startup.set(command.get("enabled"))
        elif method == "browser.setup":
            return {"ok": True, "extensionPath": self.browser.setup()}
        elif method == "permission":
            if not self.unlocked or self.grants.grant or self.grants.pending or self.grants.updating:
                raise ValueError("Stop access before changing sharing")
            self.portal.connect()
        elif method == "permission.disconnect":
            self.grants.stop()
            self.portal.close()
        elif method == "prepare_update":
            self.grants.prepare_update()
            self.portal.close()
        elif method == "cancel_update":
            self.grants.updating = False
        elif method == "quit":
            self.shutdown()
        else:
            raise ValueError("Unknown operator command")
        return {"ok": True}

    def handle(self, request, caller, complete, caller_pid=None):
        started = time.monotonic()
        request["requestId"] = request.get("requestId") or uuid.uuid4().hex
        operation = request.get("operation", "")
        result = self.provider.envelope(request, operation)

        def finish(value):
            value["generation"] = self.grants.generation
            value["elapsedMs"] = int((time.monotonic() - started) * 1000)
            if not self.journal.record(value):
                value.update(accepted=False, errorCode="audit_storage_unavailable", uncertainty="audit_result_not_persisted", retrySafety="unsafe")
            self.grants.record(value)
            complete(value)

        def grant_reply(accepted, error):
            value = self.provider.envelope(request, operation)
            value["accepted"] = accepted
            if error:
                value["errorCode"] = error
            value["data"] = self.grants.state()["deployment"]
            finish(value)

        try:
            durable = self.journal.begin(operation, request["requestId"], self.grants.generation, caller_pid)
            if not durable and operation != "grant.revoke":
                finish(self.provider.fail(request, operation, "audit_storage_unavailable", "Audit storage unavailable"))
                return
            self.monitor()
            if operation in {"update.check", "update.status"}:
                result["data"] = self.updates.request(operation == "update.check")
                finish(result)
                return
            if operation == "grant.request":
                self.grants.request(request, caller, grant_reply)
                return
            if operation == "grant.revoke":
                self.grants.stop("revoked_by_caller")
                if self.portal.state == "pending":
                    self.portal.close()
            elif operation in {"grant.status", "status"}:
                result["data"] = {**self.grants.state()["deployment"],
                                  "desktopProduct": True, "ready": self.grants.ready,
                                  "sourceRevision": self.identity.get("sourceRevision"),
                                  "semanticState": "ready" if self.unlocked else "unavailable",
                                  "captureState": "ready" if self.portal.ready else "unavailable",
                                  "inputState": "ready" if self.provider.input_ready() else "unavailable"}
            elif operation == "capabilities":
                result["data"] = {"provider": "linux-desktop", "profile": "gnome_wayland",
                                  "privilege": "ordinary_user", "operations": sorted(OBSERVE | CONTROL | {"update.check", "update.status"}),
                                  "capture": {"route": "user/linux.portal-pipewire", "scope": "shared_screen",
                                              "state": self.portal.state},
                                  "input": {"route": "user/linux.portal-notify", "authorization": "portal_consent",
                                            "coordinateSpace": "portal_shared_screen"},
                                  "protectedDesktop": False, "hostInterference": "none"}
            else:
                error = self.grants.authorize(operation, request.get("expectedGeneration") or request.get("generation"))
                if error:
                    result = self.provider.fail(request, operation, error, "Access refused")
                elif operation.startswith("browser."):
                    if operation == "browser.upload":
                        result = self.provider.fail(request, operation, "unsupported_operation", "Upload is unavailable")
                    else:
                        self.browser.execute(request, finish)
                        return
                else:
                    self.provider_work(request, finish)
                    return
            finish(result)
        except Exception as error:
            self.journal.diagnostic("provider.request", "operation_failed")
            finish(self.provider.fail(request, operation, "invalid_request", str(error)))

    def start_safety(self):
        environment = dict(os.environ)
        environment.pop("NO_AT_BRIDGE", None)
        self.safety = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).with_name("notice.py"))],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=sys.stderr, env=environment)

        def write():
            while not self.stopped:
                with self.safety_condition:
                    self.safety_condition.wait_for(lambda: self.safety_state is not None or self.stopped)
                    value, self.safety_state = self.safety_state, None
                if self.stopped:
                    return
                try:
                    self.safety.stdin.write(encode(value))
                    self.safety.stdin.flush()
                except OSError:
                    return

        def read():
            try:
                while True:
                    value = read_frame(self.safety.stdout)
                    if value is None:
                        break
                    def intent(value=value):
                        method = value.get("method")
                        if method == "ready":
                            self.safety_available = True
                            self.monitor()
                        elif method == "presented" and value.get("generation") == self.grants.generation:
                            self.grants.notice_ready = True
                        elif method in {"stop", "pause", "resume"}:
                            try:
                                self.operator(value)
                            except ValueError:
                                pass
                        elif method == "settings":
                            subprocess.Popen([self.executable, "--instance", self.instance, "--settings"],
                                             stdout=subprocess.DEVNULL, stderr=sys.stderr)
                        return False
                    self.scheduler.post(intent)
            finally:
                self.safety.wait()
                def lost():
                    self.safety_available = False
                    self.grants.set_ready(False)
                    self.grants.stop("safety_unavailable")
                    return False
                self.scheduler.post(lost)
        threading.Thread(target=write, daemon=True).start()
        threading.Thread(target=read, daemon=True).start()

    def accept_recovery(self):
        while not self.stopped:
            try:
                client, _ = self.recovery.accept()
            except OSError:
                return
            if not self.recovery_slots.acquire(blocking=False):
                client.close()
                continue
            threading.Thread(target=self.recovery_client, args=(client,), daemon=True).start()

    def recovery_client(self, client):
        try:
            _pid, uid, _gid = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                return
            client.settimeout(3)
            request = read_frame(SocketFrames(client))
            if not request or request.get("method") not in {"presentation", "presentation.status", "stop"}:
                return
            event = threading.Event()
            reply = []
            cancelled = threading.Event()
            def run():
                if cancelled.is_set():
                    return False
                try:
                    reply.append(self.operator(request))
                except Exception as error:
                    reply.append({"ok": False, "error": str(error)})
                event.set()
                return False
            self.scheduler.post(run)
            if event.wait(3):
                client.sendall(encode(reply[0]))
            else:
                cancelled.set()
        except (OSError, ValueError):
            pass
        finally:
            client.close()
            self.recovery_slots.release()

    def provider_work(self, request, finish):
        operation = request["operation"]
        grant = self.grants.grant
        ticket = Ticket(self.grants.generation, grant["expires"] if grant else None)
        ticket.request_id = request["requestId"]
        replied = False
        timer = None

        def completed(value, error):
            nonlocal replied
            if replied:
                return
            replied = True
            if timer:
                self.scheduler.remove(timer)
            stale = ticket.generation != self.grants.generation
            if error or stale or ticket.cancelled.is_set() or time.monotonic() >= ticket.deadline:
                observed = value
                value = self.provider.fail(request, operation, "operation_cancelled", "Work ended or authority changed")
                if observed:
                    value.update(actualRoute=observed.get("actualRoute", value["actualRoute"]),
                                 fidelity=observed.get("fidelity", value["fidelity"]))
                elif operation.startswith("input."):
                    value.update(actualRoute="user/linux.portal-notify", fidelity="foreground_input")
                if ticket.dispatched:
                    value.update(delivery="unknown", effect="unknown", uncertainty="cancelled_after_dispatch",
                                 retrySafety="unsafe_delivery_unknown")
            finish(value)

        def run(active):
            active.check()
            if self.provider.generation != active.generation:
                self.provider.generation = active.generation
                self.provider.snapshots.clear()
            self.provider.ticket = active
            self.portal.ticket = active
            try:
                return self.provider.handle(request)
            finally:
                self.provider.ticket = self.portal.ticket = None

        if not self.work.submit(ticket, run, completed):
            finish(self.provider.fail(request, operation, "provider_busy", "Provider work is still running"))
            return

        def deadline():
            if not replied:
                ticket.cancelled.set()
                completed(None, Cancelled())
            return False
        timer = self.scheduler.timer(20000, deadline)

    def accept(self):
        while not self.stopped:
            try:
                client, _ = self.socket.accept()
            except OSError:
                break
            if not self.slots.acquire(blocking=False):
                client.close()
                continue
            threading.Thread(target=self.client, args=(client,), daemon=True).start()

    def client(self, client):
        event = threading.Event()
        browser = False
        reader = None
        try:
            pid, uid, _gid = struct.unpack("3i", client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if uid != os.getuid():
                return
            client.settimeout(5)
            reader = SocketFrames(client)
            request = read_frame(reader)
            if request is None:
                return
            request["requestId"] = request.get("requestId") or uuid.uuid4().hex
            if request.get("operation") == "browser.register":
                browser = True
                def register():
                    self.journal.event("browser.connected")
                    self.browser.register(client, pid)
                    event.set()
                    return False
                self.scheduler.post(register)
                event.wait(5)
                # A separate readable descriptor avoids Python buffered socket
                # timeout poisoning. Writes remain bounded to three seconds.
                client.settimeout(3)
                while not self.stopped:
                    if b"\n" not in reader.buffer and not select.select([client], [], [], 1)[0]:
                        continue
                    line = reader.readline(1024 * 1024 + 1)
                    if not line or len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                        break
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        break
                    self.scheduler.post(lambda value=value: self.browser.message(client, value) or False)
                return

            replies = []

            def complete(value):
                replies.append(value)
                event.set()

            self.scheduler.post(lambda: self.handle(request, f"pid {pid}", complete, caller_pid=pid) or False)
            end = time.monotonic() + 610
            while not event.wait(.1):
                if time.monotonic() >= end or select.select([client], [], [], 0)[0]:
                    self.scheduler.post(lambda: self.cancel_caller(request) or False)
                    return
            if replies:
                client.sendall(encode(replies[0]))
        except (OSError, ValueError):
            pass
        finally:
            if browser:
                self.scheduler.post(lambda: self.browser.disconnect(client) or False)
            client.close()
            self.slots.release()

    def cancel_caller(self, request):
        if request.get("operation") == "grant.request" and self.grants.pending:
            if self.grants.pending.get("requestId") == request["requestId"]:
                self.grants.finish_pending(False, "caller_disconnected")
        elif self.work.active and self.work.active.request_id == request.get("requestId"):
            self.work.cancel()

    def operator_reader(self):
        while not self.stopped:
            try:
                command = read_frame(sys.stdin.buffer)
                if command is None:
                    break
                complete = threading.Event()
                replies = []

                def run(command=command):
                    try:
                        reply = self.operator(command)
                    except Exception as error:
                        reply = {"ok": False, "error": str(error)}
                    reply["coordinatorGeneration"] = self.grants.generation
                    replies.append(reply)
                    complete.set()
                    return False

                self.scheduler.post(run)
                complete.wait()
                sys.stdout.buffer.write(encode(replies[0]))
                sys.stdout.buffer.flush()
            except (ValueError, OSError):
                break
        self.scheduler.post(lambda: self.shutdown() or False)

    def shutdown(self):
        self.journal.event("resident.stop")
        if self.stopped:
            return
        self.stopped = True
        self.work.cancel()
        self.grants.stop("operator_disconnected")
        self.portal.close()
        self.browser.disconnect()
        self.socket.close()
        self.endpoint.unlink(missing_ok=True)
        self.recovery.close()
        self.recovery_endpoint.unlink(missing_ok=True)
        self.presentation.close()
        with self.safety_condition:
            self.safety_condition.notify_all()
        if self.safety.poll() is None:
            self.safety.terminate()
        self.loop.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--call", help="One agent request on stdin")
    args = parser.parse_args()
    if args.call:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(610)
            client.connect(args.call)
            client.sendall(encode(json.loads(sys.stdin.read())))
            with client.makefile("rb") as reader:
                sys.stdout.buffer.write(reader.read())
        return
    hello = read_frame(sys.stdin.buffer)
    if not hello or hello.get("method") != "hello" or hello.get("processId") != os.getppid():
        raise ValueError("Inherited operator handshake required")
    desktop = Desktop(os.getppid(), hello["executable"], hello.get("instance", "desktop"), hello.get("presentation"))
    for sig in [signal.SIGTERM, signal.SIGINT]:
        desktop.scheduler.signal(sig, lambda: desktop.shutdown() or False)
    threading.Thread(target=desktop.accept, daemon=True).start()
    threading.Thread(target=desktop.operator_reader, daemon=True).start()
    sys.stdout.buffer.write(encode({"ok": True}))
    sys.stdout.buffer.flush()
    try:
        desktop.loop.run()
    finally:
        desktop.shutdown()


if __name__ == "__main__":
    main()

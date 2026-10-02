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

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

from grants import Grants, OBSERVE, CONTROL
from portal import Portal
from provider import Provider
from shortcut import Shortcut
from browser import Browser
import linuxui

FRAME_LIMIT = 65536


def runtime_directory():
    path = Path(os.environ["XDG_RUNTIME_DIR"]) / "machine-control-desktop"
    path.mkdir(mode=0o700, exist_ok=True)
    value = path.lstat()
    if not stat.S_ISDIR(value.st_mode) or value.st_uid != os.getuid() or stat.S_IMODE(value.st_mode) != 0o700:
        raise RuntimeError("Private runtime directory is required")
    return path


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
    def __init__(self, operator_pid, executable):
        Gtk.init([])
        self.loop = GLib.MainLoop()
        self.operator_pid = operator_pid
        self.grants = Grants(self.changed)
        self.provider = Provider(self)
        self.last_portal_state = "off"
        self.portal = Portal(self.changed)
        self.shortcut = Shortcut(executable)
        self.browser = Browser(self)
        self.dialog = None
        self.dialog_id = None
        self.unlocked = False
        self.stopped = False
        self.directory = runtime_directory()
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
        self.monitor()
        GLib.timeout_add(1000, self.monitor)

    def changed(self):
        if hasattr(self, "provider"):
            self.provider.generation = self.grants.generation
            self.provider.snapshots.clear()
        if hasattr(self, "portal"):
            previous, self.last_portal_state = self.last_portal_state, self.portal.state
            if previous == "ready" and self.portal.state != "ready":
                self.grants.stop("sharing_ended")
            self.grants.set_ready(self.unlocked and self.portal.state != "pending")
        if hasattr(self, "dialog"):
            self.approval()
        if hasattr(self, "browser"):
            self.browser.sync()

    def monitor(self):
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            locked = bus.call_sync("org.gnome.ScreenSaver", "/org/gnome/ScreenSaver",
                                   "org.gnome.ScreenSaver", "GetActive", None,
                                   GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 500, None).unpack()[0]
            # This profile is deliberately GNOME Wayland only.
            self.unlocked = not locked and os.environ.get("XDG_SESSION_TYPE") == "wayland" and (
                "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", ""))
        except GLib.Error:
            self.unlocked = False
        self.grants.set_ready(self.unlocked and self.portal.state != "pending")
        if not self.unlocked and self.portal.state != "off":
            self.portal.close()
        self.grants.refresh()
        self.approval()
        self.browser.sync()
        return not self.stopped

    def approval(self):
        pending = self.grants.pending
        identifier = pending["id"] if pending else None
        if identifier == self.dialog_id:
            return
        self.dialog_id = identifier
        if self.dialog:
            if self.dialog.poll() is None:
                self.dialog.terminate()
            self.dialog.wait(timeout=3)
            self.dialog = None
        if not pending:
            return
        # GTK approval lives separately from the synchronous AT-SPI provider;
        # querying an in-process GTK accessible can deadlock its own main loop.
        process = subprocess.Popen(["/usr/bin/python3", str(Path(__file__).with_name("approval.py"))],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=sys.stderr)
        self.dialog = process
        value = {k: pending[k] for k in ["id", "reason", "caller", "duration"]}
        value["parentId"] = os.getpid()
        value["scopes"] = sorted(pending["scopes"])
        process.stdin.write(encode(value))
        process.stdin.close()

        def wait():
            line = process.stdout.readline(FRAME_LIMIT + 1)
            process.wait()
            def decision():
                if self.dialog_id != identifier:
                    return False
                try:
                    reply = json.loads(line)
                    self.grants.decide(identifier, reply.get("allow") is True,
                                       reply.get("scopes"), reply.get("duration", 0))
                except (ValueError, TypeError):
                    self.grants.stop("approval_unavailable")
                self.approval()
                return False
            GLib.idle_add(decision)
        threading.Thread(target=wait, daemon=True).start()

    def state(self):
        self.monitor()
        return {**self.grants.state(), "platform": "linux", "supportedScopes": ["observe", "control", "browser", "devtools"],
                "permissions": {"accessibility": self.unlocked, "screenRecording": self.portal.ready},
                "portal": {"state": self.portal.state, "error": self.portal.error,
                           "pointer": bool(self.portal.devices & 2), "keyboard": bool(self.portal.devices & 1)},
                "browser": {"connected": self.browser.provider is not None, "available": True},
                "socket": str(self.endpoint), "stopShortcutAvailable": self.shortcut.available,
                "stopShortcut": "Ctrl+Alt+Shift+."}

    def operator(self, command):
        method = command.get("method")
        if method == "state":
            return {"ok": True, "state": self.state()}
        if method == "arm":
            self.grants.arm(command.get("scopes"), command.get("duration", 900))
        elif method == "decision":
            self.grants.decide(command.get("id"), command.get("allow") is True,
                               command.get("scopes"), command.get("duration", 0))
        elif method == "stop":
            self.grants.stop()
            if self.portal.state == "pending":
                self.portal.close()
        elif method == "shortcut":
            self.shortcut.set(command.get("enabled"))
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

    def handle(self, request, caller, complete):
        operation = request.get("operation", "")
        result = self.provider.envelope(request, operation)

        def finish(value):
            value["generation"] = self.grants.generation
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
            self.monitor()
            if operation == "grant.request":
                self.grants.request(request, caller, grant_reply)
                return
            if operation == "grant.revoke":
                self.grants.stop("revoked_by_caller")
                if self.portal.state == "pending":
                    self.portal.close()
            elif operation in {"grant.status", "status"}:
                result["data"] = {**self.grants.state()["deployment"],
                                  "desktopProduct": True, "ready": self.unlocked,
                                  "semanticState": "ready" if self.unlocked else "unavailable",
                                  "captureState": "ready" if self.portal.ready else "unavailable",
                                  "inputState": "ready" if self.provider.input_ready() else "unavailable"}
            elif operation == "capabilities":
                result["data"] = {"provider": "linux-desktop", "profile": "gnome_wayland",
                                  "privilege": "ordinary_user", "operations": sorted(OBSERVE | CONTROL - {"input.drag"}),
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
                    result = self.provider.handle(request)
            finish(result)
        except Exception as error:
            finish(self.provider.fail(request, operation, "invalid_request", str(error)))

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
            if request.get("operation") == "browser.register":
                browser = True
                def register():
                    self.browser.register(client, pid)
                    event.set()
                    return False
                GLib.idle_add(register)
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
                    GLib.idle_add(lambda value=value: self.browser.message(client, value) or False)
                return

            def complete(value):
                try:
                    client.sendall(encode(value))
                except OSError:
                    pass
                finally:
                    event.set()

            GLib.idle_add(lambda: self.handle(request, f"pid {pid}", complete) or False)
            event.wait(610)
        except (OSError, ValueError):
            pass
        finally:
            if browser:
                GLib.idle_add(lambda: self.browser.disconnect(client) or False)
            client.close()
            self.slots.release()

    def operator_reader(self):
        while not self.stopped:
            try:
                command = read_frame(sys.stdin.buffer)
                if command is None:
                    break
                complete = threading.Event()

                def run(command=command):
                    try:
                        reply = self.operator(command)
                    except Exception as error:
                        reply = {"ok": False, "error": str(error)}
                    sys.stdout.buffer.write(encode(reply))
                    sys.stdout.buffer.flush()
                    complete.set()
                    return False

                GLib.idle_add(run)
                complete.wait()
            except (ValueError, OSError):
                break
        GLib.idle_add(lambda: self.shutdown() or False)

    def shutdown(self):
        if self.stopped:
            return
        self.stopped = True
        self.grants.stop("operator_disconnected")
        self.portal.close()
        self.browser.disconnect()
        self.socket.close()
        self.endpoint.unlink(missing_ok=True)
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
    desktop = Desktop(os.getppid(), hello["executable"])
    for sig in [signal.SIGTERM, signal.SIGINT]:
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: desktop.shutdown() or False)
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

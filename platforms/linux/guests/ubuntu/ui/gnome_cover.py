"""An exact GNOME compositor cover bound to one live D-Bus connection."""

from __future__ import annotations

import os
from pathlib import Path
import re
import threading
import time

from gnome_unlock import UnlockRefused
from activity import ENDPOINT, console_binding, read_sample


PATH = "/dev/machinecontrol/CoveredDesktop"
INTERFACE = "dev.machinecontrol.CoveredDesktop1"


class Takeover:
    def __init__(self, console, endpoint=ENDPOINT):
        self.endpoint = Path(endpoint)
        self.binding = console_binding((console.session_id, console.started, console.shell_owner))
        self.baseline = None

    def observe(self):
        try:
            value = read_sample(self.endpoint, True, self.binding)
            motion = value.get("motionToken")
            if (not value["healthy"] or not isinstance(motion, str) or len(motion) != 32
                    or time.monotonic() - value["observedThroughUptime"] > 1.5):
                return None
            return value["generation"], value["activityToken"], motion
        except (OSError, ValueError, KeyError):
            return None

    def prepare(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            self.baseline = self.observe()
            if self.baseline is not None:
                return
            time.sleep(0.1)
        raise UnlockRefused("gnome_cover_input_observer_unavailable")

    def state(self):
        current = self.observe()
        if current is None or current[0] != self.baseline[0]:
            return "unavailable"
        return "local_input" if current[1:] != self.baseline[1:] else "quiet"


class GnomeCover:
    def __init__(self, provider, console, takeover=None):
        self.provider = provider
        self.console = console
        self.takeover = takeover if takeover is not None else Takeover(console)
        self.connection = None
        self.identifier = None
        self.stop_renewing = threading.Event()
        self.lost = threading.Event()
        self.worker = None

    def open(self):
        self.provider.require_locked(self.console)
        self.takeover.prepare()
        gio = self.provider.Gio
        address = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        if not address:
            raise UnlockRefused("gnome_cover_unavailable")
        try:
            self.connection = gio.DBusConnection.new_for_address_sync(
                address, gio.DBusConnectionFlags.AUTHENTICATION_CLIENT
                | gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None,
            )
        except self.provider.GLib.Error:
            raise UnlockRefused("gnome_cover_unavailable") from None
        self.connection.set_exit_on_close(False)
        try:
            self.shell = self.bus_query("GetNameOwner", "org.gnome.Shell", "(s)")
            if (self.bus_query("GetConnectionUnixProcessID", self.shell, "(u)")
                    != self.bus_query("GetConnectionUnixProcessID", self.console.shell_owner, "(u)")):
                raise UnlockRefused("gnome_cover_console_changed")
            self.provider.require_locked(self.console)
            self.identifier = self.call("Begin", None, "(s)")[0]
            self.worker = threading.Thread(target=self.renew, daemon=True)
            self.worker.start()
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and not self.lost.is_set():
                if self.covered():
                    self.provider.require_locked(self.console)
                    return
                if self.status()[0] != "painting":
                    break
                time.sleep(0.05)
            raise UnlockRefused("gnome_cover_not_painted")
        except BaseException:
            self.close()
            raise

    def bus_query(self, method, name, signature):
        return self.provider.call(
            self.connection, "org.freedesktop.DBus", "/org/freedesktop/DBus",
            "org.freedesktop.DBus", method, ("(s)", (name,)), signature, timeout=500,
        )[0]

    def call(self, method, parameters, signature):
        try:
            return self.provider.call(
                self.connection, self.shell, PATH, INTERFACE,
                method, parameters, signature, timeout=500,
            )
        except UnlockRefused:
            raise UnlockRefused("gnome_cover_unavailable") from None

    def status(self):
        return self.provider.call(
            self.provider.session, self.shell, PATH, INTERFACE,
            "Status", None, "(ss)", timeout=500,
        )

    def covered(self):
        return (
            not self.lost.is_set() and not self.stop_renewing.is_set()
            and self.call("Check", ("(s)", (self.identifier,)), "(b)")[0] is True
        )

    def opaque_frame(self):
        return self.call("CheckPixels", ("(s)", (self.identifier,)), "(b)")[0] is True

    def capture(self):
        gio, glib = self.provider.Gio, self.provider.GLib
        try:
            reply = self.connection.call_sync(
                self.shell, PATH, INTERFACE, "Capture", glib.Variant("(s)", (self.identifier,)),
                glib.VariantType("(ay)"), gio.DBusCallFlags.NONE, 3000, None,
            )
            return bytes(reply.unpack()[0])
        except glib.Error as error:
            name = gio.DBusError.get_remote_error(error) or ""
            reason = name.rpartition(".")[2]
            if not re.fullmatch(r"gnome_covered_capture_(setup|allocate|paint|encode)_failed", reason):
                reason = "gnome_covered_capture_unavailable"
            raise UnlockRefused(reason) from None

    def click(self, x, y):
        self.call("Click", ("(sii)", (self.identifier, x, y)), "()")

    def renew(self):
        while not self.stop_renewing.wait(0.3):
            try:
                activity = self.takeover.state()
                if activity != "quiet":
                    self.lost.set()
                    self.call("Interrupt" if activity == "local_input" else "End",
                              ("(s)", (self.identifier,)), "()")
                    return
                self.call("Keep", ("(s)", (self.identifier,)), "()")
            except UnlockRefused:
                self.lost.set()
                return

    def close(self, *, end=True):
        self.stop_renewing.set()
        if self.worker is not None:
            self.worker.join(timeout=0.6)
        if self.connection is None:
            return
        try:
            if end and self.identifier is not None:
                self.call("End", ("(s)", (self.identifier,)), "()")
        except UnlockRefused:
            # Closing the owner connection still revokes the compositor lease.
            pass
        finally:
            try:
                self.connection.close_sync(None)
            except self.provider.GLib.Error:
                pass
            self.connection = None

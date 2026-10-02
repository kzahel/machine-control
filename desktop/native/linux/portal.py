"""Ordinary-user XDG RemoteDesktop + ScreenCast adapter (no appliance input)."""

from __future__ import annotations

import math
import os
import time
import uuid

import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("GstApp", "1.0")
from gi.repository import Gdk, Gio, GLib, Gst, GstApp


DEST = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
REMOTE = "org.freedesktop.portal.RemoteDesktop"
CAST = "org.freedesktop.portal.ScreenCast"


class Portal:
    def __init__(self, changed):
        Gst.init(None)
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.changed = changed
        self.session = None
        self.request = None
        self.subscription = None
        self.closed_subscription = None
        self.pipeline = None
        self.fd = None
        self.stream = None
        self.devices = 0
        self.state = "off"
        self.error = None
        self.epoch = 0
        self.deadline = None
        self.deliveries = 0
        self.bus.signal_subscribe(
            "org.freedesktop.DBus", "org.freedesktop.DBus", "NameOwnerChanged",
            "/org/freedesktop/DBus", DEST, Gio.DBusSignalFlags.NONE,
            lambda *args: self.close() if not args[-2].unpack()[2] else None,
        )

    @property
    def ready(self):
        return self.state == "ready"

    def _call(self, interface, method, signature, args):
        return self.bus.call_sync(DEST, PATH, interface, method,
                                  GLib.Variant(signature, args), None,
                                  Gio.DBusCallFlags.NONE, 3000, None)

    def _request(self, interface, method, signature, args, done):
        token = "mc" + uuid.uuid4().hex
        options = args[-1]
        options["handle_token"] = GLib.Variant("s", token)
        sender = self.bus.get_unique_name()[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        epoch = self.epoch

        def response(_bus, _sender, _path, _interface, _signal, value, _data):
            if epoch != self.epoch:
                return
            self.bus.signal_unsubscribe(self.subscription)
            self.subscription = self.request = None
            code, results = value.unpack()
            if code != 0:
                self.close("Sharing was cancelled" if code == 1 else "Sharing failed")
                return
            try:
                done(results)
            except Exception:
                self.close("Desktop sharing is unavailable")

        self.request = path
        self.subscription = self.bus.signal_subscribe(
            DEST, "org.freedesktop.portal.Request", "Response", path, None,
            Gio.DBusSignalFlags.NONE, response, None)
        self._call(interface, method, signature, args)

    def connect(self):
        if self.state == "pending":
            return
        self.close()
        self.state = "pending"
        self.error = None
        self.changed()
        self.deadline = GLib.timeout_add_seconds(120, lambda: self._timeout())

        def created(value):
            self.session = value["session_handle"]
            self.closed_subscription = self.bus.signal_subscribe(
                DEST, "org.freedesktop.portal.Session", "Closed", self.session,
                None, Gio.DBusSignalFlags.NONE, lambda *args: self.close(), None)
            self._request(REMOTE, "SelectDevices", "(oa{sv})", [self.session,
                {"types": GLib.Variant("u", 3)}], devices)

        def devices(_value):
            self._request(CAST, "SelectSources", "(oa{sv})", [self.session,
                {"types": GLib.Variant("u", 1),
                 "multiple": GLib.Variant("b", False),
                 "cursor_mode": GLib.Variant("u", 2)}], sources)

        def sources(_value):
            self._request(REMOTE, "Start", "(osa{sv})", [self.session, "", {}], started)

        def started(value):
            streams = value.get("streams", [])
            if len(streams) != 1:
                raise RuntimeError("Choose one screen")
            self.stream, self.properties = streams[0]
            self.devices = value.get("devices", 0)
            response, fds = self.bus.call_with_unix_fd_list_sync(
                DEST, PATH, CAST, "OpenPipeWireRemote",
                GLib.Variant("(oa{sv})", (self.session, {})), GLib.VariantType("(h)"),
                Gio.DBusCallFlags.NONE, 3000, None, None)
            self.fd = fds.get(response.unpack()[0])
            self.pipeline = Gst.parse_launch(
                f"pipewiresrc fd={self.fd} path={self.stream} do-timestamp=true "
                "! videoconvert ! video/x-raw,format=RGB "
                "! pngenc ! appsink name=frames max-buffers=1 drop=true sync=false")
            if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                raise RuntimeError("Screen stream failed")
            self.state = "ready"
            if self.deadline:
                GLib.source_remove(self.deadline)
                self.deadline = None
            self.changed()

        try:
            self._request(REMOTE, "CreateSession", "(a{sv})", [{
                "session_handle_token": GLib.Variant("s", "mc" + uuid.uuid4().hex)
            }], created)
        except Exception:
            self.close("Desktop portal is unavailable")

    def capture(self):
        if not self.ready or self.pipeline is None:
            raise RuntimeError("Allow desktop sharing first")
        sink = self.pipeline.get_by_name("frames")
        sample = sink.try_pull_sample(2 * Gst.SECOND)
        if sample is None:
            raise RuntimeError("Screen stream did not provide a frame")
        buffer = sample.get_buffer()
        data = buffer.extract_dup(0, buffer.get_size())
        if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 16 * 1024 * 1024:
            raise RuntimeError("Invalid screen frame")
        return data

    def _timeout(self):
        self.deadline = None
        if self.state == "pending":
            self.close("Sharing timed out; try again")
        return False

    def _notify(self, method, signature, args):
        if not self.ready:
            raise RuntimeError("Desktop sharing is unavailable")
        self.deliveries += 1
        self._call(REMOTE, method, signature, [self.session, {}] + args)

    def move(self, x, y):
        size = self.properties.get("logical_size", self.properties.get("size"))
        if not size or not all(math.isfinite(v) for v in [x, y]) or not (
                0 <= x < size[0] and 0 <= y < size[1]):
            raise ValueError("Use coordinates inside the shared screen")
        if not self.devices & 2:
            raise RuntimeError("Pointer access was not shared")
        self._notify("NotifyPointerMotionAbsolute", "(oa{sv}udd)",
                     [self.stream, float(x), float(y)])

    def click(self, x, y, button="left", count=1):
        codes = {"left": 272, "right": 273, "middle": 274}
        if type(count) is not int or not 1 <= count <= 3:
            raise ValueError("Choose 1-3 clicks")
        code = codes[button]
        self.move(x, y)
        for index in range(count):
            try:
                self._notify("NotifyPointerButton", "(oa{sv}iu)", [code, 1])
            finally:
                self._notify("NotifyPointerButton", "(oa{sv}iu)", [code, 0])
            if index + 1 < count:
                time.sleep(.08)

    def drag(self, x1, y1, x2, y2):
        size = self.properties.get("logical_size", self.properties.get("size"))
        if not size or not all(math.isfinite(v) for v in [x1, y1, x2, y2]) or not (
                0 <= x1 < size[0] and 0 <= x2 < size[0] and 0 <= y1 < size[1] and 0 <= y2 < size[1]):
            raise ValueError("Use coordinates inside the shared screen")
        self.move(x1, y1)
        try:
            self._notify("NotifyPointerButton", "(oa{sv}iu)", [272, 1])
            for index in range(1, 9):
                self.move(x1 + (x2 - x1) * index / 8, y1 + (y2 - y1) * index / 8)
                time.sleep(.025)
        finally:
            self._notify("NotifyPointerButton", "(oa{sv}iu)", [272, 0])

    def scroll(self, dx, dy):
        if not self.devices & 2 or not all(
                math.isfinite(v) and float(v).is_integer() and abs(v) <= 1000
                for v in [dx, dy]):
            raise ValueError("Choose bounded scroll deltas with shared pointer access")
        # The facade expresses wheel steps, rather than touchpad distances.
        for axis, steps in [(0, dy), (1, dx)]:
            if steps:
                self._notify("NotifyPointerAxisDiscrete", "(oa{sv}ui)",
                             [axis, int(steps)])

    def key(self, key):
        if not self.devices & 1:
            raise RuntimeError("Keyboard access was not shared")
        aliases = {"ctrl": "Control_L", "alt": "Alt_L", "shift": "Shift_L",
                   "super": "Super_L", "enter": "Return", "esc": "Escape",
                   "tab": "Tab", "backspace": "BackSpace", "delete": "Delete",
                   "space": "space", "left": "Left", "right": "Right",
                   "up": "Up", "down": "Down", "home": "Home", "end": "End"}
        names = key.split("+")
        if len(names) > 5 or not names:
            raise ValueError("Invalid key combination")
        codes = [Gdk.keyval_from_name(aliases.get(n.lower(), n)) for n in names]
        if any(not c or c == 0xFFFFFF for c in codes):
            raise ValueError("Unknown key")
        pressed = []
        try:
            for code in codes:
                self._notify("NotifyKeyboardKeysym", "(oa{sv}iu)", [code, 1])
                pressed.append(code)
        finally:
            for code in reversed(pressed):
                self._notify("NotifyKeyboardKeysym", "(oa{sv}iu)", [code, 0])

    def close(self, error=None):
        self.epoch += 1
        if self.deadline:
            GLib.source_remove(self.deadline)
            self.deadline = None
        for attr in ["subscription", "closed_subscription"]:
            value = getattr(self, attr)
            if value:
                self.bus.signal_unsubscribe(value)
                setattr(self, attr, None)
        for path, interface in [(self.request, "org.freedesktop.portal.Request"),
                                (self.session, "org.freedesktop.portal.Session")]:
            if path:
                try:
                    self.bus.call_sync(DEST, path, interface, "Close", None, None,
                                       Gio.DBusCallFlags.NONE, 1000, None)
                except GLib.Error:
                    pass
        self.request = self.session = None
        self.stream = None
        self.devices = 0
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        self.state = "off"
        self.error = error
        self.changed()

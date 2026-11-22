"""Authenticate the current locked GNOME console through GDM.

The caller owns consent, credential storage, display covers and relocking.
This provider never chooses an account, opens a greeter or requests a logind
unlock directly.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import pwd
import time


GDM_PASSWORD_SERVICE = "gdm-password"
SCREENSAVER = "org.gnome.ScreenSaver"
SCREEN_SHIELD = "org.gnome.Shell.ScreenShield"
LOGIN = "org.freedesktop.login1"
MAX_PASSWORD_BYTES = 4096


class UnlockRefused(RuntimeError):
    """A stable result code. Never include GDM messages or credentials."""


@dataclass(frozen=True)
class Console:
    path: str
    session_id: str
    started: int
    shell_owner: str


@dataclass(frozen=True)
class Observation:
    console: Console
    locked: bool
    unlocked: bool


def observe_console(system, session, call, uid):
    """Require a unique, active, local Wayland user session on the local seat."""
    manager = LOGIN + ".Manager"
    dbus = "org.freedesktop.DBus"
    properties = dbus + ".Properties"
    sessions = call(system, LOGIN, "/org/freedesktop/login1", manager,
                    "ListSessions", None, "(a(susso))")[0]
    candidates = []
    for session_id, user_id, _name, seat, path in sessions:
        if user_id != uid:
            continue
        fields = call(system, LOGIN, path, properties, "GetAll",
                      ("(s)", (LOGIN + ".Session",)), "(a{sv})")[0]
        if fields.get("Type") in {"wayland", "x11"}:
            candidates.append((session_id, seat, path, fields))
    if len(candidates) != 1:
        raise UnlockRefused("gnome_console_unavailable")
    session_id, seat, path, fields = candidates[0]
    started = fields.get("TimestampMonotonic")
    if (seat != "seat0" or fields.get("Class") != "user"
            or fields.get("Type") != "wayland" or fields.get("Remote") is not False
            or fields.get("Active") is not True or fields.get("Id") != session_id
            or type(started) is not int or started <= 0):
        raise UnlockRefused("gnome_console_unavailable")

    def bus_query(method, name, signature):
        return call(session, dbus, "/org/freedesktop/DBus", dbus,
                    method, ("(s)", (name,)), signature)[0]

    owner = bus_query("GetNameOwner", SCREEN_SHIELD, "(s)")
    shell = bus_query("GetNameOwner", "org.gnome.Shell", "(s)")
    if (not owner.startswith(":") or not shell.startswith(":")
            or bus_query("GetConnectionUnixProcessID", owner, "(u)")
            != bus_query("GetConnectionUnixProcessID", shell, "(u)")):
        raise UnlockRefused("gnome_console_unavailable")
    locked_hint = fields.get("LockedHint")
    active = call(session, owner, "/org/gnome/ScreenSaver", SCREENSAVER,
                  "GetActive", None, "(b)")[0]
    return Observation(Console(path, session_id, started, owner),
                       locked_hint is True and active is True,
                       locked_hint is False and active is False)


class PasswordQuestion:
    """Admit exactly one recognised GDM password prompt per transaction."""

    def __init__(self):
        self.sent = False

    def accept(self, service, prompt):
        if (self.sent or service != GDM_PASSWORD_SERVICE
                or prompt.strip() not in {"Password:", "Password"}):
            raise UnlockRefused("gnome_password_prompt_unavailable")
        self.sent = True


class GnomeUnlock:
    def __init__(self):
        import gi
        gi.require_version("Gdm", "1.0")
        from gi.repository import Gdm, Gio, GLib

        self.Gdm, self.Gio, self.GLib = Gdm, Gio, GLib
        self.uid = os.getuid()
        if self.uid == 0:
            raise UnlockRefused("gnome_console_unavailable")
        self.system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.session = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def call(self, bus, destination, path, interface, method, parameters, signature,
             timeout=1000):
        try:
            return bus.call_sync(
                destination, path, interface, method,
                self.GLib.Variant(*parameters) if parameters else None,
                self.GLib.VariantType(signature), self.Gio.DBusCallFlags.NONE, timeout, None,
            ).unpack()
        except self.GLib.Error:
            raise UnlockRefused("gnome_console_unavailable") from None

    def observe(self):
        return observe_console(self.system, self.session, self.call, self.uid)

    def require_locked(self, console):
        state = self.observe()
        if state.console != console or not state.locked:
            raise UnlockRefused("gnome_locked_console_changed")

    def lock(self, console):
        state = self.observe()
        if state.console != console:
            raise UnlockRefused("gnome_locked_console_changed")
        if state.locked:
            return
        try:
            self.call(self.session, console.shell_owner, "/org/gnome/ScreenSaver",
                      SCREENSAVER, "Lock", None, "()", timeout=3000)
        except UnlockRefused:
            # Lock replies after the animation; a timeout can still have an
            # effect. Observe it without sending a second lock request.
            pass
        self.wait_for(console, "locked", lambda: True)

    def wait_for(self, console, state_field, allowed):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if not allowed():
                raise UnlockRefused("gnome_unlock_cancelled")
            state = self.observe()
            if state.console != console:
                raise UnlockRefused("gnome_locked_console_changed")
            if getattr(state, state_field):
                return
            time.sleep(0.1)
        raise UnlockRefused("gnome_" + state_field + "_effect_unverified")

    def authenticate(self, console, read_password, allowed):
        """GDM authentication and same-console unlock are separate observations.

        Read the one-shot secret only while the exact console is locked, the
        caller is still authorized and GDM is awaiting its password. An unlock
        observation alone cannot establish readiness for Desktop operations.
        """
        self.require_locked(console)
        if not allowed():
            raise UnlockRefused("gnome_unlock_cancelled")
        username = pwd.getpwuid(self.uid).pw_name
        client = self.Gdm.Client.new()
        cancel = self.Gio.Cancellable.new()
        context = self.GLib.MainContext.new()
        loop = self.GLib.MainLoop.new(context, False)
        question = PasswordQuestion()
        verifier = None
        dispatched = False
        outcome = None

        def finish(error=None):
            nonlocal outcome
            if outcome is None:
                outcome = (error,)
                loop.quit()

        def answered(source, result):
            try:
                source.call_answer_query_finish(result)
            except self.GLib.Error:
                finish("gnome_unlock_delivery_unknown")

        def query(source, service, prompt):
            nonlocal dispatched
            try:
                question.accept(service, prompt)
                if not allowed():
                    raise UnlockRefused("gnome_unlock_cancelled")
                self.require_locked(console)
                password = read_password()
                if (not isinstance(password, str) or not password or
                        any(character in password for character in ("\x00", "\r", "\n")) or
                        len(password.encode("utf-8")) > MAX_PASSWORD_BYTES):
                    raise UnlockRefused("gnome_password_invalid")
                if not allowed():
                    raise UnlockRefused("gnome_unlock_cancelled")
                self.require_locked(console)
                source.call_answer_query(service, password, cancel, answered)
                dispatched = True
            except UnlockRefused as error:
                finish(str(error))
            except (OSError, UnicodeError):
                finish("gnome_password_unavailable")

        def verified(_source, service):
            finish(None if service == GDM_PASSWORD_SERVICE and dispatched
                   else "gnome_password_prompt_unavailable")

        def started(source, result):
            try:
                source.call_begin_verification_for_user_finish(result)
            except self.GLib.Error:
                finish("gnome_authentication_unavailable")

        def opened(source, result):
            nonlocal verifier
            try:
                verifier = source.open_reauthentication_channel_finish(result)
                if not allowed():
                    raise UnlockRefused("gnome_unlock_cancelled")
                self.require_locked(console)
                verifier.connect("secret-info-query", query)
                verifier.connect("verification-complete", verified)
                verifier.connect("info-query", lambda *_: finish("gnome_password_prompt_unavailable"))
                verifier.connect("verification-failed", lambda *_: finish("gnome_authentication_failed"))
                verifier.connect("conversation-stopped", lambda *_: finish("gnome_authentication_failed"))
                verifier.connect("service-unavailable", lambda *_: finish("gnome_authentication_unavailable"))
                verifier.connect("reset", lambda *_: finish("gnome_authentication_failed"))
                verifier.call_begin_verification_for_user(
                    GDM_PASSWORD_SERVICE, username, cancel, started)
            except UnlockRefused as error:
                finish(str(error))
            except self.GLib.Error:
                finish("gnome_authentication_unavailable")

        def timeout():
            finish("gnome_unlock_delivery_unknown" if dispatched else "gnome_authentication_timeout")
            return self.GLib.SOURCE_REMOVE

        context.push_thread_default()
        timer = self.GLib.timeout_source_new_seconds(10)
        timer.set_callback(lambda *_: timeout())
        timer.attach(context)
        try:
            client.open_reauthentication_channel(username, cancel, opened)
            loop.run()
        finally:
            timer.destroy()
            cancel.cancel()
            if verifier and outcome != (None,):
                verifier.call_cancel(None, None)
            context.pop_thread_default()
        if outcome != (None,):
            raise UnlockRefused(outcome[0] if outcome else "gnome_authentication_unavailable")

        self.wait_for(console, "unlocked", allowed)

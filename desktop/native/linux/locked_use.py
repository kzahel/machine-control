"""Local opt-in and the protected GNOME authentication helper client."""

from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from gi.repository import Gio, GLib

from gnome_cover import INTERFACE, PATH
from gnome_unlock import UnlockRefused
from one_shot import read_reply


UUID = "covered-desktop@machine-control.dev"
EXTENSION = Path("/usr/share/gnome-shell/extensions") / UUID
HELPER = Path("/usr/lib/machine-control/locked-runtime/locked-credential.py")
OPERATOR = Path("/usr/bin/machine-control")
spec = importlib.util.spec_from_file_location("locked_credential", Path(__file__).with_name(HELPER.name))
credential = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = credential
spec.loader.exec_module(credential)


class LockedUse:
    def __init__(self, owner):
        self.owner = owner
        self.path = owner.presentation.root / f"{owner.instance}-locked-use.json"
        self.enabled = self.path.exists()
        self.supported = False
        self.enrolled = False
        self.extension_ready = False
        self.probe_pending = False
        self.probe_observed = 0.0
        self.setup_process = None
        self.cancel_setup = threading.Event()
        self.error = None
        self.paused = False
        self.blocker = "gnome_covered_setup_unavailable"

    @property
    def permission_ready(self):
        return (self.supported and self.enrolled and self.extension_ready
                and self.owner.activity.installed and self.owner.activity.motion_supported
                and time.monotonic() - self.probe_observed < 3)

    @property
    def ready(self):
        return self.enabled and self.permission_ready and not self.paused and self.setup_process is None

    def refresh(self):
        if self.probe_pending:
            return
        self.probe_pending = True
        threading.Thread(target=self.probe, daemon=True, name="mc-locked-use-status").start()

    def probe(self):
        supported = enrolled = extension_ready = False
        blocker = "gnome_covered_setup_unavailable"
        try:
            if os.environ.get("XDG_SESSION_TYPE") != "wayland" or "GNOME" not in os.environ.get("XDG_CURRENT_DESKTOP", ""):
                raise UnlockRefused("gnome_wayland_required")
            if (not os.path.samefile(self.owner.executable, OPERATOR)
                    or not HELPER.is_file() or not (EXTENSION / "metadata.json").is_file()):
                raise UnlockRefused("gnome_covered_debian_package_required")
            user_data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
            if os.path.lexists(user_data / "gnome-shell/extensions" / UUID):
                raise UnlockRefused("gnome_covered_extension_shadowed")
            import gi
            gi.require_version("Gdm", "1.0")
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            version, = bus.call_sync("org.gnome.Shell", "/org/gnome/Shell", "org.freedesktop.DBus.Properties",
                "Get", GLib.Variant("(ss)", ("org.gnome.Shell", "ShellVersion")), GLib.VariantType("(v)"),
                Gio.DBusCallFlags.NONE, 500, None).unpack()
            if not isinstance(version, str) or version.split(".")[0] != "50":
                raise UnlockRefused("gnome_covered_shell_50_required")
            supported = True
            lockdown = Gio.Settings.new("org.gnome.desktop.lockdown")
            if lockdown.get_boolean("disable-lock-screen"):
                raise UnlockRefused("gnome_covered_lock_disabled")
            try:
                value = credential.Client.status()
                enrolled = bool(value and value.get("accepted") is True and value.get("enrollment") == "ready")
            except (credential.Refused, credential.Closed, OSError):
                pass
            try:
                protocol, = bus.call_sync("org.gnome.Shell", PATH, INTERFACE, "Version", None,
                    GLib.VariantType("(u)"), Gio.DBusCallFlags.NONE, 500, None).unpack()
                extension_ready = protocol == 1
            except GLib.Error:
                pass
            blocker = ("gnome_covered_extension_enable_or_relogin" if not extension_ready else
                       "gnome_credential_enrollment_required" if not enrolled else None)
        except UnlockRefused as error:
            blocker = str(error)
        except (OSError, ValueError, GLib.Error):
            pass

        def apply():
            self.probe_pending = False
            self.probe_observed = time.monotonic()
            self.supported, self.enrolled, self.extension_ready = supported, enrolled, extension_ready
            self.blocker = blocker
            if not self.owner.stopped:
                self.owner.refresh_availability()
                self.owner.changed()
            return False
        self.owner.scheduler.post(apply)

    def require_settings(self):
        if (not self.owner.unlocked or self.owner.covered is not None or self.owner.grants.updating
                or time.monotonic() - self.owner.session_observed > 2 or self.setup_process
                or any(surface.get("mode", "off") != "off" and not surface.get("expired")
                       for surface in self.owner.grants.view.get("surfaces", {}).values())):
            raise ValueError("Unlock the console and turn access Off before changing covered access")

    def set_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("Choose whether to allow covered access")
        if enabled:
            self.require_settings()
            if not self.permission_ready:
                raise ValueError("Finish covered access setup first")
            self.path.touch(mode=0o600, exist_ok=True)
        else:
            self.owner.stop_access()
            self.path.unlink(missing_ok=True)
        self.enabled = enabled
        self.owner.refresh_availability()

    def setup(self, *, remove=False):
        self.require_settings()
        if not self.supported:
            raise ValueError("Use the Machine Control Debian package on Ubuntu GNOME 50 Wayland")
        if not remove:
            settings = Gio.Settings.new("org.gnome.shell")
            if settings.get_boolean("disable-user-extensions"):
                raise ValueError("Turn on GNOME extensions before setting up covered access")
            disabled = settings.get_strv("disabled-extensions")
            if UUID in disabled and not settings.set_strv("disabled-extensions", [item for item in disabled if item != UUID]):
                raise ValueError("Machine Control could not enable the GNOME extension")
            extensions = settings.get_strv("enabled-extensions")
            if UUID not in extensions and not settings.set_strv("enabled-extensions", [*extensions, UUID]):
                raise ValueError("Machine Control could not enable the GNOME extension")
            Gio.Settings.sync()
        process = subprocess.Popen(
            ["/usr/bin/python3", "-I", "-B", str(Path(__file__).with_name("locked-use-dialog.py")),
             "remove" if remove else "setup"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        self.setup_process = process
        self.cancel_setup.clear()
        self.error = None

        def wait():
            try:
                value = json.loads(read_reply(process, self.cancel_setup, time.monotonic() + 180, 2048))
            except (OSError, ValueError):
                value = {}
            def finished():
                self.setup_process = None
                if value.get("accepted") is True:
                    self.enrolled = not remove
                    if remove:
                        self.enabled = False
                        self.path.unlink(missing_ok=True)
                    elif not self.owner.stopped and (not self.owner.activity.installed or not self.owner.activity.motion_supported):
                        try:
                            self.owner.prepare_activity()
                        except (OSError, ValueError):
                            self.error = "Install the physical activity observer in Permissions"
                elif value.get("errorCode") != "cancelled":
                    self.error = ("The local password was refused" if value.get("errorCode") in
                                  {"unlock_credential_invalid", "locked_credential_rejected"}
                                  else "Covered access setup was not confirmed")
                if not self.owner.stopped:
                    self.refresh()
                    self.owner.changed()
                return False
            self.owner.scheduler.post(finished)
        threading.Thread(target=wait, daemon=True, name="mc-locked-use-setup").start()

    def authenticate(self, console, cover, seconds):
        try:
            return credential.Client.authenticate(console.session_id, console.started,
                cover.connection.get_unique_name(), cover.identifier, seconds)
        except credential.Refused as error:
            raise UnlockRefused(error.code) from None

    def ended(self, task):
        self.paused |= task.local_input
        self.error = ("Could not verify that GNOME relocked" if not task.relock_verified else
                      "GNOME ended the covered task: " + task.reason if task.reason and not task.local_input else None)
        self.refresh()

    def manual_unlock(self):
        # Resume only after the native lock and a later local unlock.
        self.paused = False

    def state(self):
        task = self.owner.covered
        phase = "ready" if self.ready else "unavailable"
        if task:
            phase = ("relock_unverified" if task.finished.is_set() else
                     "relocking" if task.cancelled.is_set() else
                     "active" if task.active.is_set() else "unlocking")
        return dict(supported=self.supported, enabled=self.enabled, permissionReady=self.permission_ready,
                    phase=phase, setupState="enrolling" if self.setup_process else "idle",
                    setupError=self.error, helperApproval="installed" if self.enrolled else "required",
                    helperHealthy=self.enrolled, helperNote=self.blocker,
                    credentialSource="service_enrolled_password" if self.enrolled else "none",
                    pausedUntilManualUnlock=self.paused, controlSessionId=self.owner.covered_session)

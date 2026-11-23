"""Common request names reach the appliance broker and activation unchanged."""

import base64
import importlib
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

UI = Path(__file__).resolve().parents[1] / "guests/ubuntu/ui"


def load():
    """Import the resident with GI and AT-SPI stubbed for portable checks."""
    gi = types.ModuleType("gi")
    gi.require_version = lambda *_: None
    repository = types.ModuleType("gi.repository")
    repository.Gdk = types.SimpleNamespace()
    repository.Gio = types.SimpleNamespace()
    repository.GLib = types.SimpleNamespace()
    gi.repository = repository
    linuxui = types.ModuleType("linuxui")
    linuxui.UIError = type("UIError", (Exception,), {})
    modules = {"gi": gi, "gi.repository": repository, "linuxui": linuxui}
    with mock.patch.dict(sys.modules, modules):
        sys.path.insert(0, str(UI))
        try:
            sys.modules.pop("linuxcontrol", None)
            return importlib.import_module("linuxcontrol")
        finally:
            sys.path.remove(str(UI))
            sys.modules.pop("linuxcontrol", None)


linuxcontrol = load()


class Recorder(linuxcontrol.Resident):
    def __init__(self):
        super().__init__()
        self.sent = []

    def display_geometry(self):
        return {"x": 0, "y": 0, "width": 1280, "height": 800}

    def call_input(self, request):
        self.sent.append(request)
        return {"accepted": True}


class CommonFieldTests(unittest.TestCase):
    def test_scroll_forwards_common_deltas(self):
        resident = Recorder()
        result = resident.handle(
            {"operation": "input.scroll", "deltaX": 0, "deltaY": -3}
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(resident.sent, [{"operation": "scroll", "dx": 0, "dy": -3}])

    def test_drag_starts_at_common_x_y(self):
        resident = Recorder()
        result = resident.handle(
            {"operation": "input.drag", "x": 10, "y": 20, "x2": 300, "y2": 40}
        )
        self.assertTrue(result["accepted"], result)
        (sent,) = resident.sent
        self.assertEqual(
            {key: sent[key] for key in ("operation", "x1", "y1", "x2", "y2")},
            {"operation": "drag", "x1": 10, "y1": 20, "x2": 300, "y2": 40},
        )
        self.assertNotIn("x", sent)

    def test_historical_names_still_work(self):
        resident = Recorder()
        resident.handle({"operation": "input.scroll", "dx": 1, "dy": 2})
        resident.handle(
            {"operation": "input.drag", "x1": 1, "y1": 2, "x2": 3, "y2": 4}
        )
        self.assertEqual(resident.sent[0], {"operation": "scroll", "dx": 1, "dy": 2})
        self.assertEqual(resident.sent[1]["x1"], 1)

    def test_conflicting_duplicates_are_refused_before_dispatch(self):
        for request in (
            {"operation": "input.scroll", "deltaY": 3, "dy": -3},
            {"operation": "input.drag", "x": 1, "x1": 2, "y": 0, "x2": 5, "y2": 5},
            {"operation": "application.activate", "applicationId": "a", "desktopId": "b"},
        ):
            resident = Recorder()
            result = resident.handle(request)
            self.assertFalse(result["accepted"])
            self.assertEqual(result["errorCode"], "invalid_request")
            self.assertEqual(resident.sent, [])

    def test_equal_duplicates_are_accepted(self):
        resident = Recorder()
        result = resident.handle(
            {"operation": "input.scroll", "deltaY": 2, "dy": 2, "deltaX": 0}
        )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(resident.sent[0]["dy"], 2)

    def test_application_id_selects_desktop_activation(self):
        resident = Recorder()
        completed = types.SimpleNamespace(returncode=0, stderr=b"")
        with mock.patch.object(linuxcontrol.subprocess, "run", return_value=completed) as run:
            result = resident.handle(
                {"operation": "application.activate", "applicationId": "org.example.App"}
            )
        self.assertTrue(result["accepted"], result)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/gtk-launch", "org.example.App"])
        self.assertEqual(result["data"]["desktopId"], "org.example.App")


class StatusTests(unittest.TestCase):
    def status(self, active):
        resident = Recorder()
        reply = types.SimpleNamespace(unpack=lambda: (active,))
        bus = types.SimpleNamespace(call_sync=lambda *args: reply)
        if isinstance(active, Exception):
            bus = types.SimpleNamespace(call_sync=mock.Mock(side_effect=active))
        gio = types.SimpleNamespace(
            bus_get_sync=lambda *_: bus,
            BusType=types.SimpleNamespace(SESSION=1),
            DBusCallFlags=types.SimpleNamespace(NONE=0),
        )
        roots = mock.patch.object(
            linuxcontrol.linuxui, "desktop", create=True, return_value=None
        )
        apps = mock.patch.object(
            linuxcontrol.linuxui, "application_roots", create=True, return_value=[]
        )
        with mock.patch.object(linuxcontrol, "Gio", gio), roots, apps:
            return resident.handle({"operation": "status"})["data"]

    def test_desktop_state_follows_the_screen_shield(self):
        self.assertEqual(self.status(True)["desktopState"], "locked")
        self.assertEqual(self.status(False)["desktopState"], "unlocked")
        self.assertEqual(self.status(RuntimeError("no bus"))["desktopState"], "unknown")

    def test_common_deployment_describes_the_standing_appliance(self):
        deployment = self.status(False)["deployment"]
        self.assertEqual(deployment["policy"]["protectedAdministration"], False)
        self.assertEqual(deployment["availability"], {"paused": False, "blockingReasons": []})
        self.assertIs(deployment["browserOnlyWhileLocked"], False)


class CaptureTests(unittest.TestCase):
    PNG = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jR0YAAAAASUVORK5CYII="
    )

    def test_route_selects_native_shortcut_on_gnome_50(self):
        for version, route in (("50.1", linuxcontrol.SHELL_CAPTURE_ROUTE),
                               ("46.0", linuxcontrol.CAPTURE_ROUTE)):
            with self.subTest(version=version), mock.patch.object(
                    linuxcontrol.subprocess, "check_output", return_value=f"GNOME Shell {version}\n"):
                self.assertEqual(Recorder().capture_route, route)

    @unittest.skipUnless(hasattr(os, "getuid"), "Screenshot trust check requires POSIX ownership")
    def test_shell_capture_returns_the_new_complete_screenshot(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            pictures = home / "Screenshots"
            pictures.mkdir()
            (pictures / "old.png").write_bytes(b"old screenshot")
            resident = Recorder()
            resident.capture_route = linuxcontrol.SHELL_CAPTURE_ROUTE

            def key(request):
                self.assertEqual(request, {"operation": "key", "key": "alt+sysrq"})
                (pictures / "fresh.png").write_bytes(self.PNG)
                return {"accepted": True}

            settings = types.SimpleNamespace(get_strv=lambda _: ["<Alt>Print"],
                                              get_boolean=lambda _: False)
            gio = types.SimpleNamespace(Settings=types.SimpleNamespace(new=lambda _: settings))
            glib = types.SimpleNamespace(get_user_special_dir=lambda _: str(home),
                                         UserDirectory=types.SimpleNamespace(DIRECTORY_PICTURES=0))
            with (mock.patch.object(linuxcontrol, "Gio", gio),
                  mock.patch.object(linuxcontrol, "GLib", glib),
                  mock.patch.object(linuxcontrol, "ARTIFACT_DIRECTORY", home / "artifacts"),
                  mock.patch.object(resident, "desktop_state", return_value="unlocked"),
                  mock.patch.object(resident, "call_input", side_effect=key)):
                result = resident.handle({"operation": "capture", "target": "active_window"})
            self.assertTrue(result["accepted"], result)
            self.assertEqual(result["actualRoute"], linuxcontrol.SHELL_CAPTURE_ROUTE)
            self.assertEqual(result["fidelity"], "pixel_exact_active_window")
            self.assertTrue(result["data"]["clipboardImageSideEffect"])
            self.assertEqual(Path(result["data"]["artifact"]["guestPath"]).read_bytes(), self.PNG)

    def test_capture_refuses_locked_session_without_input(self):
        resident = Recorder()
        with mock.patch.object(resident, "desktop_state", return_value="locked"):
            result = resident.handle({"operation": "capture"})
        self.assertFalse(result["accepted"])
        self.assertEqual(result["errorCode"], "capture_unavailable")
        self.assertEqual(resident.sent, [])

    def test_unobserved_capture_reports_delivered_shortcut(self):
        resident = Recorder()
        resident.capture_route = linuxcontrol.SHELL_CAPTURE_ROUTE
        failure = linuxcontrol.UnverifiedCapture("capture_failed", "No usable screenshot")
        with tempfile.TemporaryDirectory() as root:
            with (mock.patch.object(linuxcontrol, "ARTIFACT_DIRECTORY", Path(root)),
                  mock.patch.object(resident, "desktop_state", return_value="unlocked"),
                  mock.patch.object(resident, "shell_capture", side_effect=failure)):
                result = resident.handle({"operation": "capture"})
            self.assertEqual(list(Path(root).iterdir()), [])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["actualRoute"], linuxcontrol.SHELL_CAPTURE_ROUTE)
        self.assertEqual(result["delivery"], "confirmed")
        self.assertEqual(result["effect"], "unverifiable")


if __name__ == "__main__":
    unittest.main()

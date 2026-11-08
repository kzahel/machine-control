import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from browser_preference import BrowserPreference
from session import console_elsewhere, identity, inactive_own_logon, same_logon


class LockedBrowserTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "fchmod"), "Preference persistence requires POSIX modes")
    def test_preference_persists_without_authority(self):
        with tempfile.TemporaryDirectory() as root:
            value = BrowserPreference(root, "fixture")
            self.assertFalse(value.enabled)
            value.set(True)
            self.assertTrue(BrowserPreference(root, "fixture").enabled)
            self.assertEqual(value.path.stat().st_mode & 0o777, 0o600)
            value.path.write_text('broken')
            self.assertFalse(BrowserPreference(root, "fixture").enabled)

    def test_only_active_graphical_logon_is_eligible(self):
        uid = 1001
        properties = {"Id": "fixture", "TimestampMonotonic": 1, "Active": True,
                      "Type": "wayland", "Class": "user", "User": (uid, "/user")}
        self.assertIsNotNone(identity(properties, ":1.2", uid))
        for name, replacement in [("Active", False), ("Type", "tty"), ("Class", "greeter"),
                                  ("User", (uid+1, "/other")), ("TimestampMonotonic", 0), ("Id", "")]:
            self.assertIsNone(identity({**properties, name: replacement}, ":1.2", uid))

    def test_console_identity_is_the_login_not_the_screensaver_owner(self):
        login = ("fixture", 1, ":1.2")
        # A gnome-shell restart replaces the screensaver bus owner only.
        self.assertTrue(same_logon(login, ("fixture", 1, ":1.9")))
        self.assertFalse(same_logon(login, ("fixture", 2, ":1.2")))
        self.assertFalse(same_logon(login, None))
        self.assertFalse(console_elsewhere([login, None], ("fixture", 1, ":1.9")))
        self.assertTrue(console_elsewhere([login, None], ("other", 5, ":1.2")))
        self.assertFalse(console_elsewhere([login], None), "Unknown is not proof of replacement")
        self.assertFalse(console_elsewhere([None, None], ("other", 5, ":1.2")))

    def test_inactive_own_logon_is_another_session_on_the_seat(self):
        uid = 1001
        properties = {"Id": "fixture", "Active": False, "Class": "user", "User": (uid, "/user")}
        self.assertTrue(inactive_own_logon(properties, uid))
        self.assertFalse(inactive_own_logon({**properties, "Active": True}, uid))
        self.assertFalse(inactive_own_logon({**properties, "Active": None}, uid))
        self.assertFalse(inactive_own_logon({**properties, "User": (uid + 1, "/other")}, uid))

    def test_console_change_pauses_and_never_revokes_consent(self):
        import ast
        from types import SimpleNamespace
        source = Path(__file__).resolve().parents[2] / "desktop/native/linux/desktop.py"
        cls = next(n for n in ast.parse(source.read_text()).body
                   if isinstance(n, ast.ClassDef) and n.name == "Desktop")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "apply_session")
        import session as desktop_session
        namespace = {"desktop_session": desktop_session, "time": __import__("time")}
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"), namespace)
        events, stops = [], []
        login = ("fixture", 1, ":1.2")
        owner = SimpleNamespace(configuration_sessions={"desktop": login, "browser": login},
            grants=SimpleNamespace(console_elsewhere=False), journal=SimpleNamespace(event=events.append),
            portal=SimpleNamespace(state="off", close=lambda: None), refresh_availability=lambda: None,
            stop_access=stops.append)
        apply = lambda *a: namespace["apply_session"](owner, *a)
        apply(True, False, ("fixture", 1, ":1.9"))
        self.assertFalse(owner.grants.console_elsewhere)
        apply(False, False, None, True)
        self.assertTrue(owner.grants.console_elsewhere)
        apply(True, False, ("other", 5, ":1.2"))
        self.assertTrue(owner.grants.console_elsewhere)
        apply(True, False, login)
        self.assertFalse(owner.grants.console_elsewhere)
        self.assertEqual(events, ["access.console_elsewhere", "access.console_returned"])
        self.assertEqual(stops, [])
        self.assertEqual(owner.configuration_sessions, {"desktop": login, "browser": login})


if __name__ == "__main__":
    unittest.main()

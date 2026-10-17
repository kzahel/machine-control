import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from browser_preference import BrowserPreference
from grants import Grants
from session import identity


class LockedBrowserTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.grants = Grants(clock=lambda: self.now)
        self.grants.set_ready(True, session="session-one")

    def test_mixed_scope_retention_and_locked_approval(self):
        value = self.grants
        value.configure_browser_while_locked(True)
        self.assertEqual(value.authorize("browser.tabs"), "approval_required")
        value.arm(["observe", "control", "browser"], 120)
        grant = value.grant
        value.set_ready(False, locked=True, session="session-one")
        self.assertIs(value.grant, grant)
        self.assertEqual(value.state()["deployment"]["effectiveScopes"], ["browser"])
        self.assertIsNone(value.authorize("browser.tabs"))
        for operation in ["snapshot", "capture", "input.key"]:
            self.assertEqual(value.authorize(operation), "desktop_locked_browser_only")
        self.assertEqual(value.authorize("browser.eval"), "approval_required")
        replies = []
        for selected in [["browser"], ["control"], ["devtools"]]:
            value.request({"scopes": selected, "reason": "fixture"}, "fixture", lambda ok, error: replies.append((ok, error)))
        self.assertEqual(replies, [(True, None), (False, "approval_unavailable_while_locked"), (False, "approval_unavailable_while_locked")])
        value.pause(True)
        self.assertEqual(value.authorize("browser.tabs"), "access_paused")
        value.pause(False)
        self.assertIsNone(value.authorize("browser.tabs"))
        value.configure_browser_while_locked(False)
        self.assertIsNone(value.grant)

    def test_default_off_expiry_stop_and_session_replacement(self):
        value = self.grants
        value.arm(["browser"], 120)
        value.set_ready(False, locked=True, session="session-one")
        self.assertIsNone(value.grant)
        for change in ["expiry", "stop", "replacement", "unknown"]:
            value.set_ready(True, session="session-one")
            value.configure_browser_while_locked(True)
            value.arm(["browser", "devtools"], 120)
            value.set_ready(False, locked=True, session="session-one")
            self.assertIsNone(value.authorize("browser.eval"))
            if change == "expiry":
                self.now += 121
                value.refresh()
            elif change == "stop":
                value.stop()
            else:
                value.set_ready(False, locked=True, session="replacement" if change == "replacement" else None)
            self.assertIsNone(value.grant, change)

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
        properties = {"Id": "fixture", "TimestampMonotonic": 1, "Active": True,
                      "Type": "wayland", "Class": "user", "User": (os.getuid(), "/user")}
        self.assertIsNotNone(identity(properties, ":1.2", os.getuid()))
        for name, replacement in [("Active", False), ("Type", "tty"), ("Class", "greeter"),
                                  ("User", (os.getuid()+1, "/other")), ("TimestampMonotonic", 0), ("Id", "")]:
            self.assertIsNone(identity({**properties, name: replacement}, ":1.2", os.getuid()))


if __name__ == "__main__":
    unittest.main()

import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from browser_preference import BrowserPreference
from session import identity


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


if __name__ == "__main__":
    unittest.main()

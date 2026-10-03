import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from updates import Updates


class UpdateMailboxTests(unittest.TestCase):
    def test_initialization_coalescing_and_busy_exclusion(self):
        updates = Updates()
        with self.assertRaises(ValueError):
            updates.request(True)
        idle = {"checking": False, "installing": False, "phase": "idle"}
        self.assertFalse(updates.sync(idle))
        updates.request(True)
        updates.request(True)
        self.assertTrue(updates.sync(idle))
        self.assertTrue(updates.request()["update"]["checking"])
        self.assertFalse(updates.sync(idle))
        for busy in ("checking", "installing"):
            self.assertFalse(updates.sync({**idle, busy: True}))
            self.assertFalse(updates.request(True)["queued"])
            self.assertFalse(updates.sync(idle))

    def test_snapshots_are_owned_and_status_never_queues(self):
        updates = Updates()
        source = {"availableVersion": "1.2.3"}
        updates.sync(source)
        source["availableVersion"] = "other"
        reply = updates.request()
        self.assertEqual(reply["update"]["availableVersion"], "1.2.3")
        reply["update"]["availableVersion"] = "changed"
        self.assertEqual(updates.request()["update"]["availableVersion"], "1.2.3")
        self.assertFalse(updates.sync({}))


if __name__ == "__main__":
    unittest.main()

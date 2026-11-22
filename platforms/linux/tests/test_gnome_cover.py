"""Fence cover readiness and cleanup to the live D-Bus owner."""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

TEST_PATH = Path(__file__).resolve()
sys.path.insert(0, str(TEST_PATH.parents[1] / "guests/ubuntu/ui"))
sys.path.insert(0, str(TEST_PATH.parents[3] / "desktop/native/linux"))
from gnome_cover import GnomeCover, INTERFACE, PATH, Takeover
from gnome_unlock import Console, UnlockRefused


class CoverTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        self.cover = GnomeCover(self.provider, Mock(), takeover=Mock())
        self.cover.connection = Mock()
        self.cover.shell = ":1.7"
        self.cover.identifier = "lease"

    def test_readiness_checks_the_exact_owner_lease(self):
        self.provider.call.return_value = (True,)
        self.assertTrue(self.cover.covered())
        self.provider.call.assert_called_once_with(
            self.cover.connection, ":1.7", PATH, INTERFACE,
            "Check", ("(s)", ("lease",)), "(b)", timeout=500,
        )
        self.cover.lost.set()
        self.assertFalse(self.cover.covered())
        self.assertEqual(self.provider.call.call_count, 1)

    def test_close_disconnects_even_if_end_has_no_reply(self):
        self.provider.call.side_effect = UnlockRefused("gnome_console_unavailable")
        original = self.cover.connection
        self.cover.close()
        self.assertTrue(self.cover.stop_renewing.is_set())
        self.assertIsNone(self.cover.connection)
        original.close_sync.assert_called_once_with(None)

    def test_observer_refusal_precedes_acquiring_cover(self):
        cover = GnomeCover(self.provider, Mock(), takeover=Mock())
        cover.takeover.prepare.side_effect = UnlockRefused("gnome_cover_input_observer_unavailable")
        with self.assertRaisesRegex(UnlockRefused, "gnome_cover_input_observer_unavailable"):
            cover.open()
        self.assertIsNone(cover.connection)
        self.provider.call.assert_not_called()

    def test_motion_and_observer_replacement_are_distinct(self):
        takeover = Takeover(Console("/fixture", "local", 100, ":1.2"))
        takeover.baseline = ("1" * 32, "2" * 32, "3" * 32)
        value = dict(healthy=True, observedThroughUptime=100,
                     generation="1" * 32, activityToken="2" * 32, motionToken="4" * 32)
        with patch("gnome_cover.time.monotonic", return_value=100), patch(
                "gnome_cover.read_sample", return_value=value):
            self.assertEqual(takeover.state(), "local_input")
            value["generation"] = "5" * 32
            self.assertEqual(takeover.state(), "unavailable")


if __name__ == "__main__":
    unittest.main()

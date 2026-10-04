#!/usr/bin/env python3
"""Deterministic grant boundary tests; no GTK, portal or appliance privilege."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from grants import Grants


class GrantsTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.broker = Grants(clock=lambda: self.now)
        self.broker.set_ready(True)
        self.replies = []

    def request(self, **extra):
        self.broker.request({"scopes": ["observe", "control"], "reason": "Fixture test",
                             "durationSeconds": 30, "timeoutSeconds": 5, **extra},
                            "pid 123", lambda ok, error: self.replies.append((ok, error)))

    def test_off_and_scope(self):
        self.assertEqual(self.broker.authorize("snapshot"), "approval_required")
        self.broker.arm(["observe"], 30)
        self.assertIsNone(self.broker.authorize("snapshot"))
        self.assertEqual(self.broker.authorize("input.key"), "approval_required")
        self.assertEqual(self.broker.authorize("shell"), "unsupported_operation")

    def test_request_pause_and_narrow(self):
        self.broker.arm(["observe", "control"], 60)
        self.request(scopes=["observe", "control", "browser"])
        self.assertEqual(self.broker.authorize("input.click"), "approval_prompt_visible")
        self.assertIsNone(self.broker.authorize("snapshot"))
        pending = self.broker.pending
        with self.assertRaises(ValueError):
            self.broker.decide(pending["id"], True, ["devtools"], 30)
        with self.assertRaises(ValueError):
            self.broker.decide(pending["id"], True, ["observe"], 31)
        self.broker.decide(pending["id"], True, ["observe"], 10)
        self.assertEqual(self.replies, [(True, None)])
        self.assertEqual(self.broker.authorize("input.click"), "approval_required")

    def test_denial_and_timeout(self):
        self.request()
        self.broker.decide(self.broker.pending["id"], False, None, 0)
        self.assertEqual(self.replies[-1], (False, "approval_denied"))
        self.request()
        self.now = 5
        self.broker.refresh()
        self.assertEqual(self.replies[-1], (False, "approval_timeout"))

    def test_expiry_and_stale_generation(self):
        self.broker.arm(["control"], 2)
        generation = self.broker.generation
        self.now = 2
        self.assertEqual(self.broker.authorize("input.text", generation), "stale_generation")
        self.assertIsNone(self.broker.grant)

    def test_session_loss_recursive_notification(self):
        self.broker.changed = lambda: self.broker.set_ready(False)
        self.broker.arm(["observe"], 5)
        self.assertFalse(self.broker.ready)
        self.assertIsNone(self.broker.grant)

    def test_stop_ends_pending(self):
        self.request()
        self.broker.stop()
        self.assertEqual(self.replies[-1], (False, "stopped_by_person"))
        self.assertIsNone(self.broker.pending)

    def test_update_excludes_access(self):
        self.broker.arm(["observe"], 60)
        with self.assertRaises(ValueError):
            self.broker.prepare_update()
        self.broker.stop()
        self.request()
        with self.assertRaises(ValueError):
            self.broker.prepare_update()
        self.broker.stop()
        self.broker.prepare_update()
        self.assertEqual(self.broker.authorize("snapshot"), "update_in_progress")
        with self.assertRaises(ValueError):
            self.broker.arm(["observe"], 60)

    def test_invalid_values(self):
        for seconds in [True, 0, 3601, "30"]:
            with self.assertRaises(ValueError):
                self.broker.arm(["observe"], seconds)
        for value in [None, [], ["shell"], "observe"]:
            with self.assertRaises(ValueError):
                self.broker.arm(value, 30)

    def test_until_stopped_has_no_expiry_and_retains_scopes(self):
        self.broker.arm(["observe"], 0, "until_stopped")
        self.now = 365 * 24 * 3600
        state = self.broker.state()
        self.assertTrue(state["manualUntilStoppedSupported"])
        self.assertEqual(state["deployment"]["grant"]["lifetime"], "until_stopped")
        self.assertIsNone(state["deployment"]["grant"]["remainingSeconds"])
        self.assertIsNone(self.broker.authorize("snapshot"))
        self.assertEqual(self.broker.authorize("input.key"), "approval_required")
        with self.assertRaises(ValueError):
            self.broker.prepare_update()
        generation = self.broker.generation
        self.broker.stop()
        self.assertEqual(self.broker.authorize("snapshot", generation), "stale_generation")
        self.assertEqual(self.broker.authorize("snapshot"), "approval_required")
        self.broker.prepare_update()
        with self.assertRaises(ValueError):
            self.broker.arm(["observe"], 0, "until_stopped")

    def test_until_stopped_session_loss_and_timed_replacement(self):
        self.broker.arm(["observe"], 0, "until_stopped")
        self.broker.set_ready(False)
        self.assertIsNone(self.broker.grant)
        self.broker.set_ready(True)
        self.assertEqual(self.broker.authorize("snapshot"), "approval_required")
        self.broker.arm(["observe"], 0, "until_stopped")
        self.broker.arm(["observe"], 30)
        self.assertEqual(self.broker.state()["deployment"]["grant"]["lifetime"], "timed")
        self.now = 30
        self.assertEqual(self.broker.authorize("snapshot"), "approval_required")

    def test_until_stopped_keeps_public_approvals_bounded(self):
        self.broker.arm(["observe"], 0, "until_stopped")
        with self.assertRaises(ValueError):
            self.request(scopes=["observe"], durationSeconds=0, lifetime="until_stopped")
        self.request(lifetime="until_stopped")
        with self.assertRaises(ValueError):
            self.broker.arm(["observe"], 0, "until_stopped")
        with self.assertRaises(ValueError):
            self.broker.decide(self.broker.pending["id"], True, ["observe"], 0)
        self.broker.decide(self.broker.pending["id"], True, ["observe"], 10)
        self.now = 10
        self.assertEqual(self.broker.authorize("snapshot"), "approval_required")

    def test_until_stopped_rejects_invalid_lifetime_and_scopes(self):
        for lifetime in [None, "", "forever", True]:
            with self.assertRaises(ValueError):
                self.broker.arm(["observe"], 30, lifetime)
        for selected in [[], ["shell"], None]:
            with self.assertRaises(ValueError):
                self.broker.arm(selected, 0, "until_stopped")


if __name__ == "__main__":
    unittest.main()

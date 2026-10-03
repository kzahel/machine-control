from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "providers/claims"))
import admission
import claims


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.clock = time.monotonic()
        self.patch = mock.patch.object(admission.time, "monotonic", side_effect=lambda:self.clock)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temporary.cleanup()

    def args(self, operation="acquire", identity="exact-fixture", *extra):
        return claims.parser().parse_args(["--state-dir", str(self.directory),
            operation, "--provider", "fixture", "--resource-id", identity,
            *(["--reason", "Fixture task", "--claimant-authority", "fixture", "--claimant-id", "caller"]
              if operation == "acquire" else []), *extra])

    def owner(self, identity="exact-fixture", **overrides):
        a = admission.Authority(self.args(identity=identity), clock=lambda:self.clock)
        options = dict(reason="Fixture task", claimantAuthority="fixture", claimantId="caller", waitSeconds=300)
        options.update(overrides)
        return a, a.submit(options)

    def test_fifo_aliases_disjoint_resources_and_no_legacy_offer_theft(self):
        first, offer = self.owner()
        second, waiting = self.owner()
        third, disjoint = self.owner("another-fixture")
        self.assertEqual([offer["state"], waiting["state"], disjoint["state"]],
                         ["offered", "waiting_for_resource", "offered"])
        with self.assertRaisesRegex(claims.ClaimError, "queued owner"):
            claims.command_acquire(self.args())
        first.cancel()
        offer = second.inspect()
        active = second.accept(offer["offerGeneration"])
        self.assertEqual(active["state"], "active")
        self.assertEqual(active["claim"]["generation"], 1)
        first.close()  # a dead owner cannot release its successor
        self.assertEqual(second.inspect()["state"], "active")

    def test_status_is_read_only_late_heartbeat_cannot_restore_position(self):
        held = claims.command_acquire(self.args())["data"]["claim"]
        owner, _ = self.owner()
        self.clock += 59
        owner.inspect()
        self.clock += 2
        expired = owner.inspect(heartbeat=True)
        self.assertEqual(expired["terminalReason"], "heartbeat_expired")
        claims.command_release(self.args("release", "exact-fixture", "--claim-id", held["claimId"]))
        self.assertEqual(owner.inspect()["state"], "ended")
        fresh, offer = self.owner()
        self.assertEqual(offer["state"], "offered")
        self.assertEqual(owner.inspect()["state"], "ended")

    def test_useful_deadline_survives_heartbeats(self):
        claims.command_acquire(self.args())
        owner, _ = self.owner(waitSeconds=10)
        self.clock += 9
        owner.inspect(heartbeat=True)
        self.clock += 2
        self.assertEqual(owner.inspect()["terminalReason"], "wait_deadline_exceeded")

    def test_offer_expiry_refuses_accept_and_never_creates_a_claim(self):
        owner, offer = self.owner()
        self.clock += 16
        with self.assertRaises(claims.ClaimError):
            owner.accept(offer["offerGeneration"])
        self.assertEqual(owner.inspect()["terminalReason"], "activation_offer_expired")
        self.assertEqual(claims.command_status(self.args("status"))["data"]["state"], "available")

    def test_active_heartbeat_expiry_fences_before_claim_check(self):
        owner, offer = self.owner()
        active = owner.accept(offer["offerGeneration"])
        self.clock += 6
        with self.assertRaises(claims.ClaimError):
            claims.command_check(self.args("check", "exact-fixture", "--claim-id", active["claim"]["claimId"]))
        self.assertEqual(owner.inspect()["terminalReason"], "heartbeat_expired")
        self.assertEqual(claims.command_status(self.args("status"))["data"]["state"], "available")

    def test_keepalive_does_not_renew_underlying_claim(self):
        owner, offer = self.owner()
        active = owner.accept(offer["offerGeneration"])
        for _ in range(5):
            self.clock += 4
            self.assertEqual(owner.inspect(heartbeat=True)["claim"]["expiresAt"], active["claim"]["expiresAt"])

    def test_replacement_is_not_released_by_old_owner(self):
        owner, offer = self.owner()
        active = owner.accept(offer["offerGeneration"])
        claims.command_release(self.args("release", "exact-fixture", "--claim-id", active["claim"]["claimId"]))
        replacement = claims.command_acquire(self.args())["data"]["claim"]
        owner.close()
        self.assertEqual(claims.command_status(self.args("status"))["data"]["claim"]["claimId"], replacement["claimId"])

    def test_crash_between_claim_and_queue_commit_is_recoverable(self):
        owner, offer = self.owner()
        write = claims.write_record
        def fail_active_queue(path, value):
            if path.name == "queue.json" and any(v["state"] == "active" for v in value["entries"]):
                raise OSError("fixture simulated interrupted commit")
            return write(path, value)
        with mock.patch.object(claims, "write_record", side_effect=fail_active_queue):
            with self.assertRaises(OSError):
                owner.accept(offer["offerGeneration"])
        pending = admission.load(self.directory)["entries"][0]
        self.assertEqual(pending["state"], "activating")
        self.clock += 6
        self.assertEqual(claims.command_status(self.args("status"))["data"]["state"], "available")
        self.assertEqual(owner.inspect()["state"], "ended")

    def test_clock_rewind_and_corrupt_state_fail_closed(self):
        owner, _ = self.owner()
        self.clock -= 20
        self.assertEqual(owner.inspect()["terminalReason"], "claim_clock_changed")
        (self.directory / "queue.json").write_text("{}")
        with self.assertRaises(claims.ClaimError):
            claims.command_acquire(self.args())

    def test_duplicate_parameters_and_bounded_capacity(self):
        owner, offer = self.owner()
        self.assertEqual(owner.submit(owner.options)["offerGeneration"], offer["offerGeneration"])
        with self.assertRaises(claims.ClaimError):
            owner.submit({**owner.options, "reason":"Changed"})
        for i in range(255):
            self.owner(f"fixture-{i}")
        with self.assertRaises(claims.ClaimError):
            self.owner("overflow")
        self.assertEqual(len(admission.load(self.directory)["entries"]), 256)

    def test_version_zero_remains_fail_fast_and_version_one_is_explicit(self):
        args = claims.parser().parse_args(["--state-dir", str(self.directory), "capabilities"])
        self.assertFalse(claims.command_capabilities(args)["queueing"])
        args.version = 1
        self.assertTrue(claims.command_capabilities(args)["queueing"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[3]
CLAIMS_PATH = ROOT / "providers" / "claims" / "claims.py"
SPEC = importlib.util.spec_from_file_location("machine_control_claims", CLAIMS_PATH)
assert SPEC is not None and SPEC.loader is not None
claims = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(claims)


class ClaimStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def args(self, command: str, **overrides: object) -> object:
        values: dict[str, object] = {
            "state_dir": str(self.directory),
            "minimum_duration": 60,
            "default_duration": 1800,
            "maximum_duration": 14400,
            "maximum_lifetime": 14400,
            "provider": "fixture",
            "resource_id": "private-resource",
            "duration_seconds": None,
            "reason": "test the fixture",
            "claimant_authority": "test-runner",
            "claimant_id": "case-1",
            "session_id": "session-1",
            "label": "fixture claim",
            "metadata_json": '{"suite":"claims"}',
            "claim_id": None,
            "command": command,
        }
        values.update(overrides)
        return type("Arguments", (), values)()

    def acquire(self, **overrides: object) -> dict[str, object]:
        with mock.patch.object(claims, "utc_now", return_value=self.now):
            return claims.command_acquire(self.args("acquire", **overrides))

    def test_acquire_status_and_conflict_are_minimized(self) -> None:
        acquired = self.acquire()
        descriptor = acquired["data"]["claim"]
        self.assertEqual(descriptor["generation"], 1)
        self.assertEqual(descriptor["claimant"]["assurance"], "self_asserted")
        self.assertNotIn("private-resource", json.dumps(acquired))

        with mock.patch.object(claims, "utc_now", return_value=self.now):
            status = claims.command_status(self.args("status"))
        self.assertEqual(status["data"]["state"], "held")
        self.assertEqual(status["data"]["claim"]["claimId"], descriptor["claimId"])

        with self.assertRaises(claims.ClaimError) as raised:
            self.acquire(claimant_id="case-2")
        self.assertEqual(raised.exception.code, "target_claimed")
        self.assertNotIn("private-resource", json.dumps(raised.exception.data))

    def test_renew_expire_and_reacquire_fence_old_holder(self) -> None:
        acquired = self.acquire(duration_seconds=60)
        claim_id = acquired["data"]["claim"]["claimId"]
        renewed_at = self.now + timedelta(seconds=30)
        with mock.patch.object(claims, "utc_now", return_value=renewed_at):
            renewed = claims.command_renew(
                self.args("renew", claim_id=claim_id, duration_seconds=120)
            )
        self.assertEqual(renewed["data"]["claim"]["remainingSeconds"], 120)

        expired_at = renewed_at + timedelta(seconds=121)
        with mock.patch.object(claims, "utc_now", return_value=expired_at):
            with self.assertRaises(claims.ClaimError) as raised:
                claims.command_check(self.args("check", claim_id=claim_id))
            self.assertEqual(raised.exception.code, "claim_expired")
            replacement = claims.command_acquire(
                self.args("acquire", claimant_id="case-2")
            )
        self.assertEqual(replacement["data"]["claim"]["generation"], 2)
        with mock.patch.object(claims, "utc_now", return_value=expired_at):
            with self.assertRaises(claims.ClaimError) as raised:
                claims.command_check(self.args("check", claim_id=claim_id))
        self.assertEqual(raised.exception.code, "claim_mismatch")

    def test_release_is_idempotent_but_cannot_release_new_holder(self) -> None:
        acquired = self.acquire()
        claim_id = acquired["data"]["claim"]["claimId"]
        with mock.patch.object(claims, "utc_now", return_value=self.now):
            released = claims.command_release(
                self.args("release", claim_id=claim_id)
            )
            repeated = claims.command_release(
                self.args("release", claim_id=claim_id)
            )
        self.assertEqual(released["data"]["disposition"], "released")
        self.assertEqual(repeated["data"]["disposition"], "alreadyReleased")

        later = self.now + timedelta(seconds=1)
        with mock.patch.object(claims, "utc_now", return_value=later):
            replacement = claims.command_acquire(
                self.args("acquire", claimant_id="case-2")
            )
            with self.assertRaises(claims.ClaimError) as raised:
                claims.command_release(self.args("release", claim_id=claim_id))
        self.assertEqual(raised.exception.code, "claim_mismatch")
        self.assertNotEqual(
            replacement["data"]["claim"]["claimId"], claim_id
        )

    def test_exact_resource_identity_controls_contention(self) -> None:
        self.acquire()
        other = self.acquire(resource_id="other-private-resource")
        self.assertEqual(other["data"]["claim"]["generation"], 1)

    def test_clock_rollback_fails_closed(self) -> None:
        acquired = self.acquire()
        claim_id = acquired["data"]["claim"]["claimId"]
        earlier = self.now - timedelta(seconds=1)
        with mock.patch.object(claims, "utc_now", return_value=earlier):
            with self.assertRaises(claims.ClaimError) as raised:
                claims.command_check(self.args("check", claim_id=claim_id))
        self.assertEqual(raised.exception.code, "claim_clock_invalid")

    def test_metadata_and_duration_are_bounded(self) -> None:
        with self.assertRaises(claims.ClaimError) as raised:
            self.acquire(duration_seconds=59)
        self.assertEqual(raised.exception.code, "invalid_claim_duration")
        metadata = {f"key-{index}": "value" for index in range(17)}
        with self.assertRaises(claims.ClaimError) as raised:
            self.acquire(metadata_json=json.dumps(metadata))
        self.assertEqual(raised.exception.code, "invalid_claim_request")

    @unittest.skipIf(os.name == "nt", "POSIX permission assertion")
    def test_store_permissions_are_private(self) -> None:
        self.acquire()
        records = list(self.directory.glob("resource-*.json"))
        self.assertEqual(len(records), 1)
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(records[0].stat().st_mode & 0o777, 0o600)

    def test_recent_dead_lock_is_not_reclaimed(self) -> None:
        lock = self.directory / ".operation.lock"
        lock.mkdir()
        (lock / "pid").write_text("999999\n", encoding="ascii")

        with mock.patch.object(claims, "process_alive") as process_alive:
            self.assertFalse(claims.remove_stale_lock(lock))

        process_alive.assert_not_called()
        self.assertTrue(lock.is_dir())

    def test_aged_dead_lock_is_reclaimed(self) -> None:
        lock = self.directory / ".operation.lock"
        lock.mkdir()
        (lock / "pid").write_text("999999\n", encoding="ascii")
        stale_time = lock.stat().st_mtime + claims.STALE_LOCK_GRACE_SECONDS

        with (
            mock.patch.object(claims.time, "time", return_value=stale_time),
            mock.patch.object(claims, "process_alive", return_value=False),
        ):
            self.assertTrue(claims.remove_stale_lock(lock))

        self.assertFalse(lock.exists())

    def test_simultaneous_acquire_has_one_winner(self) -> None:
        processes = [
            subprocess.Popen(
                [
                    sys.executable,
                    str(CLAIMS_PATH),
                    "--state-dir",
                    str(self.directory),
                    "acquire",
                    "--provider",
                    "fixture",
                    "--resource-id",
                    "private-resource",
                    "--reason",
                    "concurrency test",
                    "--claimant-authority",
                    "fixture",
                    "--claimant-id",
                    f"process-{index}",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for index in range(6)
        ]
        results = []
        try:
            for process in processes:
                stdout, _ = process.communicate(timeout=10)
                results.append((process.returncode, json.loads(stdout)))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                process.communicate()
        winners = [value for status, value in results if status == 0]
        conflicts = [value for status, value in results if status != 0]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(conflicts), 5)
        self.assertTrue(all(
            value["errorCode"] == "target_claimed" for value in conflicts
        ), conflicts)


if __name__ == "__main__":
    unittest.main()

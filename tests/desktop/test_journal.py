"""Persistence/failure/privacy tests without a desktop or OS permissions."""
import concurrent.futures
import json
import os
import time
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "desktop/native/linux"))
from journal import Journal
from grants import Grants


@unittest.skipUnless(hasattr(os, "getuid"), "Linux journal uses POSIX ownership and modes")
class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "logs"

    def test_restart_and_unknown_intent(self):
        journal = Journal(self.root)
        self.assertTrue(journal.begin("input.text", "request-secret"))
        again = Journal(self.root)
        rows = again.query()["entries"]
        intent = next(r for r in rows if r["phase"] == "intent")
        self.assertEqual(intent["effect"], "unknown")
        self.assertNotEqual(intent["requestId"], "request-secret")
        self.assertEqual(self.root.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.root.rglob("*.jsonl")))

    def test_payloads_excluded_and_discovery_not_recorded(self):
        journal = Journal(self.root)
        secret = "SENTINEL-sensitive-payload"
        journal.begin(secret, secret)
        journal.record({"operation": "input.text", "requestId": secret, "accepted": True,
                        "text": secret, "data": {"clipboard": secret}, "message": secret,
                        "evidence": secret, "params": secret, "url": secret})
        journal.begin("status", secret)
        text = json.dumps(journal.preview())
        self.assertNotIn(secret, text)
        self.assertNotIn('"operation": "status"', text)
        exported = Path(journal.export())
        self.assertNotIn(secret, exported.read_text())
        self.assertEqual(exported.stat().st_mode & 0o777, 0o600)

    def test_disk_full_blocks_access_but_stop_and_recovery_work(self):
        journal = Journal(self.root)
        broker = Grants(journal=journal)
        broker.set_ready(True)
        broker.arm(["control"], 30)
        with patch("journal.os.write", side_effect=OSError("disk full")):
            self.assertFalse(journal.begin("input.click", "r"))
            self.assertEqual(broker.authorize("input.click"), "audit_storage_unavailable")
            broker.stop()
            self.assertIsNone(broker.grant)
        self.assertTrue(journal.event("storage.recovered"))
        self.assertEqual(broker.authorize("input.click"), "approval_required")

    def test_rotation_retention_concurrent_requests_and_pages(self):
        journal = Journal(self.root, segment_bytes=1000, audit_bytes=5000)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertTrue(all(pool.map(lambda i: journal.begin("input.key", str(i)), range(100))))
        self.assertLessEqual(sum(p.stat().st_size for p in (self.root / "audit").glob("*.jsonl")), 5000)
        rows = journal.query()["entries"]
        self.assertEqual(len({r["eventId"] for r in rows}), len(rows))
        self.assertLess(len(rows), 101)
        self.assertEqual(len(journal.query(operation="doesnotexist")["entries"]), 0)

    def test_history_pages_filters_and_age_retention(self):
        journal = Journal(self.root)
        for i in range(60):
            journal.record({"operation": "input.key", "requestId": str(i),
                            "accepted": i % 2 == 0})
        first = journal.query(operation="input.key")
        second = journal.query(offset=50, operation="input.key")
        self.assertTrue(first["hasMore"])
        self.assertEqual(len(first["entries"]), 50)
        self.assertEqual(len(second["entries"]), 10)
        self.assertFalse(second["hasMore"])
        self.assertFalse({e["eventId"] for e in first["entries"]} &
                         {e["eventId"] for e in second["entries"]})
        self.assertEqual(len(journal.query(operation="input.key", outcome="accepted")["entries"]), 30)
        old = self.root / "audit/00000000000000000000-expired.jsonl"
        old.write_text('{}\n')
        os.utime(old, (time.time() - 31 * 86400,) * 2)
        journal.event("storage.recovered")
        self.assertFalse(old.exists())

    def test_partial_record_and_symlink_refused(self):
        journal = Journal(self.root)
        path = next((self.root / "audit").glob("*.jsonl"))
        with path.open("ab") as file:
            file.write(b'{}\n42\n{"partial":')
        self.assertEqual(len(journal.query()["entries"]), 1)
        self.assertTrue(journal.health["historyGap"])
        (self.root / "audit/00000000000000000000-invalid.jsonl").write_text("42\n")
        self.assertIsNone(journal.query()["earliestAt"])
        bad = Path(self.temp.name) / "bad"
        bad.symlink_to(self.root, target_is_directory=True)
        self.assertFalse(Journal(bad).health["available"])


if __name__ == "__main__":
    unittest.main()

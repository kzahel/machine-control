"""Private operational history: identity, durability, bounds and omissions."""

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import audit_history as audit


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.audit = self.root / "audit"
        patch = mock.patch.dict(
            os.environ, {"MACHINE_CONTROL_AUDIT_DIR": str(self.audit)}
        )
        patch.start()
        self.addCleanup(patch.stop)

    def test_empty_offline_query_does_not_create_storage(self):
        value = audit.history(target="retired-fixture")
        self.assertFalse(value["available"])
        self.assertFalse(value["coverage"]["complete"])
        self.assertFalse(self.audit.exists())

    def test_restart_pagination_filter_and_private_permissions(self):
        for i in range(5):
            audit.append("fixture", logicalTarget="a" if i % 2 else "b")
        first = audit.history(limit=2)
        second = audit.history(before=first["nextBeforeId"], limit=2)
        third = audit.history(before=second["nextBeforeId"], limit=2)
        self.assertEqual(
            [e["eventId"] for p in (third, second, first) for e in p["events"]],
            [1, 2, 3, 4, 5],
        )
        self.assertIsNone(third["nextBeforeId"])
        self.assertEqual(len(audit.history(target="a")["events"]), 2)
        self.assertTrue(first["coverage"]["startedAt"])
        self.assertFalse(first["coverage"]["complete"])
        if os.name != "nt":
            self.assertEqual(self.audit.stat().st_mode & 0o777, 0o700)
            self.assertEqual(
                (self.audit / "history.sqlite3").stat().st_mode & 0o777, 0o600
            )

    def test_event_bound_and_retention_are_reported(self):
        with mock.patch.object(audit, "MAX_EVENTS", 3):
            for i in range(5):
                audit.append("fixture", ordinal=i)
            value = audit.history()
            self.assertEqual([e["ordinal"] for e in value["events"]], [2, 3, 4])
            self.assertEqual(value["coverage"]["maximumEvents"], 3)
        db = sqlite3.connect(self.audit / "history.sqlite3")
        db.execute("UPDATE events SET timestamp='2000-01-01T00:00:00Z'")
        db.commit()
        db.close()
        audit.append("fixture", ordinal=5)
        self.assertEqual(len(audit.history()["events"]), 1)
        with self.assertRaises(audit.AuditError):
            audit.append("fixture", invalid="x" * audit.MAX_EVENT_BYTES)

    @unittest.skipIf(os.name == "nt", "POSIX link and permissions test")
    def test_unsafe_directory_file_links_and_permissions_are_refused(self):
        victim = self.root / "victim"
        victim.mkdir(mode=0o700)
        self.audit.symlink_to(victim, target_is_directory=True)
        with self.assertRaises(audit.AuditError):
            audit.append("fixture")
        self.assertEqual(list(victim.iterdir()), [])
        self.audit.unlink()
        self.audit.mkdir(mode=0o700)
        file = victim / "untouched"
        file.write_text("owned")
        file.chmod(0o600)
        (self.audit / "history.sqlite3").symlink_to(file)
        with self.assertRaises(audit.AuditError):
            audit.history()
        self.assertEqual(file.read_text(), "owned")
        (self.audit / "history.sqlite3").unlink()
        os.link(file, self.audit / "history.sqlite3")
        with self.assertRaises(audit.AuditError):
            audit.append("fixture")
        (self.audit / "history.sqlite3").unlink()
        self.audit.chmod(0o755)
        with self.assertRaises(audit.AuditError):
            audit.append("fixture")

    def test_concurrent_writers_keep_unique_events(self):
        code = "import audit_history as a; [a.append('fixture', ordinal=i) for i in range(10)]"
        environment = dict(os.environ, PYTHONPATH=str(ROOT / "client"))
        children = [
            subprocess.Popen(
                [sys.executable, "-c", code],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            for _ in range(4)
        ]
        try:
            results = [(child, child.communicate(timeout=30)[1]) for child in children]
            for child, errors in results:
                self.assertEqual(child.returncode, 0, errors.decode())
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=5)
        value = audit.history()
        self.assertEqual(len(value["events"]), 40)
        self.assertEqual(len({e["eventId"] for e in value["events"]}), 40)

    def test_busy_initialization_retries_without_losing_vacuum_or_events(self):
        class Contended(sqlite3.Connection):
            collisions = 2

            def execute(self, sql, *args):
                if sql == "PRAGMA auto_vacuum=FULL" and self.collisions:
                    self.collisions -= 1
                    error = sqlite3.OperationalError("fixture initialization contention")
                    error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                    raise error
                return super().execute(sql, *args)

        connect = sqlite3.connect
        with mock.patch.object(audit.sqlite3, "connect", side_effect=lambda *a, **kw:
                               connect(*a, **kw, factory=Contended)):
            audit.append("fixture")
        self.assertEqual(len(audit.history()["events"]), 1)
        db = connect(self.audit / "history.sqlite3")
        try:
            self.assertEqual(db.execute("PRAGMA auto_vacuum").fetchone()[0], 1)
        finally:
            db.close()

    def test_failed_initialization_closes_its_connection(self):
        connections = []

        class Broken(sqlite3.Connection):
            def execute(self, sql, *args):
                raise sqlite3.OperationalError("fixture non-retryable failure")

        connect = sqlite3.connect
        def broken(*args, **kwargs):
            db = connect(*args, **kwargs, factory=Broken)
            connections.append(db)
            return db
        with mock.patch.object(audit.sqlite3, "connect", side_effect=broken):
            with self.assertRaisesRegex(sqlite3.OperationalError, "non-retryable"):
                audit.append("fixture")
        self.assertEqual(len(connections), 1)
        with self.assertRaisesRegex(sqlite3.ProgrammingError, "closed"):
            sqlite3.Connection.execute(connections[0], "SELECT 1")

    def test_opaque_arguments_are_never_resumed_as_grammar_tokens(self):
        command = audit.Command(
            "fixture",
            "linux",
            [
                "testbed",
                "--",
                "exec",
                "python3",
                "-c",
                "PASSWORD_MARKER",
                "delete",
                "store",
            ],
        )
        command.observe(
            dict(
                accepted=True,
                delivery="confirmed",
                effect="unknown",
                uncertainty="observation_unavailable",
            )
        )
        command.finish(0)
        value = audit.history()
        self.assertEqual(value["events"][0]["command"], "testbed exec")
        self.assertNotIn("PASSWORD_MARKER", json.dumps(value))
        self.assertNotIn("python3", json.dumps(value))
        self.assertEqual(value["events"][0]["programKind"], "python")
        self.assertEqual(value["events"][-1]["effect"], "unknown")
        self.assertFalse(value["events"][-1]["payloadsRecorded"])

    def test_unpaired_intent_remains_visible(self):
        audit.Command("fixture", "linux", ["testbed", "exec", "opaque"])
        self.assertEqual(
            [e["event"] for e in audit.history()["events"]], ["command.intent"]
        )


class CliHistoryTests(unittest.TestCase):
    def setUp(self):
        HistoryTests.setUp(self)
        self.adapter = self.root / "adapter.py"
        self.adapter.write_text("""import os,sys,subprocess
from pathlib import Path
root=Path(sys.argv[1]); state=Path(sys.argv[2]); verb=sys.argv[3]
if verb.startswith('claim-'):
 args=[a for a in sys.argv[4:] if a!='--json']
 command=[sys.executable,str(root/'providers/claims/claims.py'),'--state-dir',str(state),verb[6:]]
 if verb!='claim-capabilities':command+=['--provider','fixture','--resource-id',os.environ.get('FIXTURE_IDENTITY','exact-resource-one')]
 raise SystemExit(subprocess.call(command+args))
if '--break-audit' in sys.argv:
 db=Path(os.environ['MACHINE_CONTROL_AUDIT_DIR'])/'history.sqlite3'; db.unlink(); db.mkdir()
 effect=state/'effects'; effect.write_text(str(int(effect.read_text())+1 if effect.exists() else 1))
print('OUTPUT_SECRET_MARKER')
raise SystemExit(7 if '--fail' in sys.argv else 0)
""")
        self.registry = self.root / "targets.json"
        self.write_registry()

    def write_registry(self, identity="exact-resource-one"):
        target = dict(
            platform="linux",
            profile="fixture",
            launcher="direct",
            claimPolicy="required",
            controllerPlatforms=["darwin", "linux", "windows"],
            command=[
                sys.executable,
                str(self.adapter),
                str(ROOT),
                str(self.root / "claims"),
            ],
            environment={"FIXTURE_IDENTITY": identity},
        )
        self.registry.write_text(
            json.dumps(
                dict(
                    schema="machine-control-targets/v0",
                    targets={"fixture": target, "alias": target},
                )
            )
        )

    def cli(self, *args):
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "bin/machine-control"),
                "--registry",
                str(self.registry),
                *args,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def acquire(self, alias="fixture", who="session-one"):
        result = self.cli(
            "--target",
            alias,
            "claim",
            "acquire",
            "--claimant-authority",
            "fixture",
            "--claimant-id",
            who,
            "--reason",
            "Owned diagnostic",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["data"]["claim"]["claimId"]

    def test_full_cli_claim_use_release_correlates_without_secrets(self):
        identifier = self.acquire()
        result = self.cli(
            "--target",
            "alias",
            "--claim",
            identifier,
            "testbed",
            "--",
            "exec",
            "OPAQUE_PASSWORD_MARKER",
            "--fail",
        )
        self.assertEqual(result.returncode, 7)
        self.assertIn("OUTPUT_SECRET_MARKER", result.stdout)
        self.assertEqual(
            self.cli("--target", "fixture", "claim", "release", identifier).returncode,
            0,
        )
        value = audit.history(target="alias")
        lifecycle = [e for e in value["events"] if e["event"].startswith("claim.")]
        self.assertEqual(
            [e["event"] for e in lifecycle], ["claim.acquired", "claim.released"]
        )
        result = next(
            e
            for e in value["events"]
            if e["event"] == "command.result" and e["command"] == "testbed exec"
        )
        self.assertEqual(result["exitCode"], 7)
        self.assertEqual(result["claimant"]["id"], "session-one")
        self.assertEqual(len({e["resourceKey"] for e in lifecycle}), 1)
        stored = (self.audit / "history.sqlite3").read_bytes()
        for secret in (
            b"OPAQUE_PASSWORD_MARKER",
            b"OUTPUT_SECRET_MARKER",
            b"exact-resource-one",
        ):
            self.assertNotIn(secret, stored)
        self.assertEqual(
            len(audit.history(claim=identifier)["events"]),
            len(audit.history(claimant="session-one")["events"]),
        )

    def test_same_alias_replacement_and_old_claimant_survive_release(self):
        first = self.acquire()
        self.cli("--target", "fixture", "claim", "release", first)
        self.write_registry("replacement-resource")
        second = self.acquire(who="session-two")
        self.cli("--target", "fixture", "claim", "release", second)
        acquired = [
            e
            for e in audit.history(target="fixture")["events"]
            if e["event"] == "claim.acquired"
        ]
        self.assertEqual(
            [e["claimant"]["id"] for e in acquired], ["session-one", "session-two"]
        )
        self.assertNotEqual(acquired[0]["resourceKey"], acquired[1]["resourceKey"])

    def test_refused_acquire_does_not_adopt_the_other_holder(self):
        identifier = self.acquire()
        result = self.cli(
            "--target",
            "fixture",
            "claim",
            "acquire",
            "--claimant-authority",
            "fixture",
            "--claimant-id",
            "contender",
            "--reason",
            "Cannot borrow",
        )
        self.assertEqual(result.returncode, 1)
        last = audit.history()["events"][-1]
        self.assertEqual(last["errorCode"], "target_claimed")
        self.assertIsNone(last["claimId"])
        self.assertEqual(
            len(
                [e for e in audit.history()["events"] if e["event"] == "claim.acquired"]
            ),
            1,
        )
        self.cli("--target", "fixture", "claim", "release", identifier)

    def test_history_reads_retired_alias_without_loading_registry(self):
        self.acquire()
        self.registry.unlink()
        result = self.cli(
            "--target", "fixture", "audit", "history", "--limit", "2", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["events"]), 2)
        result = self.cli("audit", "history", "--since", "2026-01-01")
        self.assertEqual(result.returncode, 2)

    def test_result_persistence_failure_reports_failure_without_replay(self):
        identifier = self.acquire()
        result = self.cli(
            "--target",
            "fixture",
            "--claim",
            identifier,
            "testbed",
            "exec",
            "--break-audit",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("OUTPUT_SECRET_MARKER", result.stdout)
        self.assertIn("coverage gap", result.stderr)
        self.assertEqual((self.root / "claims/effects").read_text(), "1")
        self.assertEqual(
            self.cli("--target", "fixture", "claim", "release", identifier).returncode,
            0,
        )

    def test_renewal_preserves_claim_correlation_and_attribution(self):
        identifier = self.acquire()
        self.assertEqual(
            self.cli(
                "--target", "fixture", "claim", "renew", identifier, "--duration", "1h"
            ).returncode,
            0,
        )
        self.cli("--target", "fixture", "claim", "release", identifier)
        events = audit.history(claim=identifier)["events"]
        renewal = next(e for e in events if e["event"] == "claim.renewed")
        self.assertEqual(renewal["claimant"]["id"], "session-one")
        self.assertTrue(
            any(
                e["event"] == "command.result" and e["command"] == "claim renew"
                for e in events
            )
        )

    def test_unavailable_intent_refuses_new_work_but_release_still_runs(self):
        identifier = self.acquire()
        db = self.audit / "history.sqlite3"
        db.unlink()
        db.mkdir()
        result = self.cli(
            "--target", "fixture", "--claim", identifier, "testbed", "exec", "opaque"
        )
        self.assertEqual(json.loads(result.stdout)["errorCode"], "audit_unavailable")
        self.assertNotIn("OUTPUT_SECRET_MARKER", result.stdout)
        result = self.cli("--target", "fixture", "claim", "release", identifier)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = list((self.root / "claims").glob("resource-*.json"))
        self.assertIsNone(json.loads(records[0].read_text())["active"])


if __name__ == "__main__":
    unittest.main()

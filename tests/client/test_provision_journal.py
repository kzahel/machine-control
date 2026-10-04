"""Provisioning evidence: private storage, phase projection, failures, notes."""

import ast
import io
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
import provision_journal as journal
import audit_history as audit


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "journals"
        patch = mock.patch.dict(os.environ, {
            "MACHINE_CONTROL_PROVISION_DIR": str(self.store),
            "MACHINE_CONTROL_AUDIT_DIR": str(self.root / "audit"),
            "MACHINE_CONTROL_PROVISION_RUN": "",
        })
        patch.start()
        self.addCleanup(patch.stop)

    def begin(self):
        return journal.begin("linux", "development")["runId"]

    def test_dated_restart_pagination_and_notes_after_finish(self):
        identifier = self.begin()
        self.assertRegex(identifier, r"p-\d{8}T\d{6}Z-")
        journal.append(identifier, "agent.note", dict(kind="friction", text="Waited for updates"), source="agent")
        command = journal.Command(identifier, ["testbed", "factory-stages", "--json"])
        command.finish(0)
        journal.finish(identifier, "ready")
        journal.append(identifier, "agent.note", dict(kind="follow-up", text="Improve progress reporting"), source="agent")
        pages, before = [], None
        while True:
            page = journal.show(identifier, before=before, limit=2)
            pages.insert(0, page["events"])
            before = page["nextBeforeId"]
            if not before:
                break
        self.assertEqual([e["eventId"] for p in pages for e in p], list(range(1, 7)))
        self.assertFalse(page["coverage"]["complete"])
        self.assertFalse(page["coverage"]["automaticRetention"])
        self.assertIn("agent reported", journal.markdown(page))
        if os.name != "nt":
            self.assertEqual(self.store.stat().st_mode & 0o777, 0o700)
            self.assertEqual((self.store / (identifier + ".sqlite3")).stat().st_mode & 0o777, 0o600)
        with self.assertRaises(journal.JournalError):
            journal.Command(identifier, ["target", "up"])

    def test_unknown_intent_blocks_ready_without_inventing_outcome(self):
        identifier = self.begin()
        journal.Command(identifier, ["target", "up"])
        with self.assertRaises(journal.JournalError):
            journal.finish(identifier, "ready")
        value = journal.finish(identifier, "abandoned")
        self.assertEqual(value["unpairedCommands"], 1)
        self.assertEqual(journal.show(identifier)["coverage"]["unpairedCommands"], 1)

    def test_bounds_and_unsafe_selectors(self):
        identifier = self.begin()
        with mock.patch.object(journal, "MAX_EVENTS", 1):
            with self.assertRaises(journal.JournalError):
                journal.Command(identifier, ["target", "up"])
        for invalid in ("../private", "p-20260101T000000Z-x", "/tmp/file"):
            with self.assertRaises(journal.JournalError):
                journal.show(invalid)

    @unittest.skipIf(os.name == "nt", "POSIX storage")
    def test_links_and_public_permissions_refused(self):
        identifier = self.begin()
        path = self.store / (identifier + ".sqlite3")
        path.chmod(0o644)
        with self.assertRaises(audit.AuditError):
            journal.show(identifier)
        path.chmod(0o600)
        alias = self.root / "linked"
        os.link(path, alias)
        with self.assertRaises(audit.AuditError):
            journal.show(identifier)
        alias.unlink()
        path.unlink()
        path.symlink_to(alias)
        with self.assertRaises(audit.AuditError):
            journal.show(identifier)
        self.store.rename(self.root / "real")
        self.store.symlink_to(self.root / "real", target_is_directory=True)
        with self.assertRaises(audit.AuditError):
            journal.begin("linux", "runtime")

    def test_concurrent_writes_are_serialized(self):
        identifier = self.begin()
        code = "import provision_journal as j,sys; [j.append(sys.argv[1], 'agent.note', {'kind':'friction','text':'fixture'}, source='agent') for i in range(8)]"
        children = [subprocess.Popen([sys.executable, "-c", code, identifier],
                    env=dict(os.environ, PYTHONPATH=str(ROOT / "client")),
                    stderr=subprocess.PIPE) for _ in range(3)]
        for child in children:
            _, errors = child.communicate(timeout=30)
            self.assertEqual(child.returncode, 0, errors)
        self.assertEqual(len(journal.show(identifier)["events"]), 25)

    def test_projection_omits_payloads_and_covers_owned_inspectors(self):
        for schema in journal.STAGE_SCHEMAS:
            value = journal.stage_projection(dict(schema=schema, secret="OUTPUT_SECRET_MARKER",
                stages=[dict(name="resident", state="blocked", evidence="OUTPUT_SECRET_MARKER", nextCommand=["password"]),
                        dict(name="UNRECOGNIZED_SECRET", state="waiting"),
                        dict(name=[], state="blocked")]))
            self.assertEqual(value["stages"], [dict(name="resident", state="blocked")])
            self.assertEqual(value["omittedStages"], 2)
            self.assertNotIn("SECRET", json.dumps(value))
        self.assertIsNone(journal.stage_projection({"schema": []}))
        for relative in ("windows/scripts/factory-stages.py", "linux/scripts/factory-stages.py", "macos/scripts/bootstrap-stages.py"):
            tree = ast.parse((ROOT / "platforms" / relative).read_text())
            names = {n.args[0].value for n in ast.walk(tree)
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                     and n.func.id == "stage" and n.args and isinstance(n.args[0], ast.Constant)}
            self.assertFalse(names - journal.STAGES, relative)


class CliJournalTests(JournalTests):
    def setUp(self):
        super().setUp()
        self.adapter = self.root / "adapter.py"
        self.adapter.write_text('''import json,os,sys,subprocess
from pathlib import Path
root=Path(sys.argv[1]); state=Path(sys.argv[2]); verb=sys.argv[3]
if verb.startswith('claim-'):
 args=[a for a in sys.argv[4:] if a!='--json']
 command=[sys.executable,str(root/'providers/claims/claims.py'),'--state-dir',str(state),verb[6:]]
 if verb!='claim-capabilities':command+=['--provider','fixture','--resource-id','exact-resource-one']
 raise SystemExit(subprocess.call(command+args))
if '--nested' in sys.argv:
 raise SystemExit(subprocess.call([sys.executable,str(root/'bin/machine-control'),
  '--registry',str(state.parent/'targets.json'),'--target','fixture',
  '--claim',os.environ['MACHINE_CONTROL_CLAIM_ID'],'testbed','exec','--fail']))
if '--break-journal' in sys.argv:
 path=Path(os.environ['MACHINE_CONTROL_PROVISION_DIR'])/(os.environ['MACHINE_CONTROL_PROVISION_RUN']+'.sqlite3')
 path.unlink();path.mkdir();(state/'effect').write_text('once')
if verb=='factory-stages':
 if '--bad-json' in sys.argv:print('OUTPUT_SECRET_MARKER')
 elif '--oversize' in sys.argv:print('X'*300000)
 else:print(json.dumps({'schema':'linuxvm-factory-stages/v0','stages':[{'name':'resident','state':'waiting','evidence':'OUTPUT_SECRET_MARKER'},{'name':'credential-handoff','state':'complete'}]}))
else:print('OUTPUT_SECRET_MARKER')
print('STDERR_SECRET_MARKER',file=sys.stderr)
raise SystemExit(7 if '--fail' in sys.argv else 0)
''')
        self.registry = self.root / "targets.json"
        self.registry.write_text(json.dumps(dict(schema="machine-control-targets/v0", targets={"fixture":dict(
            platform="linux", profile="fixture", launcher="direct", claimPolicy="required",
            controllerPlatforms=["darwin", "linux", "windows"],
            command=[sys.executable, str(self.adapter), str(ROOT), str(self.root / "claims")])})))

    def cli(self, *args, stdin=None):
        return subprocess.run([sys.executable, str(ROOT / "bin/machine-control"),
                               "--registry", str(self.registry), *args],
                              input=stdin, capture_output=True, text=True, timeout=30)

    def acquire(self, identifier):
        value = self.cli("--provision-run", identifier, "--target", "fixture", "claim", "acquire",
            "--claimant-authority", "fixture", "--claimant-id", "fixture-session", "--reason", "Provision fixture")
        self.assertEqual(value.returncode, 0, value.stderr)
        claim = json.loads(value.stdout)["data"]["claim"]["claimId"]
        self.addCleanup(lambda: self.cli("--target", "fixture", "claim", "release", claim))
        return claim

    def test_offline_notes_and_finish_work_without_registry(self):
        self.registry.unlink()
        value = self.cli("provision", "begin", "--platform", "windows")
        self.assertEqual(value.returncode, 0, value.stderr)
        identifier = json.loads(value.stdout)["runId"]
        value = self.cli("provision", "note", identifier, "--kind", "friction", stdin="Updates took a while\n")
        self.assertEqual(value.returncode, 0, value.stderr)
        self.assertEqual(json.loads(value.stdout)["source"], "agent")
        self.assertNotEqual(self.cli("provision", "note", identifier, "--kind", "friction", stdin="x" * 4097).returncode, 0)
        self.assertEqual(self.cli("provision", "finish", identifier, "--outcome", "blocked").returncode, 0)
        report = self.cli("provision", "show", identifier, "--markdown")
        self.assertIn("Updates took a while", report.stdout)
        self.assertIn(identifier, report.stdout)

    def test_ready_refusal_explains_unpaired_intent(self):
        identifier = self.begin()
        journal.Command(identifier, ["target", "up"])
        result = self.cli("provision", "finish", identifier, "--outcome", "ready")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unpaired command intents", json.loads(result.stdout)["message"])
        self.assertEqual(journal.show(identifier)["run"]["outcome"], "in_progress")

    def test_precreation_phase_claims_failure_and_secret_omission(self):
        identifier = self.begin()
        self.assertEqual(self.cli("--provision-run", identifier, "--target", "fixture", "testbed", "--", "factory-stages", "preflight", "--json").returncode, 0)
        denied = self.cli("--provision-run", identifier, "--target", "fixture", "testbed", "--", "exec", "ARGUMENT_SECRET_MARKER")
        self.assertNotEqual(denied.returncode, 0)
        claim = self.acquire(identifier)
        prefix = ("--provision-run", identifier, "--target", "fixture", "--claim", claim)
        self.assertEqual(self.cli(*prefix, "testbed", "--", "factory-stages", "--json").returncode, 0)
        failure = self.cli(*prefix, "testbed", "--", "exec", "ARGUMENT_SECRET_MARKER", "--fail")
        self.assertEqual(failure.returncode, 7)
        self.assertIn("OUTPUT_SECRET_MARKER", failure.stdout)
        self.assertEqual(self.cli("--provision-run", identifier, "--target", "fixture", "claim", "release", claim).returncode, 0)
        events = journal.show(identifier)["events"]
        results = [e for e in events if e["event"] == "command.result"]
        phase = next(e for e in results if e["command"] == "testbed factory-stages")
        self.assertEqual(phase["stageObservation"]["stages"][0]["state"], "waiting")
        self.assertEqual(next(e for e in results if e["command"] == "claim acquire")["claimId"], claim)
        self.assertTrue(phase["auditCorrelationId"])
        self.assertTrue(any(e.get("exitCode") == 7 for e in results))
        stored = (self.store / (identifier + ".sqlite3")).read_bytes()
        for secret in (b"ARGUMENT_SECRET_MARKER", b"OUTPUT_SECRET_MARKER", b"STDERR_SECRET_MARKER"):
            self.assertNotIn(secret, stored)

    def test_environment_attachment_and_invalid_phase_output(self):
        identifier = self.begin()
        with mock.patch.dict(os.environ, {"MACHINE_CONTROL_PROVISION_RUN": identifier}):
            for extra in ("--bad-json", "--oversize"):
                value = self.cli("--target", "fixture", "testbed", "factory-stages", "preflight", "--json", extra)
                self.assertEqual(value.returncode, 0, value.stderr)
        results = [e for e in journal.show(identifier)["events"] if e["event"] == "command.result"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(e["stageObservation"] == {"available": False} for e in results))

    def test_child_common_cli_inherits_run_without_explicit_flag(self):
        identifier = self.begin()
        claim = self.acquire(identifier)
        value = self.cli("--provision-run", identifier, "--target", "fixture", "--claim", claim,
                         "testbed", "exec", "--nested")
        self.assertEqual(value.returncode, 7, value.stderr)
        results = [e for e in journal.show(identifier)["events"]
                   if e["event"] == "command.result" and e["command"] == "testbed exec"]
        self.assertEqual(len(results), 2)
        self.assertTrue(all(e["exitCode"] == 7 and e["claimId"] == claim for e in results))

    def test_macos_precreation_inspector_remains_read_only_and_claim_free(self):
        import machine_control
        self.assertFalse(machine_control.operation_requires_claim("testbed", ["--", "bootstrap-stages", "preflight", "--json"]))
        self.assertTrue(machine_control.operation_requires_claim("testbed", ["--", "bootstrap-stages", "--json"]))

    def test_failed_intent_prevents_dispatch_but_release_remains_available(self):
        identifier = self.begin()
        claim = self.acquire(identifier)
        journal.finish(identifier, "abandoned")
        result = self.cli("--provision-run", identifier, "--target", "fixture", "--claim", claim, "testbed", "exec", "--fail")
        self.assertEqual(json.loads(result.stdout)["errorCode"], "provision_journal_unavailable")
        self.assertNotIn("OUTPUT_SECRET_MARKER", result.stdout)
        result = self.cli("--provision-run", identifier, "--target", "fixture", "claim", "release", claim)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("coverage gap", result.stderr)

    def test_result_write_failure_is_not_success_or_replayed(self):
        identifier = self.begin()
        claim = self.acquire(identifier)
        value = self.cli("--provision-run", identifier, "--target", "fixture", "--claim", claim, "testbed", "exec", "--break-journal")
        self.assertEqual(value.returncode, 1, value.stderr)
        self.assertIn("coverage gap", value.stderr)
        self.assertEqual((self.root / "claims/effect").read_text(), "once")


if __name__ == "__main__":
    unittest.main()

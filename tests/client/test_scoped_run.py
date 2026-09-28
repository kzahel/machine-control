import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "machine-control"
sys.path.insert(0, str(ROOT / "client"))
import machine_control as mc
from scoped_process import bounded_capture


class ScopedRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.registry = self.directory / "registry.json"
        self.target = {
            "platform": "linux", "profile": "fixture",
            "interface": "machine-control-v0", "claimPolicy": "required",
            "controllerPlatforms": [mc.controller_platform()], "launcher": "auto",
            "command": [sys.executable, str(Path(__file__).with_name("fixtures")
                                           / "scoped-testbed.py")],
            "environment": {"SCOPE_FIXTURE_DIR": str(self.directory)},
        }
        self.registry.write_text(json.dumps({"schema": mc.TARGET_SCHEMA,
                                            "targets": {"fixture": self.target}}))
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("MACHINE_CONTROL_")}
        self.env.update(XDG_CONFIG_HOME=str(self.directory / "config"),
                        APPDATA=str(self.directory / "config"))

    def tearDown(self):
        self.temp.cleanup()

    def argv(self, code, *options):
        return [sys.executable, str(CLI), "--registry", str(self.registry),
                "--target", "fixture", "run", "--claimant-authority", "tests",
                "--claimant-id", "scoped-test", "--reason", "exercise cleanup",
                *options, "--", sys.executable, "-c", code]

    def events(self):
        return [json.loads(line) for line in
                (self.directory / "events.jsonl").read_text().splitlines()]

    def execute(self, code="print('task output')", *options, mode="", ttl="30"):
        result = subprocess.run(self.argv(code, *options), capture_output=True,
                                text=True, timeout=20,
                                env={**self.env, "SCOPE_FIXTURE_MODE": mode,
                                     "SCOPE_FIXTURE_TTL": ttl})
        records = [json.loads(line) for line in result.stderr.splitlines()
                   if line.startswith('{"schema":"machine-control-run/v0"')]
        self.assertTrue(records, result.stderr + result.stdout)
        self.assertEqual(records[-1]["event"], "finished")
        self.assertNotIn("private-detail", result.stderr)
        self.assertNotIn(str(self.directory), result.stderr)
        return result, records[-1]

    def assert_released(self, audit):
        self.assertEqual(audit["cleanup"]["claim"], "released")
        self.assertFalse((self.directory / "held.json").exists())
        self.assertEqual(sum(event["operation"].endswith("-release")
                             for event in self.events()), 1)

    def test_success_inherits_selection_and_removes_private_context(self):
        code = (
            "import os,subprocess,sys; "
            "print(os.environ['MACHINE_CONTROL_SCOPE_FILE'],flush=True); "
            f"sys.exit(subprocess.call([sys.executable,{str(CLI)!r},'os','--','true']))"
        )
        result, audit = self.execute(code)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(audit["outcome"], "completed")
        self.assertFalse(Path(result.stdout.splitlines()[0]).exists())
        self.assert_released(audit)
        operations = [event["operation"] for event in self.events()]
        self.assertEqual(operations[:3], ["doctor", "claim-status", "claim-acquire"])
        self.assertIn("claim-check", operations)

    def test_child_failure_preserves_exit_status(self):
        result, audit = self.execute("raise SystemExit(7)")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(audit["outcome"], "child_failed")
        self.assert_released(audit)

    def test_off_target_is_eligible_without_starting_it(self):
        self.env["MACHINE_CONTROL_MOCK_NOT_READY"] = "1"
        result, audit = self.execute("pass")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_released(audit)
        self.assertNotIn("up", [event["operation"] for event in self.events()])

    def test_bad_doctor_stops_before_acquisition(self):
        self.env["MACHINE_CONTROL_MOCK_BAD_DOCTOR"] = "1"
        result, audit = self.execute("pass")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(audit["cleanup"]["claim"], "not_acquired")
        self.assertEqual(len(self.events()), 1)

    def test_unknown_acquisition_is_unresolved_without_guessing(self):
        result, audit = self.execute(mode="unknown_receipt")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(audit["cleanup"]["claim"], "unresolved")
        self.assertIsNone(audit["claimId"])
        self.assertTrue((self.directory / "held.json").exists())
        self.assertNotIn("claim-release", [event["operation"] for event in self.events()])

    def test_disruptive_use_class_survives_renewal(self):
        result, audit = self.execute("import time; time.sleep(2.5)",
                                     "--disruptive", ttl="6")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(audit["renewals"], 1)
        self.assert_released(audit)

    def test_pinned_registry_survives_original_registry_change(self):
        code = (f"import pathlib,subprocess,sys; pathlib.Path({str(self.registry)!r})"
                ".write_text('{}'); "
                f"sys.exit(subprocess.call([sys.executable,{str(CLI)!r},'os','--','true']))")
        result, audit = self.execute(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_released(audit)

    def test_successful_parent_does_not_leave_descendants(self):
        marker = self.directory / "survived"
        grandchild = f"import time,pathlib; time.sleep(3); pathlib.Path({str(marker)!r}).touch()"
        code = (f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',"
                f"{grandchild!r}])")
        result, audit = self.execute(code)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_released(audit)
        time.sleep(3)
        self.assertFalse(marker.exists())

    def test_scope_refuses_conflicting_selection_and_nested_run(self):
        for args in (["--target", "different", "target", "status"], ["run", "--help"]):
            with self.subTest(args=args):
                (self.directory / "events.jsonl").unlink(missing_ok=True)
                code = ("import subprocess,sys; "
                        f"sys.exit(subprocess.call([sys.executable,{str(CLI)!r},*{args!r}]))")
                result, audit = self.execute(code)
                self.assertNotEqual(result.returncode, 0)
                self.assert_released(audit)

    def test_workspace_releases_exact_handle_with_claim(self):
        result, audit = self.execute("pass", "--intent", "isolated")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(audit["cleanup"]["workspace"], "released")
        self.assert_released(audit)
        self.assertEqual(self.events()[-1]["operation"], "workspace-release")

    def test_workspace_renewal_carries_both_selectors(self):
        result, audit = self.execute("import time; time.sleep(2.5)",
                                     "--intent", "isolated", ttl="6")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(audit["renewals"], 1)
        self.assert_released(audit)

    def test_renewal_failures_stop_child_then_release(self):
        for mode in ("renew_refused", "renew_mismatch", "renew_slow"):
            with self.subTest(mode=mode):
                (self.directory / "events.jsonl").unlink(missing_ok=True)
                marker = self.directory / "should-not-exist"
                code = (f"import pathlib,time; time.sleep(6); "
                        f"pathlib.Path({str(marker)!r}).touch()")
                result, audit = self.execute(code, mode=mode, ttl="6")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(audit["outcome"], "renewal_failed")
                self.assertFalse(marker.exists())
                self.assert_released(audit)

    def test_release_failure_is_unresolved_without_blind_retry(self):
        result, audit = self.execute("pass", "--intent", "isolated",
                                     mode="release_refused")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(audit["cleanup"], {"claim": "unresolved",
                                            "workspace": "unresolved"})
        self.assertTrue((self.directory / "held.json").exists())
        self.assertEqual(self.events()[-1]["operation"], "workspace-release")
        self.assertNotIn("claim-release", [event["operation"] for event in self.events()])

    def test_malformed_acquisition_retains_receipt_for_cleanup(self):
        result, audit = self.execute(mode="bad_receipt")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assert_released(audit)

    def test_preflight_refusal_does_not_acquire(self):
        result, audit = self.execute(mode="identity")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(audit["cleanup"]["claim"], "not_acquired")
        self.assertNotIn("claim-acquire", [event["operation"] for event in self.events()])

    def test_busy_acquisition_does_not_release_another_holder(self):
        result, audit = self.execute(mode="acquire_refused")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(audit["cleanup"]["claim"], "not_acquired")
        self.assertNotIn("claim-release", [event["operation"] for event in self.events()])

    def test_successful_management_preserves_provider_owned_service(self):
        marker = self.directory / "service-effect"
        service = (f"import time,pathlib; time.sleep(0.5); "
                   f"pathlib.Path({str(marker)!r}).touch()")
        command = ("import subprocess,sys; "
                   f"subprocess.Popen([sys.executable,'-c',{service!r}],"
                   "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,"
                   "stderr=subprocess.DEVNULL)")
        result = bounded_capture([sys.executable, "-c", command], timeout=5, text=True)
        self.assertEqual(result.returncode, 0)
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(marker.exists())

    def test_management_timeout_stops_late_mutation(self):
        marker = self.directory / "late-mutation"
        grandchild = (f"import time,pathlib; time.sleep(1.5); "
                      f"pathlib.Path({str(marker)!r}).touch()")
        command = (f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"
                   f"{grandchild!r}]); time.sleep(20)")
        with self.assertRaises(subprocess.TimeoutExpired):
            bounded_capture([sys.executable, "-c", command], timeout=0.5, text=True)
        time.sleep(1.5)
        self.assertFalse(marker.exists())

    def test_child_cannot_change_selection_or_release_scope(self):
        code = ("import subprocess,sys; "
                f"sys.exit(subprocess.call([sys.executable,{str(CLI)!r},"
                "'claim','release','c-0123456789abcdef01234567']))")
        result, audit = self.execute(code)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["errorCode"], "run_scope_management")
        self.assert_released(audit)

    @unittest.skipIf(os.name == "nt", "POSIX signal delivery")
    def test_sigterm_stops_descendants_before_release(self):
        ready = self.directory / "ready"
        marker = self.directory / "survived"
        grandchild = f"import time,pathlib; time.sleep(3); pathlib.Path({str(marker)!r}).touch()"
        code = (f"import subprocess,sys,time,pathlib; subprocess.Popen([sys.executable,'-c',"
                f"{grandchild!r}]); pathlib.Path({str(ready)!r}).touch(); time.sleep(30)")
        process = subprocess.Popen(self.argv(code), env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists())
            process.send_signal(signal.SIGTERM)
            _, stderr = process.communicate(timeout=8)
            audit = json.loads(stderr.splitlines()[-1])
            self.assertEqual(process.returncode, 143, stderr)
            self.assertEqual(audit["outcome"], "interrupted")
            self.assert_released(audit)
            time.sleep(3)
            self.assertFalse(marker.exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    @unittest.skipIf(os.name == "nt", "POSIX signal delivery")
    def test_signal_during_acquisition_still_cleans_receipt(self):
        process = subprocess.Popen(self.argv("raise SystemExit(99)"),
                                   env={**self.env, "SCOPE_FIXTURE_MODE": "acquire_slow"},
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8
            while not (self.directory / "acquiring").exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue((self.directory / "acquiring").exists())
            process.send_signal(signal.SIGINT)
            stdout, stderr = process.communicate(timeout=8)
            audit = json.loads(stderr.splitlines()[-1])
            self.assertEqual(process.returncode, 130, stdout + stderr)
            self.assertIsNone(audit["childExitCode"])
            self.assert_released(audit)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()

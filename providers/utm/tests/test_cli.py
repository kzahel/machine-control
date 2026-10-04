"""No real UTM or VM is contacted; signal fixtures do not generate crash reports."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

RUNNER = Path(__file__).resolve().parents[1] / "cli.py"
ROOT = RUNNER.parents[2]


@unittest.skipIf(os.name == "nt", "UTM runs on POSIX controllers")
class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.logs = self.root / "logs"
        self.environment = {**os.environ, "MACHINE_CONTROL_UTM_DIAGNOSTICS_DIR": str(self.logs)}
        self.fixture = self.root / "utmctl"
        spec = importlib.util.spec_from_file_location("utm_cli", RUNNER)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def script(self, body):
        self.fixture.write_text(f"#!{sys.executable}\n" + body)
        self.fixture.chmod(0o700)

    def call(self, *args, **kwargs):
        return subprocess.run([sys.executable, str(RUNNER), "diagnostic", str(self.fixture), *args],
                              env=self.environment, capture_output=True, timeout=10, **kwargs)

    def rows(self):
        return [json.loads(line) for line in (self.logs / "calls.jsonl").read_text().splitlines()]

    def test_streams_exit_status_and_private_content(self):
        self.script("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n"
                    "sys.stderr.write('secret guest stderr\\n')\nsys.exit(7)\n")
        result = self.call("file", "push", "private-vm", "secret-path", input=b"secret-input\x00\xff")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"secret-input\x00\xff")
        self.assertEqual(result.stderr, b"secret guest stderr\n")
        rows = self.rows()
        self.assertEqual([r["event"] for r in rows], ["intent", "spawn", "result"])
        self.assertEqual(rows[-1]["operation"], "file.push")
        self.assertEqual(rows[-1]["returnCode"], 7)
        self.assertEqual(rows[1]["pid"], rows[-1]["pid"])
        self.assertEqual(len({r["id"] for r in rows}), 1)
        text = (self.logs / "calls.jsonl").read_text()
        for forbidden in ("secret", "private-vm", str(self.fixture)):
            self.assertNotIn(forbidden, text)
        self.assertEqual(self.logs.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.logs / "calls.jsonl").stat().st_mode & 0o777, 0o600)

    def test_failure_classification_and_signal(self):
        self.script("import os,signal,sys\n"
                    "sys.stderr.write('failed to get scripting definition private-path\\n"
                    "NSInvalidArgumentException: unrecognized selector secret-data\\n')\n"
                    "sys.stderr.flush()\nos.kill(os.getpid(), signal.SIGTERM)\n")
        result = self.call("status", "private-vm")
        self.assertEqual(result.returncode, 128 + signal.SIGTERM)
        row = self.rows()[-1]
        self.assertEqual(row["signal"], signal.SIGTERM)
        self.assertEqual(row["failureCategories"], ["objc_exception", "scripting_definition_unavailable", "unrecognized_selector"])
        self.assertNotIn("private-path", json.dumps(self.rows()))

    def test_large_stderr_is_drained(self):
        self.script("import sys\nsys.stderr.buffer.write(b'x' * 300000 + b'unrecognized selector')\n")
        result = self.call("unknown-private-command")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stderr), 300021)
        self.assertEqual(self.rows()[-1]["operation"], "other")
        self.assertEqual(self.rows()[-1]["failureCategories"], ["unrecognized_selector"])

    def test_logging_failure_does_not_repeat_or_prevent_dispatch(self):
        self.logs.write_text("not a directory")
        self.script("print('ran once')\n")
        result = self.call("list")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"ran once\n")
        self.assertIn(b"diagnostics unavailable", result.stderr)

    def test_symlink_log_is_not_followed(self):
        self.logs.mkdir()
        victim = self.root / "victim"
        victim.write_text("untouched")
        (self.logs / "calls.jsonl").symlink_to(victim)
        self.script("print('ok')\n")
        self.assertEqual(self.call("list").returncode, 0)
        self.assertEqual(victim.read_text(), "untouched")

    def test_rotation_and_concurrent_writers(self):
        with patch.dict(os.environ, self.environment), patch.object(self.module, "MAX_BYTES", 100):
            for i in range(20):
                self.module.append_event({"sequence": i})
        self.assertEqual(len(list(self.logs.glob("calls*.jsonl"))), 3)
        self.script("print('ok')\n")
        processes = [subprocess.Popen([sys.executable, str(RUNNER), "diagnostic", str(self.fixture), "list"],
                                     env=self.environment, stdout=subprocess.DEVNULL) for _ in range(8)]
        for process in processes:
            self.assertEqual(process.wait(timeout=10), 0)
        rows = self.rows()
        results = [r for r in rows if r.get("event") == "result"]
        self.assertEqual(len(results), 8)
        self.assertEqual(len({r["id"] for r in results}), 8)

    def test_cancel_is_forwarded_and_child_reaped(self):
        self.script("import time\ntime.sleep(30)\n")
        process = subprocess.Popen([sys.executable, str(RUNNER), "diagnostic", str(self.fixture), "list"],
                                   env=self.environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if (self.logs / "calls.jsonl").exists() and any(r["event"] == "spawn" for r in self.rows()):
                    break
                time.sleep(0.02)
            child_pid = next(r["pid"] for r in self.rows() if r["event"] == "spawn")
            process.terminate()
            self.assertEqual(process.wait(timeout=5), 128 + signal.SIGTERM)
            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

    def test_missing_executable(self):
        result = self.call("list")
        self.assertEqual(result.returncode, 127)
        self.assertEqual(self.rows()[-1]["outcome"], "launch_failed")

    @unittest.skipUnless(sys.platform == "darwin", "providers require macOS")
    def test_provider_status_keeps_diagnostics_when_stderr_discarded(self):
        self.script("import sys\nsys.stderr.write('unrecognized selector\\n')\nsys.exit(8)\n")
        for platform, prefix in (("windows", "WINVM"), ("linux", "LINUXVM")):
            environment = {**self.environment, f"{prefix}_UTMCTL": str(self.fixture),
                           f"{prefix}_CONFIG_FILE": str(self.root / "absent"),
                           f"{prefix}_TARGET_FILE": str(self.root / "absent"),
                           "MACHINE_CONTROL_CLAIM_POLICY": "optional"}
            result = subprocess.run(["bash", str(ROOT / f"platforms/{platform}/providers/utm-macos/provider.sh"), "status"],
                                    env=environment, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 8, result.stderr)
            self.assertEqual(self.rows()[-1]["source"], platform)
            self.assertEqual(self.rows()[-1]["failureCategories"], ["unrecognized_selector"])


if __name__ == "__main__":
    unittest.main()

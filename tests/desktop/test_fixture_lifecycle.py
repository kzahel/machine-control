"""Real child effects distinguish clean exit, forced recovery and failed cleanup."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest

spec = importlib.util.spec_from_file_location("fixture_lifecycle",
    Path(__file__).resolve().parents[1] / "windows/fixture_lifecycle.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class FixtureLifecycleTests(unittest.TestCase):
    def child(self):
        child = subprocess.Popen([sys.executable, "-c", "import sys;sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.reap, child)
        return child

    @staticmethod
    def reap(child):
        if child.poll() is None: child.kill()
        child.wait(timeout=5)
        if child.stdin: child.stdin.close()

    def test_graceful_exit_does_not_request_force(self):
        child = self.child(); child.stdin.close()
        result = module.finish_owned_process(child, lambda _: self.fail("Unexpected termination"), grace_seconds=2)
        self.assertEqual(result, dict(gracefulDeadlineExceeded=False, forcedTerminationRequested=False, exitObserved=True))

    def test_late_exit_records_force_request_and_observed_exit(self):
        child = self.child()
        result = module.finish_owned_process(child, lambda owned: owned.kill(), grace_seconds=.03)
        self.assertEqual(result, dict(gracefulDeadlineExceeded=True, forcedTerminationRequested=True, exitObserved=True))
        self.assertIsNotNone(child.poll())

    def test_failed_termination_cannot_report_cleanup_success(self):
        child = self.child()
        with self.assertRaises(subprocess.TimeoutExpired):
            module.finish_owned_process(child, lambda _: None, grace_seconds=.03, forced_seconds=.03)


if __name__ == "__main__":
    unittest.main()

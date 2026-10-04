"""Verify bridge failures are refused before CLI dispatch, without real UTM."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "providers/utm"))
import automation


class AutomationTests(unittest.TestCase):
    def probe_result(self, code, stdout="", stderr=""):
        with patch.object(automation, "application_bundle", return_value=Path("/fixture/UTM.app")), \
             patch.object(automation.subprocess, "run", return_value=subprocess.CompletedProcess([], code, stdout, stderr)):
            return automation.probe("fixture")

    def test_empty_is_distinct_from_unknown(self):
        self.assertEqual(self.probe_result(0, "empty\n"), "empty")
        self.assertEqual(self.probe_result(1, stderr="Application isn't running. (-600)"), "unavailable")
        self.assertEqual(self.probe_result(1, stderr="Not authorized. (-1743)"), "unavailable")
        self.assertEqual(self.probe_result(0, "unexpected"), "unavailable")
        self.assertEqual(self.probe_result(0, "ready\n"), "ready")
        self.assertEqual(self.probe_result(0, "not_running\n"), "not_running")
        self.assertEqual(self.probe_result(1, stderr="UTM is not ready to accept commands"), "library_unready")

    def test_probe_is_bounded_and_does_not_consume_stdin(self):
        with patch.object(automation, "application_bundle", return_value=Path('/fixture/UTM.app')), \
             patch.object(automation.subprocess, "run", side_effect=subprocess.TimeoutExpired("probe", 7)) as run:
            self.assertEqual(automation.probe("fixture"), "unavailable")
            self.assertEqual(run.call_args.kwargs["timeout"], 7)
            self.assertNotIn("input", run.call_args.kwargs)
            self.assertEqual(run.call_args.args[0][-1], str(Path('/fixture/UTM.app')))
            self.assertIn('application appPath is running', run.call_args.args[0][-2])

    def test_custom_executable_never_probes_real_app(self):
        with patch.object(automation.subprocess, "run") as run:
            self.assertEqual(automation.probe("/fixture/utmctl"), "not_applicable")
            run.assert_not_called()

    @unittest.skipIf(os.name == "nt", "POSIX UTM wrapper")
    def test_unavailable_bridge_never_launches_cli(self):
        import cli
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"MACHINE_CONTROL_UTM_DIAGNOSTICS_DIR": directory}), \
             patch.object(cli, "automation_probe", return_value="unavailable"), \
             patch.object(cli.subprocess, "Popen") as launch:
            self.assertEqual(cli.run("diagnostic", "/fixture/utmctl", ["status", "private-vm"]), 69)
            launch.assert_not_called()
            text = (Path(directory) / "calls.jsonl").read_text()
            self.assertIn('utm_automation_unavailable', text)
            self.assertNotIn('private-vm', text)
            self.assertNotIn('"event":"spawn"', text)

    @unittest.skipIf(os.name == "nt", "POSIX shell helpers")
    def test_library_recovery_refuses_unknown_without_cli_or_open(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, prefix, func in [('windows', 'WINVM', 'winvm'), ('linux', 'LINUXVM', 'linuxvm')]:
                script = f'''source "$1"
{func}_utm_automation_state() {{ echo unavailable; }}
{func}_load_utm_library
'''
                env = {**os.environ, f"{prefix}_CONFIG_FILE": "/dev/null",
                       f"{prefix}_TARGET_FILE": "/dev/null", f"{prefix}_PROVIDER": "utm-macos",
                       f"{prefix}_UTM_BUNDLE": directory, f"{prefix}_UTMCTL": "/must/not/execute"}
                result = subprocess.run(['bash', '-c', script, '_', str(ROOT / f'platforms/{name}/scripts/common.sh')],
                                        env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertIn('refusing library recovery', result.stderr)

    def test_factory_probes_also_gate_cli_dispatch(self):
        for name, prefix, method in [('windows', 'WINVM', 'command'), ('linux', 'LINUXVM', 'call')]:
            path = ROOT / f'platforms/{name}/scripts/factory-stages.py'
            spec = importlib.util.spec_from_file_location('factory_' + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with patch.dict(os.environ, {f'{prefix}_UTMCTL': '/fixture/utmctl'}), \
                 patch.object(module, 'utm_automation_probe', return_value='unavailable'), \
                 patch.object(module.subprocess, 'run') as run, \
                 patch.object(module.subprocess, 'Popen') as popen:
                self.assertEqual(getattr(module, method)('/fixture/utmctl', 'list'), (False, ''))
                run.assert_not_called()
                popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()

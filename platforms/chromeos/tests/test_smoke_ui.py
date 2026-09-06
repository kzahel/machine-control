import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / 'scripts/smoke-ui.py'
spec = importlib.util.spec_from_file_location('smoke_ui', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SmokeUISelectionTests(unittest.TestCase):
    def test_pinned_settings_does_not_replace_panel_button(self):
        shelf = {'location': {'x': 300, 'y': 750, 'width': 48, 'height': 48}}
        gear = {'location': {'x': 1100, 'y': 700, 'width': 32, 'height': 32}}
        baseline = {'matches': [shelf]}
        self.assertEqual(module.new_button_indices(baseline, {'matches': [shelf, gear]}), [2])
        self.assertEqual(module.new_button_indices(baseline, {'matches': [gear, shelf]}), [1])
        self.assertEqual(module.new_button_indices(baseline, baseline), [])
        self.assertEqual(module.new_button_indices({'matches': []}, {'matches': [gear]}), [1])

    def test_hidden_or_unlocated_buttons_cannot_be_targets(self):
        hidden = {'location': {'x': 1}, 'state': {'invisible': True}}
        offscreen = {'location': {'x': 2}, 'state': {'offscreen': True}}
        self.assertEqual(module.new_button_indices({'matches': []}, {'matches': [hidden, offscreen, {}]}), [])


class SmokeFailureTests(unittest.TestCase):
    def test_failed_capture_keeps_failure_exit_status(self):
        import os
        import shutil
        import subprocess
        import tempfile
        if os.name == 'nt' or not shutil.which('bash'):
            self.skipTest('Requires POSIX bash')
        source = (Path(__file__).resolve().parents[1] / 'scripts/smoke-test.sh').read_text()
        function = 'capture_step() {' + source.split('capture_step() {', 1)[1].split('\n}', 1)[0] + '\n}'
        with tempfile.TemporaryDirectory() as directory:
            script = function + '\nrecord() { :; }\ncapture_step fixture result false\n'
            result = subprocess.run(['bash', '-c', script], env={**os.environ, 'output': directory})
            self.assertEqual(result.returncode, 1)

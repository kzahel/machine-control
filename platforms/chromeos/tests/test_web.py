import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'chromeos_web', Path(__file__).resolve().parents[1] / 'web/server.py'
)
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class WebInputTests(unittest.TestCase):
    def test_untrusted_input_names_never_reach_a_subprocess(self):
        events = [
            {'type': 'shortcut', 'key': 'a', 'mods': ['ctrl", "cmd":"type']},
            {'type': 'shortcut', 'key': '--help'},
            {'type': 'shortcut', 'key': 'a', 'mods': 'ctrl'},
            {'type': 'mouse_click', 'button': 'left", "cmd":"type'},
            {'type': 'mouse_click', 'button': ['left']},
        ]
        for event in events:
            with self.subTest(event=event), patch.object(web.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    web.Handler._handle_event(None, event)
                run.assert_not_called()

    def test_valid_input_names_are_normalized_and_keep_argument_boundaries(self):
        with patch.object(web.subprocess, 'run', return_value=SimpleNamespace(returncode=0)) as run:
            result = web.Handler._handle_event(None, {
                'type': 'shortcut', 'mods': ['CTRL', 'shift'], 'key': 'F12'
            })
            self.assertTrue(result['ok'])
            self.assertEqual(run.call_args.args[0], [web.CHROMEOS_BIN, 'shortcut', 'ctrl', 'shift', 'f12'])
            result = web.Handler._handle_event(None, {
                'type': 'mouse_click', 'button': 'RIGHT', 'x': 3.4, 'y': 9.6
            })
            self.assertTrue(result['ok'])
            self.assertEqual(run.call_args.args[0], [web.CHROMEOS_BIN, 'mouse-click', 'right', '3', '10'])

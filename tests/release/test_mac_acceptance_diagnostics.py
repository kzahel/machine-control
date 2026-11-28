import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MACOS = ROOT / 'tests/macos'


def load(script):
    spec = importlib.util.spec_from_file_location(script, MACOS / (script + '.py'))
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, 'path', [str(MACOS), *sys.path]):
        spec.loader.exec_module(module)
    return module


controller = load('packaged-acceptance')
reliability = load('reliability-acceptance')
display = load('acceptance_display')


class AcceptanceDiagnosticsTests(unittest.TestCase):
    def test_display_requests_deliver_one_fresh_frame_to_the_owned_stage(self):
        stage = Path('/fixture/owned-stage')
        token = b'9' * 32
        line = display.MARKER + token + b'\n'
        capture = mock.Mock(return_value=display.PNG + b'fixture')
        send = mock.Mock()
        seen = set()
        self.assertFalse(display.deliver_frame(b'ordinary guest output\n', stage, capture, send, seen))
        self.assertTrue(display.deliver_frame(line, stage, capture, send, seen))
        send.assert_called_once_with(stage / f'display-frame-{token.decode()}.png', capture.return_value)
        for invalid in (line, display.MARKER + b'../../../outside.png\n'):
            with self.assertRaises(ValueError):
                display.deliver_frame(invalid, stage, capture, send, seen)
        capture.assert_called_once_with()

    def test_display_refusal_cannot_deliver_a_frame(self):
        capture = mock.Mock(return_value=b'unavailable')
        send = mock.Mock()
        with self.assertRaises(ValueError):
            display.deliver_frame(display.MARKER + b'8' * 32 + b'\n', Path('/fixture/stage'),
                                  capture, send, set())
        send.assert_not_called()

    def test_a_stale_cover_cannot_pass_the_pre_unlock_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'observe-acceptance-cover').touch()
            frame = display.PNG + b'stale covered display'
            result = SimpleNamespace(returncode=0, stdout=b'{"sampledConcealment":true,"coverTextObserved":true}')
            with (mock.patch.object(display, 'request_frame', return_value=frame),
                  mock.patch.object(display.subprocess, 'run', return_value=result)):
                with self.assertRaises(AssertionError):
                    display.observe_cover(root / 'source', root, 'baseline', covered=False)

    def test_failed_guest_check_is_journaled_after_observed_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app = root / 'fixture.app'
            (app / 'Contents').mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(
                {'CFBundleIdentifier': 'org.machine-control.app'}))
            output = root / 'private evidence'
            output.mkdir()
            args = SimpleNamespace(app=app, output=output, package_directory=None, repeat=1, seed=1,
                soak_seconds=0, faults=False, model_only=False, dialog_probe=False, source_sdk=False,
                covered_probe=False, covered_recovery=False, remote_arming=False, development=True)
            report = controller.FailureReport(output, workspace_owned=False)
            notes = []

            def run(command, **kwargs):
                if command[1:] == ['target', 'doctor']:
                    return SimpleNamespace(stdout=b'{"states":{"power":"off"}}')
                if command[1:3] == ['usage', 'note']:
                    notes.append(kwargs['input'].decode())
                    self.assertEqual(report.cleanup['power'], 'restored')
                return SimpleNamespace(returncode=0)

            calls = []

            def check_output(command, **_):
                calls.append(command[1:])
                if command[1:] == ['target', 'doctor']:
                    return b'{"ready":true}'
                if command[1:] == ['target', 'status']:
                    return b'{"data":{"powerState":"off"}}'
                if command[-1].endswith('/results/cleanup.json'):
                    return b'{"restored":true,"appStateRestored":true}'
                return b''

            process = SimpleNamespace(stdout=[
                b'MC_ACCEPTANCE_CHECK covered_control verify_concealment\n',
                b'MC_ACCEPTANCE_CHECK covered_control secret-guest-text\n',
                b'raw private assertion with credentials\n',
            ], wait=lambda **_: 1, poll=lambda: 1)
            with (
                mock.patch.object(subprocess, 'run', side_effect=run),
                mock.patch.object(subprocess, 'check_output', side_effect=check_output),
                mock.patch.object(subprocess, 'Popen', return_value=process),
                mock.patch.object(controller.signal, 'signal'),
                mock.patch.dict(controller.os.environ, {'MACHINE_CONTROL_CLAIM_ID': 'fixture'}),
                mock.patch.object(controller.sys, 'stdout', SimpleNamespace(buffer=mock.Mock(), flush=mock.Mock())),
            ):
                with self.assertRaises(AssertionError):
                    controller.run_controller(args, ROOT, ['fixture-mc'], report)
                report.publish(['fixture-mc'])

            document = json.loads((output / 'failure.json').read_text())
            self.assertEqual((document['phase'], document['check']), ('covered_control', 'verify_concealment'))
            self.assertEqual(document['cleanup']['appState'], 'restored')
            self.assertEqual((output / 'failure.json').stat().st_mode & 0o777, 0o600)
            self.assertLess(calls.index(['target', 'shutdown']), calls.index(['target', 'status']))
            self.assertEqual(len(notes), 1)
            self.assertIn(str((output / 'failure.json').resolve()), notes[0])
            self.assertNotIn('secret-guest-text', notes[0])
            self.assertNotIn('raw private assertion', notes[0])

    def test_failed_child_still_contributes_exact_scope_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            start = dict(schema='machine-control-run/v0', event='acquired',
                         claimId='fixture-claim', workspaceHandle='fixture-workspace', logicalTarget='fixture')
            end = dict(start, event='finished', childExitCode=1, exitCode=1,
                       cleanup={'claim': 'released', 'workspace': 'released'})
            for expected, completion in [('released', end), ('unknown', dict(end, workspaceHandle='other'))]:
                report = controller.FailureReport(output, workspace_owned=True)
                report.step('covered_control', 'observe_same_owner')
                report.failed(AssertionError('fixture'))
                report.publish()
                with (
                    mock.patch.object(sys, 'path', [str(MACOS), *sys.path]),
                    mock.patch.object(subprocess, 'run'),
                ):
                    reliability.report_campaign_failure(output, [start, completion], RuntimeError(), ['fixture-mc'])
                result = json.loads((output / 'failure.json').read_text())
                self.assertEqual(result['check'], 'observe_same_owner')
                self.assertEqual(result['cleanup']['workspace'], expected)

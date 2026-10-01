"""Local Windows selection and artifact/coordination boundaries."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('winhost', ROOT / 'platforms/windows/host/winhost.py')
winhost = importlib.util.module_from_spec(spec)
spec.loader.exec_module(winhost)


class WindowsHostTests(unittest.TestCase):
    def test_installation_refuses_component_or_wrong_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'runtime').mkdir()
            with mock.patch.dict(os.environ, LOCALAPPDATA=directory,
                                 MACHINE_CONTROL_DESKTOP_INSTALL_DIR=directory):
                for instance in ('default', 'desktop'):
                    (root / 'runtime/desktop-runtime.json').write_text(json.dumps({
                        'schema': 'machine-control-desktop-runtime/v0',
                        'profile': 'ordinary_user_desktop', 'instance': instance}))
                    if instance == 'default':
                        with self.assertRaises(ValueError):
                            winhost.installation()
                    else:
                        self.assertEqual(winhost.installation(), root)

    def test_no_dispatch_without_live_claim(self):
        with mock.patch.dict(os.environ, MACHINE_CONTROL_CLAIM_ID=''), \
                mock.patch.object(winhost, 'call') as call:
            self.assertEqual(winhost.main(['control', '{"operation":"status"}']), 1)
            call.assert_not_called()

    def test_opaque_artifact_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.dict(os.environ, LOCALAPPDATA=directory), \
                mock.patch.object(winhost, 'session_id', return_value=2):
            root = Path(directory) / 'MachineControl/workstation/desktop/session-2/artifacts'
            root.mkdir(parents=True)
            identifier = 'a' * 32
            content = b'\x89PNG\r\n\x1a\nfixture'
            (root / (identifier + '.png')).write_bytes(content)
            output = Path(directory) / 'output.png'
            self.assertEqual(winhost.artifact_fetch([identifier, str(output)]), 0)
            self.assertEqual(output.read_bytes(), content)
            with self.assertRaises(FileExistsError):
                winhost.artifact_fetch([identifier, str(output)])
            with self.assertRaises(ValueError):
                winhost.artifact_fetch(['../elsewhere', str(output)])

    def test_claim_cannot_override_identity(self):
        with mock.patch.object(winhost, 'claim') as claim:
            self.assertEqual(winhost.main(['claim-acquire', '--json', '--resource-id=elsewhere']), 2)
            claim.assert_not_called()

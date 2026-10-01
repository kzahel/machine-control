"""Independent updater authentication, provenance, and companion staging."""
import base64
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


package = module('windows_desktop_package', 'desktop/scripts/windows-package.py')
prepare = module('windows_desktop_prepare', 'desktop/scripts/prepare-windows.py')
REVISION = 'a' * 40
VERSION = '0.4.0'
TARGET = 'x86_64-pc-windows-msvc'


@unittest.skipUnless(shutil.which('minisign'), 'minisign required')
class WindowsDesktopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.directory = self.root / 'candidate'
        self.directory.mkdir()
        key, public = self.root / 'key', self.root / 'pub'
        subprocess.run(['minisign', '-G', '-W', '-s', str(key), '-p', str(public)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        config = self.root / 'desktop/src-tauri/tauri.conf.json'
        config.parent.mkdir(parents=True)
        config.write_text(json.dumps({'plugins': {'updater': {'pubkey': base64.b64encode(public.read_bytes()).decode()}}}))
        self.installer = self.directory / 'MachineControl_0.4.0_x64-setup.exe'
        self.installer.write_bytes(b'installer fixture')
        subprocess.run(['minisign', '-S', '-s', str(key), '-m', str(self.installer), '-t', 'timestamp:0\tversion:' + VERSION],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        signature = Path(str(self.installer) + '.minisig')
        Path(str(self.installer) + '.sig').write_bytes(base64.b64encode(signature.read_bytes()))
        (self.directory / 'payload.json').write_text(json.dumps({'schema': 'machine-control-desktop-payload/v0',
            'sourceRevision': REVISION, 'target': TARGET, 'version': VERSION, 'files': []}))
        package.evidence(self.directory, target=TARGET, version=VERSION, revision=REVISION, run='123.1')

    def verify(self, **changes):
        with patch.object(package, 'ROOT', self.root):
            return package.verify(self.directory, revision=REVISION, version=VERSION, run='123.1', target=TARGET, **changes)

    def test_real_installer_signature_and_tamper_rejection(self):
        self.assertEqual(self.verify(tamper=True)['arch'], 'x64')
        self.installer.write_bytes(self.installer.read_bytes() + b'changed')
        with self.assertRaises(ValueError): self.verify()
        package.evidence(self.directory, target=TARGET, version=VERSION, revision=REVISION, run='123.1')
        with self.assertRaises(ValueError): self.verify()  # Rehashed metadata cannot forge the signature.

    def test_source_workflow_target_and_version_fences(self):
        path = self.directory / 'build.json'
        original = json.loads(path.read_text())
        for key, bad in [('sourceRevision', 'b' * 40), ('sourceState', 'local_working_tree'),
                         ('workflowAttempt', '2'), ('arch', 'arm64'), ('target', 'aarch64-pc-windows-msvc'), ('version', '0.3.5')]:
            value = dict(original); value[key] = bad; path.write_text(json.dumps(value))
            with self.subTest(key=key), self.assertRaises(ValueError): self.verify()
        path.write_text(json.dumps(original))

    def test_missing_duplicate_and_unsafe_assets(self):
        path = self.directory / 'build.json'
        original = json.loads(path.read_text())
        variants = [original['artifacts'][:-1], original['artifacts'] + original['artifacts'][:1],
                    [dict(original['artifacts'][0], name='..\\outside.exe')]]
        for files in variants:
            changed = dict(original, artifacts=files); path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): self.verify()

    def test_authenticated_version_comment(self):
        signature = Path(str(self.installer) + '.sig')
        text = base64.b64decode(signature.read_bytes()).decode().replace('version:0.4.0', 'version:9.0.0')
        signature.write_bytes(base64.b64encode(text.encode()))
        package.evidence(self.directory, target=TARGET, version=VERSION, revision=REVISION, run='123.1')
        with self.assertRaises(ValueError): self.verify()


class CompanionTests(unittest.TestCase):
    def test_staging_preserves_provider_binding_and_omits_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source = root / 'source'; source.mkdir()
            provider = source / 'providers/cua/cua-driver.exe'; provider.parent.mkdir(parents=True); provider.write_bytes(b'provider')
            build = {'sourceRevision': REVISION, 'sourceDirty': False, 'runtime': 'win-x64', 'providerDigest': package.digest(provider)}
            (source / 'build.json').write_text(json.dumps(build))
            (source / 'machine-control-windows.exe').write_bytes(b'companion')
            (source / 'unlock-setup.exe').write_bytes(b'omit')
            output = root / 'output'
            prepare.stage(source, output, REVISION, 'win-x64')
            self.assertTrue((output / 'machine-control-windows.exe').is_file())
            self.assertFalse((output / 'unlock-setup.exe').exists())
            self.assertEqual(json.loads((output / 'desktop-runtime.json').read_text())['profile'], 'ordinary_user_desktop')
            with self.assertRaises(ValueError): prepare.stage(source, output, REVISION, 'win-x64')
            build['sourceDirty'] = True; (source / 'build.json').write_text(json.dumps(build))
            with self.assertRaises(ValueError): prepare.stage(source, root / 'dirty', REVISION, 'win-x64')


if __name__ == '__main__': unittest.main()

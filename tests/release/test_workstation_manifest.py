"""Apply the real signature rejection suite to the workstation artifact set."""
import importlib.util
from pathlib import Path
from unittest import mock
import test_manifest

spec = importlib.util.spec_from_file_location('workstation_manifest', Path(__file__).resolve().parents[2] / 'release/workstation-manifest.py')
workstation_manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workstation_manifest)


class WorkstationManifestTests(test_manifest.ManifestTests):
    def setUp(self):
        patch = mock.patch('test_manifest.manifest', workstation_manifest)
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_modified_payload(self):
        (self.packages / workstation_manifest.PACKAGES['win-x64']).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'modified artifact'):
            self.verify()

    def test_missing_platform(self):
        (self.packages / workstation_manifest.PACKAGES['win-arm64']).unlink()
        with self.assertRaisesRegex(ValueError, 'Missing regular artifact'):
            self.verify()

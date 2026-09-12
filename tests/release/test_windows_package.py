import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE_PATH = Path(__file__).resolve().parents[2] / 'release/windows-package.py'
spec = importlib.util.spec_from_file_location('windows_package', MODULE_PATH)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class WindowsPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        provider = self.root / 'providers/cua/cua-driver.exe'
        provider.parent.mkdir(parents=True)
        provider.write_bytes(b'pinned-provider')
        (self.root / 'build.json').write_text(json.dumps({
            'schema': 'machine-control-windows-build/v0', 'profile': 'workstation',
            'protocol': 'machine-control/v0', 'runtime': 'win-arm64',
            'providerDigest': package.digest(provider)}))

    def test_package_identity_changes_with_payload_and_is_repeatable(self):
        first = package.finalize(self.root)
        self.assertEqual(first, package.finalize(self.root))
        (self.root / 'runtime.exe').write_bytes(b'changed')
        self.assertNotEqual(first['packageId'], package.finalize(self.root)['packageId'])

    def test_rejects_changed_provider(self):
        (self.root / 'providers/cua/cua-driver.exe').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Provider bytes'):
            package.finalize(self.root)

    def test_nested_manifests_are_hashed(self):
        nested = self.root / 'providers/package.json'
        nested.write_text('{}')
        self.assertIn('providers/package.json', package.finalize(self.root)['files'])

    def test_rejects_symlink(self):
        try:
            (self.root / 'linked').symlink_to(self.root / 'build.json')
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaisesRegex(ValueError, 'symbolic links'):
            package.finalize(self.root)


if __name__ == '__main__':
    unittest.main()

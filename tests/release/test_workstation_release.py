"""Consumer manifests bind version, publisher, protocol and exact artifacts."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('product', Path(__file__).resolve().parents[2] / 'release/workstation-release.py')
product = importlib.util.module_from_spec(spec)
spec.loader.exec_module(product)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for target, filename in product.preview.PACKAGES.items():
            (self.root / filename).write_bytes(target.encode())
        self.args = (self.root, 'a' * 40, '123.1', '0.1.0', 'Test publisher')

    def test_contract(self):
        product.create(*self.args)
        value = json.loads((self.root / 'release.json').read_text())
        self.assertEqual(value['tag'], 'workstation-v0.1.0')
        self.assertEqual(value['consumerProtocol'], 1)
        self.assertEqual(len(value['artifacts']), 2)
        self.assertEqual(value['publisher'], 'Test publisher')

    def test_reject_invalid_versions(self):
        for version in ('01.2.3', '1.2', '1.2.3-beta', '../1.2.3', '1.2.3;echo nope'):
            with self.assertRaises(ValueError):
                product.create(*self.args[:3], version, self.args[4])

    @unittest.skipUnless(shutil.which('minisign'), 'minisign is required')
    def test_real_signature_and_tampering(self):
        key, pub = self.root / 'test.key', self.root / 'test.pub'
        subprocess.run(['minisign', '-G', '-W', '-s', str(key), '-p', str(pub)], check=True, stdout=subprocess.DEVNULL)
        product.create(*self.args)
        manifest = self.root / 'release.json'
        subprocess.run(['minisign', '-S', '-s', str(key), '-m', str(manifest)], check=True)
        product.verify(*self.args, pub)
        with self.assertRaisesRegex(ValueError, 'identity'):
            product.verify(*self.args[:3], '0.2.0', self.args[4], pub)
        manifest.write_bytes(manifest.read_bytes() + b' ')
        with self.assertRaises(subprocess.CalledProcessError):
            product.verify(*self.args, pub)

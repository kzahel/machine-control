"""Exercise real signatures and rejection of incomplete or tampered sets."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("manifest", ROOT / "release/manifest.py")
manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(manifest)


@unittest.skipUnless(shutil.which("minisign"), "minisign is required")
class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packages = self.root / "packages"
        self.packages.mkdir()
        self.key = self.root / "test.key"
        self.public_key = self.root / "test.pub"
        self.revision = "a" * 40
        self.run_id = "123.1"
        subprocess.run(["minisign", "-G", "-W", "-s", str(self.key),
                        "-p", str(self.public_key)], check=True,
                       stdout=subprocess.DEVNULL)
        for target, name in manifest.PACKAGES.items():
            (self.packages / name).write_bytes(target.encode())
        manifest.create(self.packages, self.revision, self.run_id)
        self.sign()

    def sign(self):
        subprocess.run(["minisign", "-S", "-s", str(self.key), "-m",
                        str(self.packages / "manifest.json")], check=True,
                       stdout=subprocess.DEVNULL)

    def verify(self, revision=None, run=None):
        manifest.verify(self.packages, revision or self.revision,
                        run or self.run_id, self.public_key)

    def test_complete_signed_set(self):
        self.verify()

    def test_modified_payload(self):
        (self.packages / manifest.PACKAGES["linux-x64"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "modified artifact"):
            self.verify()

    def test_missing_platform(self):
        (self.packages / manifest.PACKAGES["windows-x64"]).unlink()
        with self.assertRaisesRegex(ValueError, "Missing regular artifact"):
            self.verify()

    def test_modified_manifest(self):
        path = self.packages / "manifest.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()

    def test_another_source_or_attempt(self):
        with self.assertRaisesRegex(ValueError, "identity"):
            self.verify(revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "identity"):
            self.verify(run="123.2")

    def test_wrong_signing_key(self):
        other_key = self.root / "other.key"
        subprocess.run(["minisign", "-G", "-W", "-s", str(other_key),
                        "-p", str(self.root / "other.pub")], check=True,
                       stdout=subprocess.DEVNULL)
        subprocess.run(["minisign", "-S", "-s", str(other_key), "-m",
                        str(self.packages / "manifest.json")], check=True,
                       stdout=subprocess.DEVNULL)
        with self.assertRaises(subprocess.CalledProcessError):
            self.verify()

    def test_valid_signature_with_omitted_platform(self):
        path = self.packages / "manifest.json"
        value = json.loads(path.read_text())
        value["artifacts"].pop()
        path.write_text(json.dumps(value))
        self.sign()
        with self.assertRaisesRegex(ValueError, "modified artifact"):
            self.verify()


if __name__ == "__main__":
    unittest.main()

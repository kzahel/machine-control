import shutil
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prepare-bootstrap.py"
spec = importlib.util.spec_from_file_location("prepare_bootstrap", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class PrepareBootstrapTests(unittest.TestCase):
    def test_bundle_preserves_source_and_exports_only_public_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key"
            subprocess.run(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C",
                 "comment $(touch should-not-exist)", "-f", str(key)], check=True,
            )
            output = root / "bootstrap.sh"
            module.prepare(key.with_suffix(".pub"), output)
            bundle = output.read_text()
            self.assertTrue(bundle.endswith(SCRIPT.with_name("bootstrap.sh").read_text()))
            self.assertNotIn("PRIVATE KEY", bundle)
            self.assertNotIn("should-not-exist", bundle)
            subprocess.run(["bash", "-n", str(output)], check=True)
            prefix = "\n".join(bundle.splitlines()[:3])
            value = subprocess.check_output(
                ["bash", "-c", prefix + '\nprintf "%s" "$CHROMEOS_TESTBED_CONTROLLER_PUBKEY"'],
                text=True,
            )
            self.assertEqual(value.split(), key.with_suffix(".pub").read_text().split()[:2])
            with self.assertRaises(FileExistsError):
                module.prepare(key.with_suffix(".pub"), output)
            with self.assertRaises(ValueError):
                module.prepare(key, root / "private.sh")

    def test_rejects_malformed_and_multiple_keys_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key = root / "key.pub"
            for value in ["", "ssh-ed25519 invalid", "ssh-ed25519 a\nssh-ed25519 b"]:
                key.write_text(value)
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    module.prepare(key, root / "bootstrap.sh")
                self.assertFalse((root / "bootstrap.sh").exists())

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "client"))
import storage_analysis as storage


class StorageAnalysisTests(unittest.TestCase):
    def test_sparse_file_is_not_virtual_capacity_and_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "disk.qcow2"
            with path.open("wb") as file:
                file.seek(16 * 1024 * 1024)
                file.write(b"fixture")
            before = path.stat()
            result = storage.analyze([Path(tmp)])
            self.assertEqual(result["summary"]["logicalBytes"], before.st_size)
            self.assertEqual(result["summary"]["exclusiveBytes"], None)
            self.assertEqual(result["summary"]["reclaimableBytes"], None)
            self.assertEqual(path.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertFalse(result["images"][0]["automaticDeletionAllowed"])

    def test_links_overlapping_roots_and_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); factory = root / ".factory.local"; factory.mkdir()
            disk = factory / "saved.img"; disk.write_bytes(b"x" * 4096)
            (root / "secrets").mkdir()
            (root / "secrets/private.img").write_bytes(b"secret")
            if sys.platform != "win32":
                (root / "alias.img").symlink_to(disk)
                (root / "loop").symlink_to(root, target_is_directory=True)
                (root / "hardlink.img").hardlink_to(disk)
            result = storage.analyze([root, factory], minimum_bytes=0)
            self.assertEqual(result["summary"]["imagesFound"], 1)
            self.assertNotIn("secret", json.dumps(result["images"]))

    def test_limits_report_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(3):
                (root / f"{i}.img").write_bytes(b"x")
            result = storage.analyze([root], minimum_bytes=0, max_results=1)
            self.assertFalse(result["coverage"]["complete"])
            self.assertEqual(result["summary"]["imagesFound"], 3)
            self.assertEqual(len(result["images"]), 1)

    def test_offline_cli_and_unknown_provider_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); factory = root / ".factory.local"; factory.mkdir()
            (factory / "retained.qcow2").write_bytes(b"x")
            reply = subprocess.run([sys.executable, str(ROOT / "client/machine_control.py"),
                                    "--registry", str(root / "absent.json"), "storage",
                                    "analyze", "--root", str(factory), "--minimum-bytes", "0"],
                                   text=True, capture_output=True)
            self.assertEqual(reply.returncode, 0, reply.stderr)
            result = json.loads(reply.stdout)
            self.assertEqual(result["images"][0]["category"], "factory_artifact_review")
            self.assertTrue(result["readOnly"])


if __name__ == "__main__":
    unittest.main()

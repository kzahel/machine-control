"""Trust boundaries for standalone Python staging and installed payloads."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prepare = module("prepare_cli", "desktop/scripts/prepare-cli.py")
payload = module("cli_payload", "desktop/scripts/cli-payload.py")


class CliPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def archive(self, name="python/bin/python3", link=None):
        archive = self.root / "python.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            item = tarfile.TarInfo(name)
            if link:
                item.type = tarfile.SYMTYPE
                item.linkname = link
                output.addfile(item)
            else:
                item.size = 7
                output.addfile(item, io.BytesIO(b"fixture"))
        return archive

    def test_archive_root_and_traversal_refusal(self):
        for name in ["outside", "python/../../outside"]:
            with self.assertRaises((ValueError, tarfile.FilterError)):
                prepare.extract(self.archive(name), self.root / "out")
        self.assertFalse((self.root / "outside").exists())

    def test_escaping_runtime_link_is_refused(self):
        with self.assertRaises((ValueError, tarfile.FilterError)):
            prepare.extract(self.archive(link="../../../outside"), self.root / "out")

    def test_download_requires_pinned_digest_and_repairs_bad_cache(self):
        archive = self.archive()
        pin = {"url": archive.as_uri(), "sha256": hashlib.sha256(archive.read_bytes()).hexdigest()}
        cache = self.root / "cache"
        cached = prepare.fetch(pin, cache)
        cached.write_bytes(b"tampered")
        self.assertEqual(prepare.fetch(pin, cache).read_bytes(), archive.read_bytes())
        with self.assertRaisesRegex(ValueError, "digest"):
            prepare.fetch({**pin, "sha256": "0" * 64}, cache)
        self.assertFalse((cache / ("0" * 64 + ".tar.gz")).exists())

    def test_payload_modification_addition_and_missing_dependency_refuse(self):
        root = self.root / "payload"
        root.mkdir()
        (root / "client-runtime.json").write_text(json.dumps({"clientProtocol": 1}))
        script = root / "client.py"
        script.write_text("original")
        prepare.inventory(root)
        self.assertEqual(payload.verify(root)["clientProtocol"], 1)
        script.write_text("modified")
        with self.assertRaises(ValueError):
            payload.verify(root)
        script.write_text("original")
        extra = root / "injected.py"
        extra.write_text("injected")
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            payload.verify(root)
        extra.unlink()
        script.unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            payload.verify(root)

    def test_payload_receipt_cannot_escape_the_installation(self):
        (self.root / "files.json").write_text(json.dumps({
            "schema": "machine-control-client-files/v1", "files": [{"path": "../outside"}]}))
        with self.assertRaisesRegex(ValueError, "path"):
            payload.verify(self.root)


if __name__ == "__main__":
    unittest.main()

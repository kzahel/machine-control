"""Portable discovery/installer contracts; native stream behavior has a Windows runner."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


identity = load("discovery_identity", "client/agent_interface.py")
path = load("windows_path", "desktop/native/windows-path.py")


class DiscoveryTests(unittest.TestCase):
    def test_identity_receipt_stays_exact_and_paths_follow_relocation(self):
        receipt = {"schema": identity.SCHEMA, "clientProtocol": 1,
                   "distribution": "desktop", "platform": "windows",
                   "command": "commands/machine-control.cmd"}
        with tempfile.TemporaryDirectory(prefix="relocated client ") as tmp:
            root = Path(tmp) / "mc-cli"
            root.mkdir()
            (root / "client-runtime.json").write_text(json.dumps(receipt))
            with patch.object(identity, "ROOT", root):
                self.assertEqual(identity.identity(), receipt)
                details = identity.identity(paths=True)
                self.assertEqual(details.pop("paths")["launcher"], str((Path(tmp) / "machine-control.exe").resolve()))
                self.assertEqual(details, receipt)
                self.assertEqual(identity.identity(), receipt)

    def test_path_registration_preserves_long_values_and_ownership(self):
        original = ";".join(f"C:\\tools\\{i}" for i in range(3000))
        directory = r"C:\Apps\Machine Control"
        added, owned = path.change(original, directory, True, False)
        self.assertTrue(owned)
        self.assertEqual(added, original + ";" + directory)
        self.assertEqual(path.change(added, directory, True, owned), (added, True))
        self.assertEqual(path.change(added, directory, False, owned), (original, False))

    def test_user_owned_equivalent_and_other_installations_survive(self):
        directory = r"C:\Apps\Machine Control"
        original = r'"c:\apps\machine control\";C:\Other\Machine Control'
        self.assertEqual(path.change(original, directory, True, False), (original, False))
        self.assertEqual(path.change(original, directory, False, False), (original, False))
        # A user has rewritten an owned entry; no longer our exact bytes.
        self.assertEqual(path.change(original, directory, False, True), (original, False))

    def test_empty_and_trailing_path_entries(self):
        directory = r"C:\Apps\Machine Control"
        self.assertEqual(path.change("", directory, True, False), (directory, True))
        self.assertEqual(path.change(directory, directory, False, True), ("", False))
        self.assertEqual(path.change("C:\\tools;", directory, True, False),
                         ("C:\\tools;;" + directory, True))


if __name__ == "__main__":
    unittest.main()

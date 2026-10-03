"""Portable discovery/installer contracts; native stream behavior has a Windows runner."""
import importlib.util
import json
import contextlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
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
launch = load("windows_launch", "desktop/native/windows-launch.py")


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
        with patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Apps"}):
            expanded = r"%LOCALAPPDATA%\Machine Control"
            self.assertEqual(path.change(expanded, directory, True, False), (expanded, False))

    def test_empty_and_trailing_path_entries(self):
        directory = r"C:\Apps\Machine Control"
        self.assertEqual(path.change("", directory, True, False), (directory, True))
        self.assertEqual(path.change(directory, directory, False, True), ("", False))
        self.assertEqual(path.change("C:\\tools;", directory, True, False),
                         ("C:\\tools;;" + directory, True))

    def test_existing_resident_is_verified_and_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "runtime").mkdir()
            (root / "machine-control.exe").touch()
            resident = root / "runtime/machine-control-windows.exe"
            resident.touch()
            def session(_pid, pointer):
                pointer._obj.value = 1
                return 1
            windll = SimpleNamespace(kernel32=SimpleNamespace(ProcessIdToSessionId=session))
            status = {"data": {"desktopProduct": True, "processId": 42, "ready": True}}
            with patch.object(launch, "__file__", str(root / "mc-cli/windows-launch.py")), \
                    patch.object(launch.ctypes, "windll", windll, create=True), \
                    patch.object(launch, "probe", return_value=status), \
                    patch.object(launch, "process_image", return_value=resident) as image, \
                    patch.object(launch.subprocess, "Popen") as spawn:
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(launch.main(), 0)
                self.assertIn("agent instructions", output.getvalue())
                spawn.assert_not_called()
                image.return_value = root / "other-install/runtime.exe"
                with self.assertRaisesRegex(RuntimeError, "Another or unidentified"):
                    launch.main()
                spawn.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows registry API required")
    def test_native_registry_long_path_preserves_type_and_other_entries(self):
        import uuid
        import winreg
        key = r"Software\MachineControl\DiscoveryTests" + "\\" + uuid.uuid4().hex
        create = winreg.CreateKey
        directory = r"C:\Discovery Fixture\Machine Control"
        original = ";".join(f"C:\\tools\\{i}" for i in range(2500))
        try:
            with create(winreg.HKEY_CURRENT_USER, key + r"\Environment") as environment:
                winreg.SetValueEx(environment, "Path", 0, winreg.REG_SZ, original)
            def isolated(hive, name):
                return create(hive, key + r"\Environment" if name == "Environment" else name)
            with patch.object(winreg, "CreateKey", side_effect=isolated), \
                    patch.object(path, "STATE", key + r"\Ownership"):
                path.apply(directory, "enable")
                path.apply(directory, "enable")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key + r"\Environment") as environment:
                    self.assertEqual(winreg.QueryValueEx(environment, "Path"),
                                     (original + ";" + directory, winreg.REG_SZ))
                path.apply(directory, "remove")
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key + r"\Environment") as environment:
                    self.assertEqual(winreg.QueryValueEx(environment, "Path"), (original, winreg.REG_SZ))
        finally:
            def remove_tree(name):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, name) as handle:
                        while True:
                            try:
                                child = winreg.EnumKey(handle, 0)
                            except OSError:
                                break
                            remove_tree(name + "\\" + child)
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, name)
                except FileNotFoundError:
                    pass
            remove_tree(key)


if __name__ == "__main__":
    unittest.main()

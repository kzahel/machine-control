"""Regression coverage for the repository's validation entry point."""

import importlib.machinery
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("repository_check", str(ROOT / "bin/check"))
spec = importlib.util.spec_from_loader(loader.name, loader)
check = importlib.util.module_from_spec(spec)
loader.exec_module(check)


@unittest.skipUnless(shutil.which("bash"), "Bash is unavailable")
class ShellSyntaxTests(unittest.TestCase):
    def test_invalid_later_script_is_rejected_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed"
            first = root / "first.sh"
            first.write_text(f"#!/usr/bin/env bash\ntouch '{marker}'\n")
            second = root / "second.sh"
            second.write_text("#!/usr/bin/env bash\nif then\n")
            with patch.object(check, "tracked_files", return_value=[first, second]):
                with self.assertRaises(SystemExit) as failure:
                    check.validate_shell()
            self.assertNotEqual(failure.exception.code, 0)
            self.assertFalse(marker.exists())

    def test_valid_scripts_include_extensionless_bash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = [root / "first.sh", root / "second"]
            for script in scripts:
                script.write_text("#!/usr/bin/env bash\ntrue\n")
            with patch.object(check, "tracked_files", return_value=scripts):
                check.validate_shell()


if __name__ == "__main__":
    unittest.main()

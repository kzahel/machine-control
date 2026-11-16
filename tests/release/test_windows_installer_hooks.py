"""Compile the real hooks, including both installer/uninstaller code paths."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class InstallerHookTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("makensis"), "NSIS compiler required")
    def test_hooks_compile(self):
        with tempfile.TemporaryDirectory(prefix="mc-nsis-") as temporary:
            root = Path(temporary)
            native = root / "native"
            native.mkdir()
            for name in ("windows-installer-hooks.nsh", "windows-payload.ps1"):
                shutil.copyfile(ROOT / "desktop/native" / name, native / name)
            helper = root / "src-tauri/native/runtime/machine-control-windows.exe"
            helper.parent.mkdir(parents=True)
            helper.write_bytes(b"compile-only embedded resource")
            source = root / "fixture.nsi"
            source.write_text('''Unicode true
!include LogicLib.nsh
!include FileFunc.nsh
!define MAINBINARYNAME "machine-control"
!define PRODUCTNAME "Machine Control"
!define MANUPRODUCTKEY "Software\\MachineControl\\HookFixture"
Var UpdateMode
Var PassiveMode
!macro CheckIfAppIsRunning executable product
!macroend
!include "native/windows-installer-hooks.nsh"
Name "Hook compile fixture"
OutFile "fixture.exe"
Section Install
  !insertmacro NSIS_HOOK_PREINSTALL
  WriteUninstaller "$INSTDIR\\uninstall.exe"
  !insertmacro NSIS_HOOK_POSTINSTALL
SectionEnd
Section Uninstall
  !insertmacro NSIS_HOOK_PREUNINSTALL
  !insertmacro NSIS_HOOK_POSTUNINSTALL
SectionEnd
''')
            result = subprocess.run(["makensis", "/V2" if os.name == "nt" else "-V2", str(source)], cwd=root,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((root / "fixture.exe").is_file())


if __name__ == "__main__":
    unittest.main()

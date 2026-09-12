#!/usr/bin/env python3
"""Compile the native elevation entry with its immutable setup script embedded."""
import argparse
import base64
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def build(runtime, output):
    if os.name != 'nt':
        raise ValueError('The bootstrap requires the Windows SDK and MSVC')
    vswhere = Path(os.environ['ProgramFiles(x86)']) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    installation = subprocess.check_output([str(vswhere), '-latest', '-products', '*',
        '-requires', 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64', '-property', 'installationPath'], text=True).strip()
    if not installation:
        raise ValueError('MSVC installation not found')
    publisher = os.environ.get('WINDOWS_SIGNER_NAME', '')
    prefix = "$expectedPublisher = '" + publisher.replace("'", "''") + "'\n"
    script = base64.b64encode((prefix + (ROOT / 'release/unlock-setup.ps1').read_text()).encode('utf-16-le')).decode()
    if len(script) > 28000:
        raise ValueError('Embedded command exceeds the bounded Windows command line')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='mc-unlock-build-') as temporary:
        work = Path(temporary)
        (work / 'unlock_setup_script.h').write_text('static const wchar_t MC_UNLOCK_SCRIPT[] =\n' +
            '\n'.join('L"' + script[i:i+1000] + '"' for i in range(0, len(script), 1000)) + ';\n')
        compiler = ['cl', '/nologo', '/W4', '/WX', '/O2', '/MT', '/guard:cf', '/D_CRT_SECURE_NO_WARNINGS',
                    '/I' + str(work), str(ROOT / 'release/unlock-setup.c'), '/Fe' + str(output),
                    '/link', 'advapi32.lib', 'shell32.lib', '/DYNAMICBASE', '/NXCOMPAT']
        # cmd.exe is required only for MSVC's environment script. Paths are local
        # build paths; no secret or proposal is interpolated into this command.
        architecture = 'x64_arm64' if runtime == 'win-arm64' else 'x64'
        vcvars = str(Path(installation) / 'VC/Auxiliary/Build/vcvarsall.bat')
        if any(character in value for value in [vcvars, *compiler] for character in '%!^&|<>\r\n'):
            raise ValueError('Unsupported cmd.exe metacharacter in build path')
        # A batch file keeps cmd syntax separate from Python/CRT argument
        # escaping: embedded quotes passed as one argv would become literal \".
        batch = '@echo off\ncall "' + vcvars + '" ' + architecture + '\n'
        batch += 'if errorlevel 1 exit /b %errorlevel%\n' + subprocess.list2cmdline(compiler) + '\n'
        batch += 'exit /b %errorlevel%\n'
        (work / 'build.cmd').write_text(batch)
        subprocess.run(['cmd.exe', '/d', '/c', 'build.cmd'], cwd=work, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', choices=['win-x64', 'win-arm64'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.runtime, args.output.resolve())

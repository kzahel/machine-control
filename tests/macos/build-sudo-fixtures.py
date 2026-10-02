#!/usr/bin/env python3
"""Build native sudo helpers and a dedicated-appliance Accessibility driver.

The driver is a transient source-native Machine Control test variant with
the existing consent identity. Never install or run it on a workstation.
"""
import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--arch', choices=['arm64', 'x86_64'], default='arm64')
parser.add_argument('--signing-identity', default='-')
args = parser.parse_args()
target = {'arm64': 'aarch64-apple-darwin', 'x86_64': 'x86_64-apple-darwin'}[args.arch]
subprocess.run(['cargo', 'build', '--locked', '--release', '--target', target,
                '--manifest-path', str(ROOT / 'platforms/macos/sudo/Cargo.toml')], check=True)
args.output.mkdir(parents=True, exist_ok=True)
for name, identifier in [('mc-sudo', 'org.machine-control.sudo'),
                         ('mc-sudo-askpass', 'org.machine-control.sudo.askpass')]:
    destination = args.output / name
    shutil.copy2(ROOT / 'platforms/macos/sudo/target' / target / 'release' / name, destination)
    subprocess.run(['codesign', '--force', '--options', 'runtime', '--sign', args.signing_identity,
                    '--identifier', identifier, str(destination)], check=True)
driver = args.output / 'Sudo Test Driver.app'
(driver / 'Contents/MacOS').mkdir(parents=True, exist_ok=True)
(driver / 'Contents/Info.plist').write_bytes(plistlib.dumps({
    'CFBundleIdentifier': 'org.machine-control.app',
    'CFBundleExecutable': 'driver',
    'CFBundleName': 'Machine Control Sudo Test Driver',
    'CFBundlePackageType': 'APPL',
    'LSUIElement': True,
}))
subprocess.run(['xcrun', 'swiftc', '-O', '-target', args.arch + '-apple-macos13.0',
                str(ROOT / 'platforms/macos/sudo/Native.swift'),
                str(ROOT / 'tests/macos/sudo-ui-driver/main.swift'),
                '-o', str(driver / 'Contents/MacOS/driver')], check=True)
subprocess.run(['codesign', '--force', '--options', 'runtime', '--sign', args.signing_identity,
                '--requirements', '=designated => identifier "org.machine-control.app"',
                str(driver)], check=True)
print('Native helper pair and dedicated-appliance driver built')

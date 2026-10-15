#!/usr/bin/env python3
"""Compile/sign the owned probe and fixture; never launch either executable."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import subprocess


def build(output: Path) -> None:
    if not output.is_absolute():
        raise ValueError('--output must be absolute')
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    source = Path(__file__).resolve().parent
    app = output / 'IdentityFixture.app'
    macos = app / 'Contents' / 'MacOS'
    macos.mkdir(parents=True)
    info = dict(CFBundleIdentifier='org.machine-control.native-identity.fixture',
                CFBundleExecutable='IdentityFixture', CFBundleName='Native Identity Fixture',
                CFBundlePackageType='APPL', NSHighResolutionCapable=True)
    (app / 'Contents' / 'Info.plist').write_bytes(plistlib.dumps(info))
    probe_app = output / 'IdentityProbe.app'
    probe_macos = probe_app / 'Contents' / 'MacOS'
    probe_macos.mkdir(parents=True)
    probe_info = dict(info, CFBundleIdentifier='org.machine-control.native-identity.probe',
                      CFBundleExecutable='IdentityProbe', CFBundleName='Native Identity Probe', LSUIElement=True)
    (probe_app / 'Contents' / 'Info.plist').write_bytes(plistlib.dumps(probe_info))
    probe = probe_macos / 'IdentityProbe'
    for name, binary in [('Fixture.swift', macos / 'IdentityFixture'), ('Probe.swift', probe)]:
        subprocess.run(['swiftc', '-O', str(source / name), '-o', str(binary)], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(app)], check=True)
    subprocess.run(['codesign', '--force', '--sign', '-', str(probe_app)], check=True)
    manifest = dict(schema='machine-control/native-identity-build/v1',
                    swift=subprocess.check_output(['swiftc', '--version'], text=True).strip(),
                    source_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(source.iterdir()) if p.suffix in ('.swift', '.py')},
                    binary_sha256={str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (macos / 'IdentityFixture', probe)})
    (output / 'build.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)

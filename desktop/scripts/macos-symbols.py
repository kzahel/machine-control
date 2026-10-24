#!/usr/bin/env python3
"""Archive matching Mac executable/framework symbols separately from packages."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tarfile

BINARIES = {'macui': 'Contents/MacOS/macui',
            'MCResident': 'Contents/Frameworks/MCResident.framework/MCResident'}


def uuids(path):
    text = subprocess.check_output(['xcrun', 'dwarfdump', '--uuid', str(path)], text=True)
    values = re.findall(r'^UUID: ([A-Fa-f0-9-]{36}) \(([^)]+)\)', text, re.M)
    if not values:
        raise ValueError('Missing Mach-O UUID')
    return sorted([uuid.lower(), arch] for uuid, arch in values)


def verify(app, directory):
    manifest = json.loads((directory / 'symbols.json').read_text())
    if manifest.get('schema') != 'machine-control-macos-symbols/v0':
        raise ValueError('Unknown symbol manifest')
    if set(manifest['images']) != set(BINARIES):
        raise ValueError('Incomplete symbol coverage')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if (manifest['sourceRevision'] != info.get('MCSourceRevision') or
            manifest['version'] != info['CFBundleShortVersionString']):
        raise ValueError('Symbol source/version does not match application')
    for name, relative in BINARIES.items():
        value = manifest['images'][name]
        symbol = directory / (name + '.dSYM')
        if uuids(app / relative) != value['uuids'] or uuids(symbol) != value['uuids']:
            raise ValueError('Symbols do not match final application UUIDs')
        dwarf = symbol / 'Contents/Resources/DWARF' / name
        if hashlib.sha256(dwarf.read_bytes()).hexdigest() != value['sha256']:
            raise ValueError('Changed symbol data')
        debug = subprocess.check_output(['xcrun', 'dwarfdump', '--debug-info', '--recurse-depth=1', str(symbol)], text=True)
        if 'DW_TAG_compile_unit' not in debug:
            raise ValueError('Empty debug information; matching UUID alone is insufficient')
    return manifest


def create(app, output, revision, native_symbols):
    if not re.fullmatch('[a-f0-9]{40}', revision):
        raise ValueError('Expected exact source revision')
    output.mkdir(parents=True, exist_ok=False)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info.get('MCSourceRevision') != revision:
        raise ValueError('Application source revision mismatch')
    manifest = {'schema': 'machine-control-macos-symbols/v0', 'sourceRevision': revision,
                'version': info['CFBundleShortVersionString'], 'images': {}}
    for name, relative in BINARIES.items():
        symbol = output / (name + '.dSYM')
        if name == 'MCResident':
            if native_symbols is None:
                raise ValueError('Supply the completed Swift dSYM; temporary objects no longer exist')
            shutil.copytree(native_symbols, symbol)
        else:
            subprocess.run(['xcrun', 'dsymutil', str(app / relative), '-o', str(symbol)], check=True)
        dwarf = symbol / 'Contents/Resources/DWARF' / name
        manifest['images'][name] = {'uuids': uuids(app / relative),
                                   'sha256': hashlib.sha256(dwarf.read_bytes()).hexdigest()}
    (output / 'symbols.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verify(app, output)
    with tarfile.open(output / 'symbols.tar.gz', 'w:gz') as archive:
        for name in ['symbols.json', *[key + '.dSYM' for key in BINARIES]]:
            archive.add(output / name, arcname=name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['create', 'verify'])
    p.add_argument('app', type=Path)
    p.add_argument('directory', type=Path)
    p.add_argument('--revision')
    p.add_argument('--native-symbols', type=Path)
    a = p.parse_args()
    if a.command == 'create':
        create(a.app, a.directory, a.revision or '', a.native_symbols)
    else:
        verify(a.app, a.directory)
    print('Matching executable and native-framework symbols verified')


if __name__ == '__main__':
    main()

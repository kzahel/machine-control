"""Verify every full byte of a privately bundled policy payload."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(root):
    root = root.resolve(strict=True)
    value = json.loads((root / 'payload.json').read_text())
    if (value.get('schema') != 'machine-control-policy-payload/v1'
            or value.get('engine') != 'node' or value.get('executable') != 'node.exe'
            or value.get('arguments') != ['policy/node/main.ts']
            or value.get('target') not in {'win-arm64', 'win-x64'}):
        raise ValueError('Unexpected Windows policy payload identity')
    files = value['files']
    if not {'node.exe', 'LICENSE.node', 'policy/node/main.ts', 'policy/node_modules/ws/LICENSE'}.issubset(files):
        raise ValueError('Incomplete policy payload')
    for name, item in files.items():
        if not isinstance(name, str) or '\\' in name or ':' in name or name.startswith('/') or any(p in {'', '.', '..'} for p in name.split('/')):
            raise ValueError('Unsafe policy payload path')
        path = root / name
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents:
            raise ValueError('Missing or linked policy payload')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if path.stat().st_size != item['bytes'] or digest != item['sha256']:
            raise ValueError('Policy payload bytes changed')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(files) | {'payload.json'}:
        raise ValueError('Unexpected policy payload file set')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    verify(args.directory)
    print('Full policy payload bytes verified')

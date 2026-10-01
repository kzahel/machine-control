"""Verify final installer authentication/provenance, independently of CI trust."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {'x86_64-pc-windows-msvc': 'x64', 'aarch64-pc-windows-msvc': 'arm64'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def evidence(directory, *, target, version, revision, run):
    if target not in TARGETS or not re.fullmatch(r'[0-9a-f]{40}', revision) or not re.fullmatch(r'\d+\.\d+', run):
        raise ValueError('Expected exact source, workflow, and Windows target')
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise ValueError('Expected stable semantic version')
    installers = list(directory.glob('*-setup.exe'))
    if len(installers) != 1 or not Path(str(installers[0]) + '.sig').is_file():
        raise ValueError('Exactly one final signed installer and updater signature required')
    files = [installers[0], Path(str(installers[0]) + '.sig'), directory / 'payload.json']
    if not files[-1].is_file():
        raise ValueError('Final installed payload inventory required')
    value = {'schema': 'machine-control-desktop-build/v0', 'platform': 'windows',
             'target': target, 'arch': TARGETS[target], 'version': version,
             'bundleIdentifier': 'org.machine-control.app', 'sourceRevision': revision,
             'sourceState': 'ci_checkout', 'workflowRun': run.split('.')[0], 'workflowAttempt': run.split('.')[1],
             'artifacts': [{'name': file.name, 'size': file.stat().st_size, 'sha256': digest(file)} for file in files]}
    (directory / 'build.json').write_text(json.dumps(value, indent=2) + '\n')


def verify(directory, *, revision, version, run=None, target=None, tamper=False):
    value = json.loads((directory / 'build.json').read_text(encoding='utf-8-sig'))
    if (value.get('schema') != 'machine-control-desktop-build/v0' or value.get('platform') != 'windows'
            or value.get('bundleIdentifier') != 'org.machine-control.app'
            or value.get('sourceState') != 'ci_checkout' or value.get('sourceRevision') != revision
            or value.get('version') != version or value.get('target') not in TARGETS
            or value.get('arch') != TARGETS[value['target']]
            or (target is not None and value['target'] != target)
            or (run is not None and f"{value.get('workflowRun')}.{value.get('workflowAttempt')}" != run)):
        raise ValueError('Windows candidate identity mismatch')
    names = set()
    for item in value['artifacts']:
        name = item['name']
        if name in names or '/' in name or '\\' in name or name in {'', '.', '..'}:
            raise ValueError('Unsafe or duplicate artifact name')
        names.add(name)
        file = directory / name
        if file.stat().st_size != item['size'] or digest(file) != item['sha256']:
            raise ValueError('Final artifact bytes changed')
    installers = [name for name in names if name.endswith('-setup.exe')]
    if len(installers) != 1 or names != {installers[0], installers[0] + '.sig', 'payload.json'}:
        raise ValueError('Incomplete final Windows artifact set')
    payload = json.loads((directory / 'payload.json').read_text(encoding='utf-8-sig'))
    if (payload.get('schema') != 'machine-control-desktop-payload/v0'
            or payload.get('sourceRevision') != revision or payload.get('version') != version
            or payload.get('target') != value['target']):
        raise ValueError('Installed payload identity mismatch')
    payload_names = set()
    for item in payload.get('files', []):
        name = item.get('name', '')
        if (not isinstance(name, str) or name in payload_names or not name
                or '\\' in name or ':' in name or name.startswith('/')
                or any(part in {'', '.', '..'} for part in name.split('/'))
                or not isinstance(item.get('size'), int) or item['size'] < 0
                or not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', ''))):
            raise ValueError('Unsafe or incomplete installed payload inventory')
        payload_names.add(name)
    required = {'machine-control.exe', 'uninstall.exe', 'runtime/desktop-runtime.json',
                'runtime/machine-control-windows.exe', 'runtime/package.cat',
                'runtime/providers/cua/cua-driver.exe'}
    if not required.issubset(payload_names):
        raise ValueError('Installed inventory must be relative to the product root')
    with tempfile.TemporaryDirectory(prefix='mc-windows-verify-') as tmp:
        root = Path(tmp)
        config = json.loads((ROOT / 'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8-sig'))
        public = root / 'updater.pub'
        public.write_bytes(base64.b64decode(config['plugins']['updater']['pubkey'], validate=True))
        signature = root / 'installer.sig'
        signature.write_bytes(base64.b64decode((directory / (installers[0] + '.sig')).read_text().strip(), validate=True))
        installer = directory / installers[0]
        def check(file):
            return subprocess.run(['minisign', '-V', '-p', str(public), '-m', str(file), '-x', str(signature)],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0
        if not check(installer):
            raise ValueError('Installer updater signature failed')
        comments = [line for line in signature.read_text().splitlines() if line.startswith('trusted comment: ')]
        versions = [field.removeprefix('version:') for line in comments for field in line.split('\t') if field.startswith('version:')]
        if len(comments) != 1 or versions != [version]:
            raise ValueError('Authenticated installer version mismatch')
        if tamper:
            modified = root / 'tampered-setup.exe'
            modified.write_bytes(installer.read_bytes() + b'tampered')
            if check(modified):
                raise ValueError('Modified installer signature was accepted')
    return value


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['evidence', 'verify'])
    p.add_argument('directory', type=Path)
    p.add_argument('--revision', required=True)
    p.add_argument('--version', required=True)
    p.add_argument('--run')
    p.add_argument('--target', choices=TARGETS)
    p.add_argument('--test-tampering', action='store_true')
    args = p.parse_args()
    if args.command == 'evidence':
        if not args.run or not args.target: p.error('evidence requires --run and --target')
        evidence(args.directory, target=args.target, version=args.version, revision=args.revision, run=args.run)
    else:
        verify(args.directory, revision=args.revision, version=args.version, run=args.run, target=args.target, tamper=args.test_tampering)
        print('Windows installer signature, signed version, provenance, and tamper rejection verified')

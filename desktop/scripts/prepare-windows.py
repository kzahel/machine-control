"""Stage a self-contained desktop companion from the audited component payload."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[2]
OMIT = {'unlock-setup.exe', 'workstation.ps1', 'unlock.md', 'unlock-controller.py', 'README.md', 'package.cat'}


def stage(payload, output, revision, runtime):
    if runtime not in {'win-x64', 'win-arm64'} or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected an exact source revision and supported Windows runtime')
    build = json.loads((payload / 'build.json').read_text())
    if build['sourceRevision'] != revision or build['sourceDirty'] or build['runtime'] != runtime:
        raise ValueError('Companion source/runtime identity mismatch')
    if output.exists():
        raise ValueError('Refusing to replace a staged companion')
    output.mkdir(parents=True)
    for file in payload.iterdir():
        if file.name in OMIT:
            continue
        if file.is_symlink():
            raise ValueError('Unexpected companion link')
        if file.is_dir():
            shutil.copytree(file, output / file.name)
        else:
            shutil.copyfile(file, output / file.name)
    shutil.copytree(ROOT / 'providers/chrome-extension', output / 'browser-extension',
                    ignore=shutil.ignore_patterns('store', '*.py', '*.md', '*.svg', '__pycache__'))
    shutil.copyfile(ROOT / 'desktop/native/windows-runtime-README.txt', output / 'README.txt')
    (output / 'desktop-runtime.json').write_text(json.dumps({
        'schema': 'machine-control-desktop-runtime/v0', 'sourceRevision': revision,
        'runtime': runtime, 'providerDigest': build['providerDigest'],
        'profile': 'ordinary_user_desktop', 'instance': 'desktop',
    }, indent=2) + '\n')
    provider = output / 'providers/cua/cua-driver.exe'
    with provider.open('rb') as stream:
        provider_digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if provider_digest != build['providerDigest']:
        raise ValueError('Companion does not contain its compiled provider digest')


def write_helper_release(output, version):
    if not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Expected a numeric desktop release version')
    manifest = output / 'helper-release.json'
    if manifest.exists() or (output / 'package.cat').exists():
        raise ValueError('Inventory must be made once before catalog signing')
    runtime = json.loads((output / 'desktop-runtime.json').read_text())['runtime']
    files = {}
    for path in sorted(output.rglob('*')):
        if path.is_symlink():
            raise ValueError('Unexpected helper payload link')
        if path.is_file():
            name = path.relative_to(output).as_posix()
            if not re.fullmatch(r'[A-Za-z0-9_@.\-]+(?:/[A-Za-z0-9_@.\-]+)*', name) or any(
                part.endswith('.') or re.fullmatch(r'CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]', part.split('.')[0], re.I)
                for part in name.split('/')
            ):
                raise ValueError('Unsupported helper release file name: ' + name)
            with path.open('rb') as stream:
                files[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    manifest.write_text(json.dumps({
        'schema': 'machine-control-desktop-helper-release/v1',
        'version': version,
        'runtime': runtime,
        'files': files,
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('payload', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'desktop/src-tauri/native/runtime')
    p.add_argument('--revision', required=True)
    p.add_argument('--runtime', required=True)
    p.add_argument('--helper-release-version',
                   help='Inventory the staged and Authenticode-signed payload before signing its catalog')
    args = p.parse_args()
    if args.helper_release_version:
        write_helper_release(args.output, args.helper_release_version)
    else:
        stage(args.payload, args.output, args.revision, args.runtime)

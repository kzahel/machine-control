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
    shutil.copytree(ROOT / 'providers/chrome-extension', output / 'browser-extension')
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


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('payload', type=Path)
    p.add_argument('--output', type=Path, default=ROOT / 'desktop/src-tauri/native/runtime')
    p.add_argument('--revision', required=True)
    p.add_argument('--runtime', required=True)
    args = p.parse_args()
    stage(args.payload, args.output, args.revision, args.runtime)

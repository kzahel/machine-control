"""Stage the pinned private shared-policy child for either Mac product shell."""
import argparse
import hashlib
import json
import importlib.util
from pathlib import Path
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[4]


def stage(output, arch):
    spec = importlib.util.spec_from_file_location('policy_package', ROOT / 'runtime/scripts/package.py')
    package = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(package)
    cache = ROOT / '.artifacts/runtime-cache'
    cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.policy-stage-', dir=output.parent) as temporary:
        payload = Path(temporary) / 'shared-policy'
        package.build('node', 'darwin-' + {'arm64': 'arm64', 'x86_64': 'x64'}[arch], payload, cache, None)
        value = json.loads((payload / 'payload.json').read_text())
        value['qualificationOnly'] = False
        value['consumer'] = 'macos-resident'
        (payload / 'payload.json').write_text(json.dumps(value, indent=2) + '\n')
        if output.exists():
            shutil.rmtree(output)
        payload.rename(output)


def seal(root):
    # Signing changes only the nested Mach-O. Seal its final bytes before the
    # enclosing app signature; scripts/dependencies retain their pinned hashes.
    path = root / 'payload.json'
    value = json.loads(path.read_text())
    executable = root / 'node'
    with executable.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    value['files']['node'] = {'sha256': digest, 'bytes': executable.stat().st_size}
    path.write_text(json.dumps(value, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arch', choices=['arm64', 'x86_64'])
    parser.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    if args.seal:
        seal(args.output)
    elif args.arch:
        stage(args.output, args.arch)
    else:
        parser.error("--arch is required for staging")

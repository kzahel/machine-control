#!/usr/bin/env python3
"""Build an inspectable Windows workstation payload; publisher signing is a CI step."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def fetch_provider(directory, rid):
    metadata = json.loads((ROOT / 'providers/cua/provider.json').read_text())
    pin = metadata['windows'][rid]
    cache = ROOT / '.cache/providers/cua' / metadata['version']
    cache.mkdir(parents=True, exist_ok=True)

    def download(url, name, expected):
        target = cache / name
        if target.is_file() and digest(target) == expected:
            return target
        with tempfile.NamedTemporaryFile(dir=cache, delete=False) as temporary:
            staging = Path(temporary.name)
        try:
            with urllib.request.urlopen(url, timeout=60) as response, staging.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(staging) != expected:
                raise ValueError('Pinned provider download digest mismatch: ' + name)
            staging.replace(target)
        finally:
            staging.unlink(missing_ok=True)
        return target

    archive_path = download(metadata['upstream'] + '/releases/download/' + metadata['releaseTag'] + '/' + pin['archive'],
                            pin['archive'], pin['archiveSha256'])
    provider = directory / 'providers/cua'
    provider.mkdir(parents=True, exist_ok=True)
    binary = provider / 'cua-driver.exe'
    with zipfile.ZipFile(archive_path) as archive_file:
        with archive_file.open('cua-driver.exe') as source, binary.open('wb') as output:
            shutil.copyfileobj(source, output)
    if digest(binary) != pin['executableSha256']:
        raise ValueError('Pinned provider executable digest mismatch')
    license_file = download(metadata['license']['url'], 'LICENSE.md', metadata['license']['sha256'])
    shutil.copyfile(license_file, provider / 'LICENSE.md')
    shutil.copyfile(ROOT / 'providers/cua/provider.json', provider / 'provider.json')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(directory):
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Package cannot contain symbolic links')
        if path.is_file() and path != directory / 'package.json':
            files[path.relative_to(directory).as_posix()] = digest(path)
    return files


def build(directory, rid, revision, provider_digest=None):
    if directory.exists():
        raise ValueError('Build output must not already exist')
    if not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Full source revision required')
    directory.mkdir(parents=True)
    command = ['dotnet', 'publish', str(ROOT / 'src/MachineControl.Windows/MachineControl.Windows.csproj'),
               '-c', 'Release', '-r', rid, '--self-contained', 'true', '-o', str(directory)]
    if provider_digest:
        if not re.fullmatch('[0-9a-f]{64}', provider_digest):
            raise ValueError('Invalid signed provider digest')
        command.append('-p:CuaExecutableSha256=' + provider_digest)
    subprocess.run(command, check=True)
    # Default build keeps the exact pinned provider bytes. Signing builds replace
    # this directory with the separately verified/signed copy before finalizing.
    fetch_provider(directory, rid)
    subprocess.run(['python', str(ROOT / 'release/build-unlock-setup.py'),
                    '--runtime', rid, '--output', str(directory / 'unlock-setup.exe')], check=True)
    shutil.copyfile(ROOT / 'release/workstation.ps1', directory / 'workstation.ps1')
    shutil.copyfile(ROOT / 'release/windows-workstation.md', directory / 'README.md')
    shutil.copyfile(ROOT / 'release/windows-unlock.md', directory / 'unlock.md')
    shutil.copyfile(ROOT / 'release/unlock-controller.py', directory / 'unlock-controller.py')
    shutil.copyfile(ROOT / 'LICENSE', directory / 'LICENSE')
    assets = json.loads((ROOT / 'src/MachineControl.Windows/obj/project.assets.json').read_text())
    dependencies = {name: item['path'] for name, item in assets['libraries'].items()
                    if item['type'] == 'package'}
    for framework in assets['project']['frameworks'].values():
        runtime_packs = {name.lower() + '.runtime.' + rid
                         for name in framework.get('frameworkReferences', {})}
        for item in framework.get('downloadDependencies', []):
            if item['name'].lower() in runtime_packs:
                version = item['version'].strip('[]').split(',')[0].strip()
                dependencies[item['name'] + '/' + version] = item['name'].lower() + '/' + version
    notices = directory / 'notices'
    for name, relative in dependencies.items():
        candidates = [Path(folder) / relative for folder in assets['packageFolders']]
        source = next((path for path in candidates if path.is_dir()), None)
        if source is None:
            raise ValueError('Missing restored dependency: ' + name)
        legal = [path for path in source.iterdir() if path.is_file()
                 and ('license' in path.name.lower() or 'notice' in path.name.lower())]
        if not any('license' in path.name.lower() for path in legal):
            raise ValueError('Dependency requires a license audit: ' + name)
        destination = notices / name.replace('/', '-')
        destination.mkdir(parents=True)
        for path in legal:
            shutil.copyfile(path, destination / path.name)
    (notices / 'dependencies.json').write_text(json.dumps(sorted(dependencies), indent=2) + '\n')
    for path in directory.glob('*.pdb'):
        path.unlink()
    (directory / 'build.json').write_text(json.dumps({
        'schema': 'machine-control-windows-build/v0', 'profile': 'workstation',
        'protocol': 'machine-control/v0', 'runtime': rid, 'sourceRevision': revision,
        'sdkVersion': subprocess.check_output(['dotnet', '--version'], text=True).strip(),
        'sourceDirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip()),
        'providerDigest': provider_digest or json.loads((ROOT / 'providers/cua/provider.json').read_text())['windows'][rid]['executableSha256'],
    }, indent=2) + '\n')


def finalize(directory):
    build_info = json.loads((directory / 'build.json').read_text())
    if digest(directory / 'providers/cua/cua-driver.exe') != build_info['providerDigest']:
        raise ValueError('Provider bytes differ from the compiled build identity')
    files = inventory(directory)
    package_id = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    value = {'schema': 'machine-control-windows-package/v0', 'packageId': package_id,
             **build_info, 'files': files}
    value['schema'] = 'machine-control-windows-package/v0'
    (directory / 'package.json').write_text(json.dumps(value, indent=2) + '\n')
    return value


def archive(directory, output):
    if (directory / 'package.cat').exists():
        value = json.loads((directory / 'package.json').read_text())
        actual = inventory(directory)
        actual.pop('package.cat')
        if actual != value['files']:
            raise ValueError('Catalogued payload changed after finalization')
    else:
        value = finalize(directory)
    output.mkdir(parents=True, exist_ok=True)
    path = output / ('machine-control-workstation-' + value['runtime'] + '.zip')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive_file:
        for source in sorted(directory.rglob('*')):
            if source.is_file():
                archive_file.write(source, source.relative_to(directory))
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'fetch-provider', 'finalize', 'archive'])
    parser.add_argument('directory', type=Path)
    parser.add_argument('--runtime', choices=['win-arm64', 'win-x64'])
    parser.add_argument('--revision')
    parser.add_argument('--provider-digest')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'build':
        if not args.runtime or not args.revision:
            parser.error('build requires --runtime and --revision')
        build(args.directory.resolve(), args.runtime, args.revision, args.provider_digest)
    elif args.command == 'fetch-provider':
        if not args.runtime:
            parser.error('fetch-provider requires --runtime')
        fetch_provider(args.directory, args.runtime)
    elif args.command == 'finalize':
        print(json.dumps(finalize(args.directory)))
    else:
        if not args.output:
            parser.error('archive requires --output')
        print(archive(args.directory, args.output))

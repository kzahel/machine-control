#!/usr/bin/env python3
"""Validate tagged desktop publication and stage the verified Mac asset set."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('release_changelog', ROOT / 'release/changelog.py')
changelog_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(changelog_notes)
REPOSITORY = 'kzahel/machine-control'
VERSION = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
TARGETS = {'aarch64-apple-darwin': ('arm64', 'darwin-aarch64'),
           'x86_64-apple-darwin': ('x86_64', 'darwin-x86_64')}


def version_tuple(version):
    if not re.fullmatch(VERSION, version):
        raise ValueError('Expected MAJOR.MINOR.PATCH without leading zeroes')
    return tuple(map(int, version.split('.')))


def notes(version, changelog=None):
    return changelog_notes.notes(version, changelog or ROOT / 'desktop/CHANGELOG.md')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def preflight(version):
    requested = version_tuple(version)
    notes(version)
    for tag in git('tag', '--list', 'desktop-v*').splitlines():
        match = re.fullmatch('desktop-v(' + VERSION + ')', tag)
        if match and version_tuple(match[1]) >= requested:
            raise ValueError('Version must exceed every existing desktop release tag')


def check_tag(tag, version, revision):
    version_tuple(version)
    if tag != 'desktop-v' + version or not re.fullmatch(r'[0-9a-f]{40}', revision):
        raise ValueError('Release tag/version/source mismatch')
    ref = 'refs/tags/' + tag
    if git('cat-file', '-t', ref) != 'tag' or git('rev-parse', ref + '^{commit}') != revision:
        raise ValueError('Annotated release tag must point to this main workflow commit')
    return notes(version)


def check_existing(releases, version):
    requested = version_tuple(version)
    for release in releases:
        if release.get('tag_name') == 'desktop-v' + version:
            raise ValueError('Release already exists; never replace published assets or drafts')
        match = re.fullmatch('desktop-v(' + VERSION + ')', release.get('tag_name', ''))
        if (match and not release.get('draft') and not release.get('prerelease')
                and version_tuple(match[1]) >= requested):
            raise ValueError('Version must exceed every published desktop release')


def stage(directory, output, version, revision, run, body):
    version_tuple(version)
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or not re.fullmatch(r'[0-9]+\.[0-9]+', run):
        raise ValueError('Expected exact source and workflow run identity')
    if output.exists():
        raise ValueError('Refusing to replace an existing staged release')
    payloads = []
    platforms = {}
    for target, (arch, platform) in TARGETS.items():
        source = directory / ('macos-desktop-' + target)
        manifest = json.loads((source / 'build.json').read_text())
        if (manifest.get('schema') != 'machine-control-desktop-build/v0'
                or manifest.get('version') != version
                or manifest.get('sourceRevision') != revision
                or manifest.get('sourceState') != 'ci_checkout'
                or manifest.get('bundleIdentifier') != 'org.machine-control.app'
                or f"{manifest.get('workflowRun')}.{manifest.get('workflowAttempt')}" != run):
            raise ValueError('Candidate identity mismatch')
        archive = f'MachineControl_{version}_{arch}.app.tar.gz'
        expected = {archive, archive + '.sig', f'MachineControl_{version}_{arch}.dmg'}
        artifacts = manifest.get('artifacts', [])
        if len(artifacts) != 3 or {a.get('name') for a in artifacts} != expected:
            raise ValueError('Incomplete or unexpected Mac artifact set')
        for item in artifacts:
            path = source / item['name']
            if (path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']
                    or sha256(path) != item['sha256']):
                raise ValueError('Candidate artifact digest mismatch')
            payloads.append((path, path.name))
        signature = (source / (archive + '.sig')).read_text().strip()
        decoded = base64.b64decode(signature, validate=True).decode('utf-8')
        trusted = [line for line in decoded.splitlines() if line.startswith('trusted comment: ')]
        signed_versions = [field.removeprefix('version:') for line in trusted
                           for field in line.split('\t') if field.startswith('version:')]
        if len(trusted) != 1 or signed_versions != [version]:
            raise ValueError('Updater signed version mismatch')
        payloads.append((source / 'build.json', f'build-macos-{arch}.json'))
        platforms[platform] = {
            'url': f'https://github.com/{REPOSITORY}/releases/download/desktop-v{version}/{archive}',
            'signature': signature,
        }
    # Native signatures, Gatekeeper, notarization, and minisign verification run
    # on both input directories in the publication job before this staging step.
    output.mkdir(parents=True)
    for source, name in payloads:
        shutil.copyfile(source, output / name)
    latest = {'version': version, 'notes': body.strip(),
              'pub_date': datetime.now(timezone.utc).isoformat(), 'platforms': platforms}
    (output / 'latest.json').write_text(json.dumps(latest, indent=2) + '\n')


def check_upload(directory, release, version):
    version_tuple(version)
    if (release.get('tag_name') != 'desktop-v' + version
            or release.get('draft') is not True or release.get('prerelease') is not False):
        raise ValueError('Expected an unpublished desktop draft')
    files = {path.name: path for path in directory.iterdir() if path.is_file()}
    assets = release.get('assets', [])
    if len(assets) != len(files) or {asset.get('name') for asset in assets} != set(files):
        raise ValueError('Uploaded asset set mismatch')
    for asset in assets:
        file = files[asset['name']]
        digest = sha256(file)
        if (asset.get('state') != 'uploaded' or asset.get('size') != file.stat().st_size
                or asset.get('digest') != 'sha256:' + digest):
            raise ValueError('Uploaded asset digest mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('notes', 'preflight'):
        sub.add_parser(name).add_argument('version')
    check = sub.add_parser('check-tag')
    check.add_argument('tag')
    for field in ('version', 'revision'):
        check.add_argument('--' + field, required=True)
    existing = sub.add_parser('check-existing')
    existing.add_argument('file', type=Path)
    existing.add_argument('--version', required=True)
    uploaded = sub.add_parser('check-upload')
    uploaded.add_argument('directory', type=Path)
    uploaded.add_argument('file', type=Path)
    uploaded.add_argument('--version', required=True)
    package = sub.add_parser('stage')
    package.add_argument('directory', type=Path)
    package.add_argument('output', type=Path)
    for field in ('version', 'revision', 'run'):
        package.add_argument('--' + field, required=True)
    args = parser.parse_args()
    if args.command == 'notes':
        print(notes(args.version), end='')
    elif args.command == 'preflight':
        preflight(args.version)
    elif args.command == 'check-tag':
        print(check_tag(args.tag, args.version, args.revision), end='')
    elif args.command == 'check-existing':
        check_existing(json.loads(args.file.read_text()), args.version)
    elif args.command == 'check-upload':
        check_upload(args.directory, json.loads(args.file.read_text()), args.version)
    else:
        stage(args.directory, args.output, args.version, args.revision, args.run, notes(args.version))


if __name__ == '__main__':
    main()

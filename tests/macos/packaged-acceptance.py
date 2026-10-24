#!/usr/bin/env python3
"""Install and exercise an exact signed app in a claimed dedicated Mac VM.

Run on the controller under `machine-control --target macos run`. All evidence
stays in a new private directory outside the checkout. The guest restores its
app/policy/operator state; this runner restores power. No outer UI is used.
Local builds require --development and cannot qualify release acceptance.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import signal
import subprocess
import sys
import tarfile
import tempfile
import uuid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--app', type=Path)
    source.add_argument('--package-directory', type=Path)
    p.add_argument('--team-id')
    p.add_argument('--development', action='store_true')
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--repeat', type=int, default=5)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--soak-seconds', type=int, default=0)
    p.add_argument('--faults', action='store_true')
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    if a.output.resolve().is_relative_to(repo):
        p.error('Raw VM evidence must be outside the public checkout')
    if not os.environ.get('MACHINE_CONTROL_CLAIM_ID'):
        p.error('Run inside a common CLI claim scope')
    if a.app and not a.development:
        p.error('An app without authenticated package metadata requires --development')
    if a.package_directory and not a.team_id:
        p.error('Package verification requires --team-id')
    if not (1 <= a.repeat <= 300 and 0 <= a.soak_seconds <= 1800 and -(2**63) <= a.seed < 2**63):
        p.error('Invalid bounded repeat/soak settings')
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    mc = [str(repo / 'bin/machine-control')]

    def call(*args, **kwargs):
        return subprocess.check_output(mc + list(args), timeout=240, **kwargs)

    def interrupted(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    remote = '/tmp/mc-packaged-' + uuid.uuid4().hex
    # Doctor returns nonzero for a parked guest while still returning its
    # read-only power/identity report. Claim resolution has already succeeded.
    doctor = subprocess.run(mc + ['target', 'doctor'], capture_output=True, timeout=90)
    initial = json.loads(doctor.stdout)['states']['power']
    staged = False
    with tempfile.TemporaryDirectory(prefix='mc-acceptance-extract-') as temporary:
        app = a.app
        manifest = None
        summary = None
        if a.package_directory:
            manifest = json.loads((a.package_directory / 'build.json').read_text())
            if not a.development:
                revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
                assert revision == manifest['sourceRevision'], 'Run the acceptance suite at the exact candidate source'
                assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo), 'Acceptance suite must be clean'
            subprocess.run([sys.executable, str(repo / 'desktop/scripts/verify-package.py'),
                str(a.package_directory), '--revision', manifest['sourceRevision'],
                '--team-id', a.team_id, '--test-tampering'], check=True)
            archives = [a.package_directory / v['name'] for v in manifest['artifacts']
                        if v['name'].endswith('.app.tar.gz')]
            assert len(archives) == 1
            with tarfile.open(archives[0]) as archive:
                archive.extractall(temporary, filter='data')
            app = Path(temporary) / 'Machine Control.app'
        assert app and plistlib.loads((app / 'Contents/Info.plist').read_bytes())['CFBundleIdentifier'] == 'org.machine-control.app'
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
        archive_path = a.output / 'staged-inputs.tar'
        with tarfile.open(archive_path, 'w') as archive:
            archive.add(app, arcname='candidate/Machine Control.app')
            for name in ['tests/macos/packaged-acceptance-guest.py',
                         'tests/macos/browser-file-dialogs.py', 'platforms/chromeos/cdp.py']:
                archive.add(repo / name, arcname='source/' + name)
            archive.add(repo / 'platforms/macos/resident/scripts/install-user.sh', arcname='install-user.sh')
        try:
            call('target', 'up')
            assert json.loads(call('target', 'doctor'))['ready'], 'Guest doctor is not ready'
            call('testbed', '--', 'exec', '/bin/mkdir', '-m', '700', remote)
            staged = True
            with archive_path.open('rb') as stream:
                call('testbed', '--', 'exec', '-i', '/usr/bin/tar', '-xf', '-', '-C', remote, stdin=stream)
            argv = ['os', '--', '/usr/bin/python3', remote + '/source/tests/macos/packaged-acceptance-guest.py',
                    '--stage', remote, '--claim', os.environ['MACHINE_CONTROL_CLAIM_ID'],
                    '--repeat', str(a.repeat), '--seed', str(a.seed), '--soak-seconds', str(a.soak_seconds)]
            if a.faults:
                argv += ['--faults']
            subprocess.run(mc + argv, check=True)
            summary = json.loads(call('os', '--', '/bin/cat', remote + '/results/summary.json'))
        except BaseException:
            subprocess.run(mc + ['usage', 'note', '--kind', 'friction', '--goal', 'Packaged desktop acceptance'],
                input=b'Packaged acceptance failed; inspect controller-private evidence and cleanup status before retrying.\n',
                stdout=subprocess.DEVNULL, timeout=30, check=False)
            raise
        finally:
            try:
                if staged:
                    with (a.output / 'guest-evidence.tar').open('wb') as stream:
                        subprocess.run(mc + ['os', '--', '/usr/bin/tar', '-cf', '-', '-C', remote, 'results'],
                                       stdout=stream, check=False, timeout=90)
                    cleanup = json.loads(call('os', '--', '/bin/cat', remote + '/results/cleanup.json'))
                    (a.output / 'cleanup.json').write_text(json.dumps(cleanup) + '\n')
                    if cleanup['restored']:
                        call('os', '--', '/bin/rm', '-rf', remote)
                    else:
                        raise RuntimeError('Guest restoration incomplete; private backups retained at ' + remote)
            finally:
                if initial == 'suspended':
                    call('target', 'suspend')
                elif initial == 'off':
                    call('target', 'shutdown')
        # Development output is deliberately ineligible as release evidence.
        (a.output / 'identity.json').write_text(json.dumps({'development': a.development,
            'build': manifest, 'seed': a.seed}) + '\n')
        subprocess.run(mc + ['usage', 'note', '--kind', 'summary', '--goal', 'Packaged desktop acceptance'],
            input=('Packaged suite passed ' + str(summary['checks']) + ' checks with seed ' + str(a.seed) +
                   '; app, policy, operator state and power restored; raw evidence remains controller-private.\n').encode(),
            stdout=subprocess.DEVNULL, check=True, timeout=30)
        if not a.development and manifest and a.faults and a.repeat >= 3 and a.soak_seconds >= 120:
            assert summary['faults'] and summary['plannedRestarts'] == 1
            spec = importlib.util.spec_from_file_location('acceptance', repo / 'desktop/scripts/packaged-acceptance.py')
            acceptance = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(acceptance)
            revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
            assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo), 'Acceptance suite must be clean exact source'
            run = f"{manifest['workflowRun']}.{manifest['workflowAttempt']}"
            receipt = {'schema': 'machine-control-packaged-acceptance/v0', 'sourceRevision': revision,
                'version': manifest['version'], 'candidateRun': run,
                'archiveSHA256': next(v['sha256'] for v in manifest['artifacts']
                    if v['name'] == f"MachineControl_{manifest['version']}_arm64.app.tar.gz"),
                'seed': a.seed, 'checks': summary['checks'], 'cycles': summary['repeat'],
                'soakSeconds': a.soak_seconds, 'coverage': sorted(acceptance.COVERAGE),
                'cleanupVerified': cleanup['restored'], 'passed': summary['passed']}
            acceptance.validate(receipt, manifest, revision=revision, version=manifest['version'], run=run)
            (a.output / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print('Packaged acceptance passed; original guest state and power restored', flush=True)


if __name__ == '__main__':
    main()

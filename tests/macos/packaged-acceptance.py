#!/usr/bin/env python3
"""Install and exercise an exact signed app in a claimed dedicated Mac VM.

Run on the controller under `machine-control --target macos run`. All evidence
stays in a new private directory outside the checkout. The guest restores its
app/policy/operator state; this runner restores power. Covered checks observe
the exact Tart window without focusing it or sending input.
Local builds require --development and cannot qualify release acceptance.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from acceptance_diagnostics import FailureReport, announce
from acceptance_display import MARKER, deliver_frame, stage_frame


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
    p.add_argument('--remote-arming', action='store_true')
    p.add_argument('--covered-recovery', action='store_true')
    p.add_argument('--covered-duration', type=int, default=0)
    p.add_argument('--covered-renewal-seconds', type=int, default=0)
    p.add_argument('--model-only', action='store_true')
    p.add_argument('--dialog-probe', action='store_true')
    p.add_argument('--source-sdk', action='store_true')
    p.add_argument('--covered-probe', action='store_true')
    p.add_argument('--defer-failure-note', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--admin-secret-file', type=Path, help='Owner-only canonical VM credential; one-shot native sheet transport only')
    a = p.parse_args()
    if a.source_sdk and not a.development:
        p.error('Source SDK is development-only and cannot qualify a release')
    if a.dialog_probe and (not a.development or a.faults or a.remote_arming or a.covered_recovery or a.model_only or a.covered_probe):
        p.error('Dialog probe is development-only and cannot run a release or protected campaign')
    repo = Path(__file__).resolve().parents[2]
    if a.output.resolve().is_relative_to(repo):
        p.error('Raw VM evidence must be outside the public checkout')
    if not os.environ.get('MACHINE_CONTROL_CLAIM_ID') or not os.environ.get('MACHINE_CONTROL_SCOPE_FILE'):
        p.error('Run inside a common CLI claim scope')
    if a.remote_arming and not os.environ.get('MACHINE_CONTROL_WORKSPACE_HANDLE'):
        p.error('Locked remote-arming acceptance requires a disposable claimed workspace')
    if a.covered_recovery and not (a.remote_arming and a.admin_secret_file):
        p.error('Covered recovery requires remote arming and the canonical credential locator')
    if a.covered_duration != 0 and not (a.covered_recovery and 60 <= a.covered_duration <= 900):
        p.error('Covered duration requires covered recovery and 60-900 seconds')
    if a.covered_renewal_seconds != 0 and not (a.covered_recovery and 120 <= a.covered_renewal_seconds <= 1800):
        p.error('Covered renewal requires covered recovery and 120-1800 seconds')
    if a.app and not a.development:
        p.error('An app without authenticated package metadata requires --development')
    if a.model_only and (not a.development or a.remote_arming or a.covered_recovery or a.faults):
        p.error('Model-only is a development diagnostic without protected setup or faults')
    if a.covered_probe and (not a.development or not a.covered_recovery or a.covered_renewal_seconds not in {0,120}):
        p.error('Covered probe is development-only, with optional bounded expiry and 120-second renewal')
    if a.package_directory and not a.team_id:
        p.error('Package verification requires --team-id')
    if not (1 <= a.repeat <= 300 and 0 <= a.soak_seconds <= 1800 and -(2**63) <= a.seed < 2**63):
        p.error('Invalid bounded repeat/soak settings')
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    mc = [str(repo / 'bin/machine-control')]
    report = FailureReport(a.output, bool(os.environ.get('MACHINE_CONTROL_WORKSPACE_HANDLE')))
    try:
        run_controller(a, repo, mc, report)
    except BaseException as error:
        report.failed(error)
        report.publish(None if a.defer_failure_note else mc)
        raise


def run_controller(a, repo, mc, report):
    if a.remote_arming:
        scope = json.loads(Path(os.environ['MACHINE_CONTROL_SCOPE_FILE']).read_text())
        # Read-only inventory proves the parent's exact receipt is disposable;
        # it neither acquires/releases a resource nor changes child selection.
        inventory_env = {k: v for k, v in os.environ.items() if k not in {'MACHINE_CONTROL_SCOPE_FILE', 'MACHINE_CONTROL_WORKSPACE_HANDLE'}}
        inventory = json.loads(subprocess.check_output(mc + ['--registry', scope['registry'],
            '--target', scope['target'], 'workspace', 'inventory'], env=inventory_env, timeout=45))
        matches = [item for item in inventory['data']['workspaces'] if item['handle'] == scope['workspace']]
        assert len(matches) == 1 and matches[0]['intent'] == 'isolated' and matches[0]['retention'] == 'discardOnRelease', 'A discard-on-release isolated receipt is required'

    def call(*args, **kwargs):
        return subprocess.check_output(mc + list(args), timeout=240, **kwargs)

    def interrupted(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    remote = '/tmp/mc-packaged-' + uuid.uuid4().hex
    report.step('controller_preflight', 'observe_initial_power')
    # Doctor returns nonzero for a parked guest while still returning its
    # read-only power/identity report. Claim resolution has already succeeded.
    doctor = subprocess.run(mc + ['target', 'doctor'], capture_output=True, timeout=90)
    initial = json.loads(doctor.stdout)['states']['power']
    staged = False
    with tempfile.TemporaryDirectory(prefix='mc-acceptance-extract-') as temporary:
        report.step('controller_preflight', 'verify_candidate')
        announce('controller_package', 'verify_candidate')
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
        report.step('controller_preflight', 'archive_candidate')
        announce('controller_package', 'stage_payload')
        archive_path = a.output / 'staged-inputs.tar'
        with tarfile.open(archive_path, 'w') as archive:
            archive.add(app, arcname='candidate/Machine Control.app')
            for name in ['tests/macos/packaged-acceptance-guest.py', 'tests/macos/acceptance_diagnostics.py',
                         'tests/macos/acceptance_display.py',
                         'tests/macos/browser-file-dialogs.py', 'tests/macos/remote-arming.py',
                         'tests/macos/browser_dialog_probe.py',
                         'tests/macos/surface_fixture.py', 'tests/macos/surface-policy-live.py', 'tests/macos/surface-covered-live.py',
                         'tests/macos/covered-recovery.py', 'tests/macos/cover-observation.swift', 'tests/macos/kernel-pointer-fixture.m',
                         'tests/macos/guardian-startup-watch.m', 'tests/macos/session-lock.m',
                         'platforms/macos/guests/macos/fixture/MachineControlFixture.swift', 'platforms/macos/guests/macos/unlock/Session.h',
                         'platforms/macos/guests/macos/unlock/Relock.h', 'platforms/chromeos/cdp.py']:
                archive.add(repo / name, arcname='source/' + name)
            archive.add(repo / 'platforms/macos/resident/scripts/install-user.sh', arcname='install-user.sh')
            if a.source_sdk:
                for file in sorted((repo/'client').glob('*.py')):
                    archive.add(file,arcname='source/client/'+file.name)
        try:
            report.step('controller_setup', 'start_guest')
            call('target', 'up')
            report.step('controller_setup', 'verify_guest_readiness')
            assert json.loads(call('target', 'doctor'))['ready'], 'Guest doctor is not ready'
            report.step('controller_setup', 'stage_candidate')
            call('testbed', '--', 'exec', '/bin/mkdir', '-m', '700', remote)
            staged = True
            report.cleanup['stage'] = 'retained'
            with archive_path.open('rb') as stream:
                call('testbed', '--', 'exec', '-i', '/usr/bin/tar', '-xf', '-', '-C', remote, stdin=stream)
            argv = ['os', '--', '/usr/bin/python3', remote + '/source/tests/macos/packaged-acceptance-guest.py',
                    '--stage', remote, '--claim', os.environ['MACHINE_CONTROL_CLAIM_ID'],
                    '--repeat', str(a.repeat), '--seed', str(a.seed), '--soak-seconds', str(a.soak_seconds)]
            if a.faults:
                argv += ['--faults']
            if a.model_only:
                argv += ['--model-only']
            if a.dialog_probe:
                argv += ['--dialog-probe']
            if a.source_sdk:
                argv += ['--source-sdk']
            if a.covered_probe:
                argv += ['--covered-probe']
            if a.remote_arming:
                argv += ['--remote-arming', '--disposable-workspace']
            if a.covered_recovery:
                argv += ['--covered-recovery', '--covered-duration', str(a.covered_duration),
                         '--covered-renewal-seconds', str(a.covered_renewal_seconds)]
            # The guest exposes only a validated one-shot lease. No password
            # enters request JSON, argv, environment, evidence or ordinary logs.
            attempted = False
            frames = set()
            report.step('guest_setup', 'verify_observer')
            proc = subprocess.Popen(mc + argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                for line in proc.stdout:
                    report.observe(line)
                    if line.startswith(MARKER):
                        if not a.covered_recovery:
                            raise ValueError('Unexpected acceptance frame request')
                        deliver_frame(line, Path(remote), lambda: call('testbed', '--', 'acceptance-display-frame'),
                                      lambda frame, contents: stage_frame(call, frame, contents), frames)
                    elif line.startswith(b'MC_CREDENTIAL_LEASE '):
                        report.step('guest_campaign', 'authorize_native_sheet')
                        assert a.covered_recovery and not attempted, 'Unexpected or repeated credential request'
                        lease = json.loads(line[len(b'MC_CREDENTIAL_LEASE '):])
                        assert set(lease) == {'leaseId'} and isinstance(lease['leaseId'], str)
                        assert re.fullmatch(r'[0-9a-fA-F-]{36}:auth:[0-9a-fA-F-]{36}', lease['leaseId'])
                        marker = Path(tempfile.gettempdir()) / ('mc-acceptance-auth-' + str(os.getuid()) + '-' + scope['workspace'])
                        marker_fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                        os.close(marker_fd)
                        fd = os.open(a.admin_secret_file, os.O_RDONLY | os.O_NOFOLLOW)
                        with os.fdopen(fd, 'rb') as secret:
                            info = os.fstat(secret.fileno())
                            assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
                            assert info.st_uid == os.getuid() and info.st_nlink == 1 and 0 < info.st_size <= 4096
                            attempted = True
                            response = json.loads(call('testbed', '--', 'exec', '-i',
                                remote + '/backup/Original.app/Contents/MacOS/macui', 'credential',
                                remote + '/observer/control.sock', lease['leaseId'], stdin=secret))
                        assert response.get('accepted') and response.get('effect') == 'confirmed', 'Credential effect uncertain; no retry'
                        print('Native System Settings credential sheet dismissed through the one-shot transport', flush=True)
                    else:
                        sys.stdout.buffer.write(line); sys.stdout.flush()
                assert proc.wait(timeout=10) == 0, 'Packaged guest campaign failed'
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT); proc.wait(timeout=45)
            report.step('controller_postflight', 'read_guest_summary')
            summary = json.loads(call('os', '--', '/bin/cat', remote + '/results/summary.json'))
        except BaseException as error:
            report.failed(error)
            raise
        finally:
            announce('controller_package', 'restore_guest')
            try:
                if staged:
                    report.step('controller_cleanup', 'collect_guest_evidence')
                    report.cleanup.update(guestEvidence='failed', appState='unknown')
                    with (a.output / 'guest-evidence.tar').open('wb') as stream:
                        archive_result = subprocess.run(mc + ['os', '--', '/usr/bin/tar', '-cf', '-', '-C', remote, 'results'],
                                                        stdout=stream, check=False, timeout=90)
                    if archive_result.returncode == 0:
                        report.cleanup['guestEvidence'] = 'collected'
                    report.step('controller_cleanup', 'read_app_restoration')
                    cleanup = json.loads(call('os', '--', '/bin/cat', remote + '/results/cleanup.json'))
                    (a.output / 'cleanup.json').write_text(json.dumps(cleanup) + '\n')
                    report.cleanup['appState'] = 'restored' if cleanup.get('appStateRestored') is True else 'failed'
                    if cleanup['restored'] or (a.remote_arming and cleanup.get('appStateRestored')
                            and cleanup.get('workspaceDiscardRequired') and os.environ.get('MACHINE_CONTROL_WORKSPACE_HANDLE')):
                        report.step('controller_cleanup', 'remove_guest_stage')
                        call('os', '--', '/bin/rm', '-rf', remote)
                        report.cleanup['stage'] = 'removed'
                    else:
                        raise RuntimeError('Guest restoration incomplete; private backups retained at ' + remote)
            except BaseException as error:
                report.failed(error)
                raise
            finally:
                if initial in {'suspended', 'off'}:
                    report.step('controller_cleanup', 'restore_power')
                    report.cleanup['power'] = 'failed'
                    call('target', 'suspend' if initial == 'suspended' else 'shutdown')
                    observed_power = json.loads(call('target', 'status'))['data']['powerState']
                    assert observed_power == initial, 'Initial guest power was not observed after cleanup'
                    report.cleanup['power'] = 'restored'
        report.step('controller_postflight', 'write_identity')
        # Development output is deliberately ineligible as release evidence.
        (a.output / 'identity.json').write_text(json.dumps({'development': a.development,
            'build': manifest, 'seed': a.seed, 'sdkOrigin':'source' if a.source_sdk else 'packaged'}) + '\n')
        receipt_path = None
        if not a.development and manifest and a.faults and a.repeat >= 3 and a.soak_seconds >= 120:
            report.step('controller_postflight', 'verify_acceptance_receipt')
            assert summary['faults']
            assert summary['plannedRestarts'] == (5 if a.covered_recovery else 1)
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
            if a.covered_recovery:
                receipt.update(schema='machine-control-packaged-acceptance/v1', reliability=summary['reliability'],
                    coverage=sorted((acceptance.COVERAGE | acceptance.RELIABILITY_COVERAGE) - acceptance.REBOOT_COVERAGE))
                assert cleanup['appStateRestored'] and cleanup['workspaceDiscardRequired']
                # The enclosing common run still owns this workspace. Only the
                # outer reliability runner can attest its completed disposal.
                # This object also lacks the independent visible-controls and
                # cold-boot evidence. It is deliberately not a release receipt.
                receipt_path = a.output / 'acceptance-pending-cleanup.json'
            elif not a.remote_arming:
                acceptance.validate(receipt, manifest, revision=revision, version=manifest['version'], run=run)
                receipt_path = a.output / 'acceptance.json'
        report.step('controller_postflight', 'write_usage_summary')
        subprocess.run(mc + ['usage', 'note', '--kind', 'summary', '--goal', 'Packaged desktop acceptance'],
            input=('Packaged suite passed ' + str(summary['checks']) + ' checks with seed ' + str(a.seed) +
                   '. App, policy and operator files restored. ' +
                   ('Helper registration awaits enclosing workspace disposal. ' if a.remote_arming else '') +
                   'Raw evidence remains controller-private.\n').encode(),
            stdout=subprocess.DEVNULL, check=True, timeout=30)
        if receipt_path is not None:
            report.step('controller_postflight', 'write_acceptance_receipt')
            receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        print('Packaged acceptance passed; ' + ('helper registration confined to disposable workspace' if a.remote_arming
            else 'original guest state and power restored'), flush=True)


if __name__ == '__main__':
    main()

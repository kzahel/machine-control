#!/usr/bin/env python3
"""Run the signed desktop release smoke in one disposable Mac workspace."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import traceback

from acceptance_diagnostics import FailureReport, Timings


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def exact_revision():
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('Release smoke requires a clean candidate checkout')
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--candidate-run', help='Download the ARM64 package from this successful unified CI candidate')
    source.add_argument('--package-directory', type=Path, help='Use an already downloaded signed candidate')
    parser.add_argument('--development', action='store_true', help='Rehearse with an earlier signed candidate')
    for name in ('target', 'team-id', 'provision-run', 'claimant-authority', 'claimant-id'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--admin-secret-file', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if os.environ.get('MACHINE_CONTROL_SCOPE_FILE') or args.output.resolve().is_relative_to(ROOT):
        parser.error('Run outside an existing scope with an output directory outside the checkout')
    if args.candidate_run and (not args.candidate_run.isascii() or not args.candidate_run.isdecimal()
                               or args.candidate_run.startswith('0')):
        parser.error('Expected a numeric candidate run ID')

    output = args.output.resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    acceptance = load('acceptance', ROOT / 'desktop/scripts/packaged-acceptance.py')
    reliability = load('reliability', Path(__file__).with_name('reliability-acceptance.py'))
    report = FailureReport(output, workspace_owned=True)
    report.cleanup = {'claim': 'not_acquired', 'workspace': 'not_acquired'}
    timings = Timings(initial_step='controller/resolve_candidate')
    passed = False

    def step(check):
        report.step('smoke_controller', check)
        timings.step('controller/' + check)

    def inspect_cleanup(events, _error):
        if (len(events) == 1 and events[0].get('event') == 'finished'
                and events[0].get('cleanup') == report.cleanup):
            return
        try:
            report.cleanup.update(reliability.scope_completion(events)['cleanup'])
        except ValueError:
            report.cleanup.update(claim='unknown', workspace='unknown')

    mc = [str(ROOT / 'bin/machine-control'), '--provision-run', args.provision_run, '--target', args.target]
    try:
        step('resolve_candidate')
        revision = None if args.development else exact_revision()
        package = args.package_directory
        candidate_id = args.candidate_run
        if candidate_id:
            step('download_candidate')
            package = output / 'candidate'
            subprocess.run(['gh', 'run', 'download', candidate_id, '--repo', 'kzahel/machine-control',
                            '-n', 'macos-desktop-aarch64-apple-darwin', '-D', str(package)],
                           check=True, timeout=240)
        build = json.loads((package / 'build.json').read_text())
        if not args.development and not acceptance.supports_standard_timing(build['version']):
            raise ValueError('Release smoke qualification starts with desktop 0.7.7')
        revision = revision or build['sourceRevision']
        if candidate_id or not args.development:
            candidate_id = candidate_id or str(build['workflowRun'])
            run_file = output / 'candidate-run.json'
            step('verify_candidate_run')
            with run_file.open('wb') as stream:
                subprocess.run(['gh', 'api', f'repos/kzahel/machine-control/actions/runs/{candidate_id}'],
                               stdout=stream, check=True, timeout=60)
            approved_run = subprocess.check_output(
                [sys.executable, str(ROOT / 'desktop/scripts/release.py'), 'check-run', str(run_file),
                 '--revision', revision, '--id', candidate_id], text=True, timeout=20).strip()
            if f"{build['workflowRun']}.{build['workflowAttempt']}" != approved_run:
                raise ValueError('Downloaded package does not match the successful unified candidate attempt')
        step('verify_package')
        subprocess.run([sys.executable, str(ROOT / 'desktop/scripts/verify-package.py'), str(package),
                        '--revision', revision, '--team-id', args.team_id], check=True, timeout=90)
        archives = [item for item in build['artifacts'] if item['name'].endswith('.app.tar.gz')]
        if len(archives) != 1 or archives[0]['name'] != f"MachineControl_{build['version']}_arm64.app.tar.gz":
            raise ValueError('Expected one Apple silicon candidate archive')

        step('workspace')
        with tempfile.TemporaryDirectory(prefix='mc-release-smoke-') as directory:
            with tarfile.open(package / archives[0]['name']) as archive:
                archive.extractall(directory, filter='data')
            reliability.run_claimed(
                mc + ['run', '--intent', 'isolated', '--duration', '15m',
                      '--reason', 'Smoke test the signed desktop candidate',
                      '--claimant-authority', args.claimant_authority, '--claimant-id', args.claimant_id,
                      '--', sys.executable, str(Path(__file__).with_name('reboot-choices.py')),
                      '--smoke', '--app', str(Path(directory) / 'Machine Control.app'),
                      '--admin-secret-file', str(args.admin_secret_file), '--output', str(output / 'guest')],
                output / 'workspace.log', diagnose_failure=inspect_cleanup, observe=report.observe, timeout=720)
        report.cleanup.update(claim='released', workspace='released')
        step('verify_result')
        protected = json.loads((output / 'guest/protected-stop.json').read_text())
        if protected.get('passed') is not True or protected.get('protectedFixtureEffects') != 1:
            raise ValueError('Expected exactly one confirmed protected fixture effect')
        if not args.development:
            if exact_revision() != revision:
                raise ValueError('Candidate checkout changed during smoke')
            run = f"{build['workflowRun']}.{build['workflowAttempt']}"
            receipt = {'schema': acceptance.SMOKE_SCHEMA, 'sourceRevision': revision,
                       'version': build['version'], 'candidateRun': run,
                       'archiveSHA256': archives[0]['sha256'], 'coverage': sorted(acceptance.SMOKE_COVERAGE),
                       'cleanupVerified': True, 'passed': True}
            acceptance.validate(receipt, build, revision=revision, version=build['version'], run=run)
            (output / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
        passed = True
        print('GO: exact signed candidate smoke passed' if not args.development else 'Development smoke passed', flush=True)
    except BaseException as error:
        report.failed(error)
        (output / 'controller-error.log').write_text(traceback.format_exc())
        report.publish(mc)
        print(f"STOP: {report.phase}/{report.check}. See failure.json and available logs.", file=sys.stderr)
        raise SystemExit(1) from error
    finally:
        timings.finish(output / 'controller.timings.json', passed)
        (output / 'result.json').write_text(json.dumps({
            'passed': passed, 'releaseEligible': passed and not args.development,
            'failure': report.failure, 'cleanup': report.cleanup}, indent=2) + '\n')


if __name__ == '__main__':
    main()

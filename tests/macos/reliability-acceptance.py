#!/usr/bin/env python3
"""Claim, run packaged reliability acceptance, and verify disposable cleanup.

This is a controller entry point, outside an existing claim scope. It never
uses the controller's desktop. Raw evidence and run receipts stay private.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def finished_scope(events):
    acquired = [e for e in events if e.get('schema') == 'machine-control-run/v0' and e.get('event') == 'acquired']
    finished = [e for e in events if e.get('schema') == 'machine-control-run/v0' and e.get('event') == 'finished']
    if len(acquired) != 1 or len(finished) != 1:
        raise ValueError('One exact acquired and completed isolated scope is required')
    start, end = acquired[0], finished[0]
    if (not start.get('claimId') or not start.get('workspaceHandle')
            or any(start.get(k) != end.get(k) for k in ['claimId', 'workspaceHandle', 'logicalTarget'])
            or end.get('exitCode') != 0 or end.get('childExitCode') != 0
            or end.get('outcome') != 'completed'
            or end.get('cleanup') != {'claim': 'released', 'workspace': 'released'}):
        raise ValueError('Isolated acceptance scope or disposal did not complete successfully')


def run_claimed(args, path):
    events = []
    with path.open('wb') as log:
        proc = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:
            for line in proc.stdout:
                log.write(line); log.flush()
                sys.stdout.buffer.write(line); sys.stdout.flush()
                try:
                    value = json.loads(line)
                    if isinstance(value,dict) and value.get('schema') == 'machine-control-run/v0':
                        events.append(value)
                except (UnicodeError,ValueError):
                    pass
            if proc.wait() != 0:
                raise RuntimeError('Reliability campaign failed; inspect private evidence')
        except KeyboardInterrupt:
            proc.terminate()
            rest,_ = proc.communicate(timeout=90)
            log.write(rest or b''); log.flush()
            raise
        finally:
            if proc.poll() is None:
                proc.terminate(); proc.wait(timeout=90)
    finished_scope(events)


def completed_development_campaign(root):
    """Reuse only a completed development phase; never mint release evidence."""
    campaign = root / 'campaign'
    if json.loads((campaign/'identity.json').read_text()).get('development') is not True:
        raise ValueError('Only a development campaign can be resumed')
    events = []
    for line in (root/'campaign.log').read_text().splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value,dict) and value.get('schema') == 'machine-control-run/v0':
            events.append(value)
    finished_scope(events)
    with tarfile.open(campaign/'guest-evidence.tar') as archive:
        summary = json.load(archive.extractfile('results/summary.json'))
    reliability = summary.get('reliability',{})
    if (not isinstance(reliability,dict) or summary.get('passed') is not True or summary.get('faults') is not True
            or summary.get('remoteArming') is not True or summary.get('plannedRestarts') != 5
            or type(summary.get('checks')) is not int or summary['checks'] < 20
            or type(summary.get('repeat')) is not int or summary['repeat'] < 3
            or reliability.get('coveredDurationSeconds') != 900
            or type(reliability.get('renewableOwnerSeconds')) is not int
            or not 960 <= reliability['renewableOwnerSeconds'] <= 1800):
        raise ValueError('Saved development campaign lacks complete reliability execution')
    return campaign


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', required=True)
    p.add_argument('--claimant-authority', required=True)
    p.add_argument('--claimant-id', required=True)
    p.add_argument('--provision-run', required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--package-directory', type=Path)
    source.add_argument('--app', type=Path)
    source.add_argument('--resume-campaign', type=Path,
        help='Development only: reuse a completed controller campaign and repeat its cold-boot phase')
    p.add_argument('--development', action='store_true')
    p.add_argument('--team-id')
    p.add_argument('--admin-secret-file', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--seed', type=int, default=141)
    a = p.parse_args()
    if (a.app or a.resume_campaign) and not a.development:
        p.error('Local app bundles and campaign recovery require --development')
    if a.package_directory and not a.team_id:
        p.error('Authenticated candidate packages require --team-id')
    if os.environ.get('MACHINE_CONTROL_SCOPE_FILE'):
        p.error('Run this controller wrapper outside an existing claim scope')
    repo = Path(__file__).resolve().parents[2]
    if a.output.resolve().is_relative_to(repo):
        p.error('Evidence must be outside the public checkout')
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    args = [str(repo / 'bin/machine-control'), '--provision-run', a.provision_run,
        '--target', a.target, 'run', '--intent', 'isolated', '--duration', '60m',
        '--reason', 'Qualify exact packaged desktop reliability with disposable cleanup',
        '--claimant-authority', a.claimant_authority, '--claimant-id', a.claimant_id, '--',
        sys.executable, str(repo / 'tests/macos/packaged-acceptance.py'),
        '--output', str(a.output / 'campaign'), '--repeat', '3', '--soak-seconds', '120',
        '--seed', str(a.seed), '--faults', '--remote-arming', '--covered-recovery',
        '--covered-duration', '900', '--covered-renewal-seconds', '960',
        '--admin-secret-file', str(a.admin_secret_file)]
    if a.resume_campaign:
        if a.resume_campaign.resolve().is_relative_to(repo):
            p.error('Saved campaign evidence must be outside the public checkout')
        campaign = completed_development_campaign(a.resume_campaign)
        (a.output/'resumed-campaign.json').write_text(json.dumps({'directory':str(a.resume_campaign.resolve())}))
    else:
        campaign = a.output/'campaign'
        args += ['--app', str(a.app)] if a.app else ['--package-directory', str(a.package_directory)]
        if a.development:
            args += ['--development']
        if a.team_id:
            args += ['--team-id', a.team_id]
        run_claimed(args,a.output/'campaign.log')
    # A fresh, sequential workspace keeps visible Stop/relaunch and boot checks
    # separate from the protected campaign's intentionally locked final state.
    mc = [str(repo/'bin/machine-control')]
    journal = json.loads(subprocess.check_output(mc+['provision','begin','--platform','macos',
        '--profile','development' if a.development else 'runtime']))['runId']
    (a.output/'reboot-provision-run.json').write_text(json.dumps({'runId':journal}))
    outcome = 'failed'
    try:
        with tempfile.TemporaryDirectory(prefix='mc-reliability-reboot-') as extracted:
            with tarfile.open(campaign/'staged-inputs.tar') as archive:
                archive.extractall(extracted,filter='data')
            app = Path(extracted)/'candidate/Machine Control.app'
            subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
            run_claimed(mc+['--provision-run',journal,'--target',a.target,'run','--intent','isolated',
                '--duration','30m','--reason','Verify exact candidate saved choices and boot-bound consent',
                '--claimant-authority',a.claimant_authority,'--claimant-id',a.claimant_id,'--',
                sys.executable,str(repo/'tests/macos/reboot-choices.py'),'--app',str(app),
                '--admin-secret-file',str(a.admin_secret_file),'--output',str(a.output/'reboot')],
                a.output/'reboot.log')
        boot = json.loads((a.output/'reboot/reboot-choices.json').read_text())
        assert boot['actualReboot'] is True and boot['authorizationRestored'] is False
        assert boot['stopCleanRelaunch'] is True and boot['rememberedScopes'] == 4 and boot['rememberedDuration'] == 0
        assert boot['browserWhileLockedRemembered'] is True
        outcome = 'ready'
    finally:
        try:
            subprocess.run(mc+['provision','note',journal,'--kind','summary'],
                input=('Exact-candidate visible Stop/relaunch and cold-boot phase: '+outcome+
                    '. Direct guest fixture details and scope cleanup are in '+str(a.output/'reboot.log')+
                    '; raw evidence remains private. No complete acceptance on failure.\n'),text=True,check=True)
        finally:
            subprocess.run(mc+['provision','finish',journal,'--outcome',outcome],check=True)
    if not a.development:
        receipt = json.loads((campaign / 'acceptance-pending-cleanup.json').read_text())
        assert receipt['cleanupVerified'] is False
        receipt['cleanupVerified'] = True
        spec = importlib.util.spec_from_file_location('acceptance', repo / 'desktop/scripts/packaged-acceptance.py')
        acceptance = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(acceptance)
        receipt['reliability'].update(stopRelaunchUI=True,coldBootChoices=True)
        receipt['coverage'] = sorted(acceptance.COVERAGE | acceptance.RELIABILITY_COVERAGE)
        revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo),'Acceptance source changed during execution'
        acceptance.validate(receipt, json.loads((a.package_directory / 'build.json').read_text()),
            revision=revision, version=receipt['version'], run=receipt['candidateRun'])
        (a.output / 'acceptance.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('Reliability campaign and exclusive workspace disposal verified', flush=True)


if __name__ == '__main__':
    main()

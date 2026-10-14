#!/usr/bin/env python3
"""Run a serial, source-pinned matrix with a review gate after the first round.

The selected checkout supplies every guest fixture and client. This driver can
live in a newer checkout while candidate work proceeds independently. All
receipts and operator control files are private and outside the source tree.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import random
import signal
import stat
import subprocess
import sys
import time
from types import SimpleNamespace

ROUTES = {'codex': ['computer-use', 'machine-control', 'mc-repl'],
          'claude': ['machine-control', 'mc-repl']}
MATRICES = {'baseline': ROUTES, 'python': {'codex': ['mc-python'], 'claude': ['mc-python']}}


def plan_rounds(tasks, repetitions, seed, routes=None):
    routes = ROUTES if routes is None else routes
    generator = random.Random(seed)
    rounds = []
    for repetition in range(1, repetitions + 1):
        rows = [{'provider': provider, 'task': task, 'route': route, 'repetition': repetition}
                for provider, provider_routes in routes.items() for task in tasks for route in provider_routes]
        generator.shuffle(rows)
        rounds.append(rows)
    return rounds


def private_secret(path):
    mode = path.lstat()
    if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600 or not path.read_bytes():
        raise ValueError('Credential must be a nonempty regular mode-0600 file')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_key(row):
    return tuple(row[k] for k in ('provider','task','route','repetition'))


def snapshot_attempt(path):
    record=json.loads((path/'trial.json').read_text())
    hashes={name:digest(path/name) for name in ('trial.json','transcript.jsonl','evaluation.json','review.json')
            if (path/name).is_file()}
    if 'evaluation.json' in hashes:
        evaluation=json.loads((path/'evaluation.json').read_text())
        if (evaluation.get('schema')!='route-comparison-evaluation/v1' or
                evaluation.get('receiptSha256')!=hashes['trial.json'] or
                evaluation.get('transcriptSha256')!=hashes.get('transcript.jsonl')):
            raise ValueError('Prior evaluation evidence changed')
        record=evaluation['record']
    if 'review.json' in hashes:
        review=json.loads((path/'review.json').read_text())
        if review.get('transcriptSha256')!=hashes.get('transcript.jsonl'):
            raise ValueError('Prior route review evidence changed')
        record={**record,'routeReview':review}
    return {'directory':str(path.resolve()),'hashes':hashes,'record':record}


def reusable(attempts):
    completed=set()
    for attempt in attempts:
        record=attempt['record']
        if record.get('releaseError') or record.get('released')!='discarded':
            raise ValueError('Prior workspace disposal unresolved')
        if record.get('validTrial') is True and not record.get('error'):
            key=row_key(record)
            if key in completed:
                raise ValueError('Duplicate qualified prior trial')
            completed.add(key)  # Product failures count; never retry to improve a score.
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clean detached baseline checkout')
    parser.add_argument('--target', required=True)
    parser.add_argument('--credential-file', type=Path, required=True)
    parser.add_argument('--gateway-credential-file', type=Path, required=True)
    parser.add_argument('--results', type=Path, default=Path.home()/'.local/state/machine-control/experiments')
    parser.add_argument('--seed', type=int, default=125)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--matrix', choices=sorted(MATRICES), default='baseline')
    parser.add_argument('--pause-after-smoke', action='store_true')
    parser.add_argument('--start-paused', action='store_true', help='Prepare the manifest and wait for removal of its private pause file')
    parser.add_argument('--resume-from',type=Path,help='Continue a stopped campaign in a new immutable result directory')
    parser.add_argument('--allow-evaluator-change',action='append',default=[],
                        help='Explicit reviewed path changed between source pins; never allow client or prompt changes')
    parser.add_argument('--ssh-key', type=Path, default=Path.home()/'.ssh/mc-experiments_ed25519')
    parser.add_argument('--known-hosts', type=Path, default=Path.home()/'.ssh/mc-experiments_known_hosts')
    parser.add_argument('--host-key-alias', default='mc-experiment-base')
    parser.add_argument('--guest-user', default='admin')
    parser.add_argument('--project', default='/Users/admin/code/machine-control')
    options = parser.parse_args()
    if options.repetitions < 1:
        parser.error('repetitions must be positive')
    os.umask(0o077)
    private_secret(options.credential_file)
    private_secret(options.gateway_credential_file)
    source = options.source.resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip():
        parser.error('baseline source must be clean')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    sys.path.insert(0, str(source/'tests/experiments'))
    harness = importlib.import_module('route_comparison')
    if harness.ROOT != source:
        raise RuntimeError('Loaded a different harness checkout')
    tasks = {path.name: json.loads((path/'task.json').read_text())
             for path in harness.TASKS.iterdir() if path.is_dir()}
    routes = MATRICES[options.matrix]
    if any(route not in harness.ROUTES for values in routes.values() for route in values):
        parser.error('selected source does not implement every requested matrix route')
    rounds = plan_rounds(sorted(tasks), options.repetitions, options.seed, routes)
    carried={provider:[] for provider in routes}
    continuation=None
    completed=set()
    if options.resume_from:
        prior=options.resume_from.resolve()
        prior_state=json.loads((prior/'state.json').read_text())
        prior_manifest=json.loads((prior/'campaign.json').read_text())
        if prior_state['state'] not in ('failed','stopped_between_trials','complete'):
            parser.error('prior campaign must have stopped and finished cleanup')
        if prior_manifest['rounds']!=rounds or prior_manifest.get('matrix','baseline')!=options.matrix:
            parser.error('prior matrix, ordering, seed or repetition plan differs')
        old_revision=prior_manifest.get('sourceRevision',prior_manifest.get('baselineRevision'))
        changed=subprocess.check_output(['git','diff','--name-only',old_revision,revision],cwd=source,text=True).splitlines()
        if set(changed)-set(options.allow_evaluator_change):
            parser.error('source changed outside explicitly reviewed evaluator paths')
        for provider in routes:
            manifest=json.loads((prior/provider/'manifest.json').read_text())
            if any(manifest.get(k)!=v for k,v in {'provider':provider,'model':harness.DEFAULT_MODELS[provider],
                    'effort':'medium','speed':'standard','instructionProfile':'current','seed':options.seed}.items()):
                parser.error('prior provider profile differs')
            carried[provider]=manifest.get('carriedAttempts',[])
            for attempt in carried[provider]:
                if any(digest(Path(attempt['directory'])/name)!=value for name,value in attempt['hashes'].items()):
                    parser.error('carried evidence changed')
            carried[provider]+= [snapshot_attempt(p.parent) for p in sorted((prior/provider).glob('*/*/trial.json'))]
        completed=reusable([a for values in carried.values() for a in values])
        if not completed<={row_key(row) for rows in rounds for row in rows}:
            parser.error('unexpected prior cells')
        continuation={'campaign':str(prior),'campaignSha256':digest(prior/'campaign.json'),
                      'sourceRevision':old_revision,'reviewedEvaluatorChanges':changed}
    campaign = options.results / ('campaign-' + harness.now())
    campaign.mkdir(mode=0o700, parents=True)
    if options.start_paused:
        (campaign/'pause').touch(mode=0o600)
    state = {'state': 'prepared', 'completed': len(completed), 'newAttempts':0,
             'carriedAttempts':sum(map(len,carried.values())), 'planned': sum(map(len, rounds)),
             'matrix': options.matrix,
             'sourceRevision': revision, 'driverSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (campaign/'campaign.json').write_text(json.dumps({**state,'continuation':continuation,'rounds': rounds}, indent=2)+'\n')
    batches, summaries = {}, {}
    for provider in routes:
        directory = campaign/provider
        directory.mkdir()
        if options.resume_from:
            reference=options.resume_from/provider/'runtime-reference.json'
            if reference.is_file():
                # Compare the very first resumed guest with the prior runtime,
                # not just later guests with a newly accepted reference.
                (directory/'runtime-reference.json').write_bytes(reference.read_bytes())
        bundle = directory/'source.bundle'
        subprocess.run(['git', 'bundle', 'create', str(bundle), 'HEAD'], cwd=source, check=True)
        args = SimpleNamespace(**vars(options), provider=provider, model=harness.DEFAULT_MODELS[provider],
            effort='medium', instructions='current', poll_seconds=1.0, revision=revision, bundle=bundle)
        manifest = {'schema': 'route-comparison-batch/v1', 'revision': revision, 'provider': provider,
            'model': args.model, 'effort': args.effort, 'speed': 'standard', 'instructionProfile': 'current',
            'seed': options.seed, 'pollSeconds': 1.0, 'driverSha256': state['driverSha256'],
            'continuation':continuation,'carriedAttempts':carried[provider],
            'plan': [{k: row[k] for k in ('task', 'route', 'repetition')}
                     for rows in rounds for row in rows if row['provider'] == provider],
            'fixtureHashes': {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in harness.TASKS.rglob('*') if p.is_file()}}
        (directory/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
        batches[provider] = (args, directory)
        summaries[provider] = []
    stopping = False
    def stop(signum, frame):
        nonlocal stopping
        stopping = True  # Finish this trial's finally-style cleanup first.
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    def status(name, **extra):
        state.update(state=name, **extra)
        temporary = campaign/'state.tmp'
        temporary.write_text(json.dumps(state, indent=2)+'\n')
        temporary.replace(campaign/'state.json')
    print(f'Campaign {campaign}: {state["planned"]} trials', flush=True)
    try:
        for round_index, rows in enumerate(rounds):
            if round_index == 1 and options.pause_after_smoke:
                status('awaiting_smoke_review')
                while not (campaign/'continue').exists() and not stopping and not (campaign/'stop').exists():
                    time.sleep(1)
            for row in rows:
                if row_key(row) in completed:
                    continue
                while (campaign/'pause').exists() and not stopping and not (campaign/'stop').exists():
                    status('paused_between_trials')
                    time.sleep(1)
                if stopping or (campaign/'stop').exists():
                    status('stopped_between_trials')
                    return 1
                status('running', current=row)
                args, directory = batches[row['provider']]
                receipt = harness.run_trial(args, tasks[row['task']], row['route'], row['repetition'], directory)
                summaries[row['provider']].append(receipt)
                (directory/'summary.json').write_text(json.dumps(summaries[row['provider']], indent=2)+'\n')
                state['newAttempts'] += 1
                print(json.dumps({**row, **{key: receipt.get(key) for key in
                    ('passed', 'validTrial', 'agentSeconds', 'toolCalls', 'error', 'releaseError')}}), flush=True)
                if receipt.get('error') or receipt.get('releaseError') or not receipt.get('released') \
                        or not receipt.get('validTrial'):
                    raise RuntimeError('Unqualified trial; inspect receipt before scheduling more work')
                state['completed'] += 1
        status('complete', current=None)
        return 0
    except BaseException as error:
        status('failed', error=type(error).__name__ + ': ' + str(error))
        raise


if __name__ == '__main__':
    raise SystemExit(main())

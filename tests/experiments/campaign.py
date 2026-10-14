#!/usr/bin/env python3
"""Run a serial, source-pinned baseline with a review gate after the first round.

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


def plan_rounds(tasks, repetitions, seed):
    generator = random.Random(seed)
    rounds = []
    for repetition in range(1, repetitions + 1):
        rows = [{'provider': provider, 'task': task, 'route': route, 'repetition': repetition}
                for provider, routes in ROUTES.items() for task in tasks for route in routes]
        generator.shuffle(rows)
        rounds.append(rows)
    return rounds


def private_secret(path):
    mode = path.lstat()
    if not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600 or not path.read_bytes():
        raise ValueError('Credential must be a nonempty regular mode-0600 file')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Clean detached baseline checkout')
    parser.add_argument('--target', required=True)
    parser.add_argument('--credential-file', type=Path, required=True)
    parser.add_argument('--gateway-credential-file', type=Path, required=True)
    parser.add_argument('--results', type=Path, default=Path.home()/'.local/state/machine-control/experiments')
    parser.add_argument('--seed', type=int, default=125)
    parser.add_argument('--repetitions', type=int, default=3)
    parser.add_argument('--pause-after-smoke', action='store_true')
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
    rounds = plan_rounds(sorted(tasks), options.repetitions, options.seed)
    campaign = options.results / ('campaign-' + harness.now())
    campaign.mkdir(mode=0o700, parents=True)
    state = {'state': 'prepared', 'completed': 0, 'planned': sum(map(len, rounds)),
             'baselineRevision': revision, 'driverSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (campaign/'campaign.json').write_text(json.dumps({**state, 'rounds': rounds}, indent=2)+'\n')
    batches, summaries = {}, {}
    for provider in ROUTES:
        directory = campaign/provider
        directory.mkdir()
        bundle = directory/'source.bundle'
        subprocess.run(['git', 'bundle', 'create', str(bundle), 'HEAD'], cwd=source, check=True)
        args = SimpleNamespace(**vars(options), provider=provider, model=harness.DEFAULT_MODELS[provider],
            effort='medium', instructions='current', poll_seconds=1.0, revision=revision, bundle=bundle)
        manifest = {'schema': 'route-comparison-batch/v1', 'revision': revision, 'provider': provider,
            'model': args.model, 'effort': args.effort, 'speed': 'standard', 'instructionProfile': 'current',
            'seed': options.seed, 'pollSeconds': 1.0, 'driverSha256': state['driverSha256'],
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
                state['completed'] += 1
                print(json.dumps({**row, **{key: receipt.get(key) for key in
                    ('passed', 'validTrial', 'agentSeconds', 'toolCalls', 'error', 'releaseError')}}), flush=True)
                if receipt.get('error') or receipt.get('releaseError') or not receipt.get('released') \
                        or not receipt.get('validTrial'):
                    raise RuntimeError('Unqualified trial; inspect receipt before scheduling more work')
        status('complete', current=None)
        return 0
    except BaseException as error:
        status('failed', error=type(error).__name__ + ': ' + str(error))
        raise


if __name__ == '__main__':
    raise SystemExit(main())

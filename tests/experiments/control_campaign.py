#!/usr/bin/env python3
"""Private, source-pinned control acceptance campaign: plan, run, report.

Planning/reporting are offline. Only explicit `run` invokes route_comparison.
See instructions/control-campaign/protocol.md before an authorized live run.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import random
import signal
import time
import subprocess
import sys
from types import SimpleNamespace

ARMS = ('discovery', 'quickstart')
TASKS = ('load-unpacked-extension', 'textedit-menu', 'finder-decoy', 'browser-form')
HELD_OUT = {'finder-decoy', 'browser-form'}
STOP_REQUESTED = False
CHECKS = ('doctor', 'claim', 'workspace', 'oracle', 'disposal', 'credentialHandoff')
LIMITS = [
    'Pilot is a qualification stage, excluded from paired summaries.',
    'Route/package comparisons do not identify a programming-language effect.',
    'Token counts, including cache reads/writes, are usage, not dollars.',
    'Missing measurements are unknown; breakdowns overlap and must not be summed again.',
    'Successful-pair latency is conditional on both effects passing; failures remain in all-attempt usage.',
    'Lifecycle evidence is separate from UI score; review annotations are assertions, not authenticated authority.',
    'Held-out fixtures need live qualification; offline oracle tests cannot establish generalization.',
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def make_plan(revision, provider, model, effort, routes, seed, repetitions=3, include_current=False):
    if provider not in ('codex', 'claude') or not model or effort not in ('low', 'medium', 'high'):
        raise ValueError('Explicit supported provider, exact model and effort required')
    if not 2 <= repetitions <= 5:
        raise ValueError('Use two to five paired repetitions after the pilot')
    if (len(set(routes)) != len(routes) or not 1 <= len(routes) <= 2 or
            'machine-control' not in routes or
            set(routes) - {'machine-control', 'mc-python', 'mc-repl', 'computer-use'} or
            provider == 'claude' and 'computer-use' in routes):
        raise ValueError('Select CLI and at most one supported comparison route')
    rng = random.Random(seed)
    rows = []
    for repetition in range(1, repetitions + 2):
        block = []
        for task in TASKS:
            for route in routes:
                # Other runner routes ignore the CLI instruction selector.
                for arm in (ARMS + (('current',) if include_current else ())) if route == 'machine-control' else ('current',):
                    block.append({'task': task, 'route': route, 'arm': arm,
                                  'repetition': repetition,
                                  'stage': 'pilot' if repetition == 1 else 'paired',
                                  'taskRoot': 'control-scenarios' if task in HELD_OUT else 'tasks',
                                  'heldOut': task in HELD_OUT, 'trialSeed': seed + repetition - 1})
        rng.shuffle(block)
        rows.extend(block)
    for index, row in enumerate(rows):
        row['id'] = f'cell-{index + 1:04d}'
        row['fixtureSeed'] = hashlib.sha256(f"{row['trialSeed']}:{row['task']}:1".encode()).hexdigest()
    return {'schema': 'control-campaign/v1', 'revision': revision,
            'profile': {'provider': provider, 'model': model, 'effort': effort, 'speed': 'standard'},
            'seed': seed, 'routes': list(routes), 'repetitions': repetitions, 'includeCurrent': include_current, 'rows': rows, 'limits': LIMITS}


def validate_plan(plan):
    profile = plan['profile']
    rebuilt = make_plan(plan['revision'], profile['provider'], profile['model'], profile['effort'],
                        plan['routes'], plan['seed'], plan['repetitions'], plan['includeCurrent'])
    if any(plan.get(key) != value for key, value in rebuilt.items()):
        raise ValueError('Plan does not match the deterministic campaign contract')


def validate_record(plan, cell, record):
    expected = {'task': cell['task'], 'route': cell['route'], 'repetition': 1,
                'instructionProfile': cell['arm'], 'provider': plan['profile']['provider'],
                'requestedModel': plan['profile']['model'], 'requestedEffort': plan['profile']['effort'],
                'fixtureSeed': cell['fixtureSeed']}
    for key, value in expected.items():
        if (key in record or valid_trial(record)) and record.get(key) != value:
            raise ValueError('Receipt identity/profile/fixture does not match planned cell')


def valid_trial(record):
    return (record.get('validTrial') is True and not record.get('error') and not record.get('driverError') and
            record.get('profileQualification', {}).get('qualified') is True)


def clean(record):
    return (record.get('released') == 'discarded' and not record.get('releaseError') and
            not record.get('tunnelCleanupError'))


def ui_pass(record):
    review = record.get('routeReview') or {}
    return (valid_trial(record) and record.get('passed') is True and record.get('oracleExit') == 0 and
            (record.get('oracle') or {}).get('passed') is True and clean(record) and
            review.get('routeAdherence') == 'conforming' and
            review.get('confirmationPolicyAdherence') in ('conforming', 'not_applicable'))


def lifecycle(record, annotation=None):
    """Absent doctor/claim/workspace evidence must never become an implicit pass."""
    result = {key: 'unknown' for key in CHECKS}
    result['disposal'] = 'pass' if clean(record) else 'fail'
    if record.get('oracleExit') == 0 and isinstance(record.get('oracle', {}).get('passed'), bool):
        result['oracle'] = 'pass'  # Oracle execution, distinct from the UI outcome.
    if record.get('credentialVerification') == 'inherited_base_bytes_equal_mode_0600':
        result['credentialHandoff'] = 'pass'
    for key, evidence in (annotation or {}).items():
        if key not in CHECKS or evidence.get('status') not in ('pass', 'fail', 'unknown') or not evidence.get('evidence'):
            raise ValueError('Lifecycle annotations require known check, status and evidence')
        # Reviews can narrow an automatic result, never erase a known failure.
        if result[key] != 'fail':
            result[key] = evidence['status']
    return result


def summarize(plan, attempts):
    from measurements import token_metrics
    from report_batch import distribution
    validate_plan(plan)
    expected = {row['id']: row for row in plan['rows']}
    groups = collections.defaultdict(list)
    qualified = collections.Counter()
    lifecycle_passes = 0
    successes = {}
    for attempt in attempts:
        cell = expected.get(attempt['cell'])
        if cell is None:
            raise ValueError('Unexpected attempt cell')
        record = effective_record(attempt)
        validate_record(plan, cell, record)
        checks = lifecycle(record, attempt.get('lifecycle'))
        lifecycle_passes += all(value == 'pass' for value in checks.values())
        if valid_trial(record):
            qualified[cell['id']] += 1
        passed = ui_pass(record)
        if passed:
            successes[cell['id']] = record
        kind = ('success' if passed else 'invalid' if not valid_trial(record) else
                'unverified' if (record.get('oracle') or {}).get('passed') is True and clean(record) else 'failed')
        groups[(cell['stage'], cell['task'], cell['route'], cell['arm'])].append(
            (record, kind, checks))
    complete = set(qualified) == set(expected) and all(n == 1 for n in qualified.values())
    result = {'schema': 'control-campaign-report/v1', 'planned': len(expected), 'attempts': len(attempts),
              'missing': len(set(expected) - {a['cell'] for a in attempts}),
              'qualifiedComplete': complete, 'uiVerifiedSuccesses': sum(ui_pass(effective_record(a)) for a in attempts),
              'lifecycleAcceptedAttempts': lifecycle_passes,
              'lifecycleChecksAccepted': complete and lifecycle_passes == len(attempts),
              'wholePackageAccepted': complete and lifecycle_passes == len(attempts) and
                  sum(ui_pass(effective_record(a)) for a in attempts) == len(attempts),
              'sourceRevision': plan['revision'], 'profile': plan['profile'], 'seed': plan['seed'],
              'acceptanceScope': list(TASKS),
              'heldOutUIVerifiedSuccesses': sum(ui_pass(effective_record(a)) for a in attempts if expected[a['cell']]['heldOut']),
              'runtimeChecks': dict(collections.Counter(a.get('runtime', {}).get('status', 'missing') for a in attempts)),
              'runtimeReferenceFingerprints': sorted({a['runtime']['referenceFingerprint'] for a in attempts
                  if a.get('runtime', {}).get('referenceFingerprint')}),
              'groups': [], 'pairedComparisons': [], 'limits': LIMITS}
    for (stage, task, route, arm), rows in sorted(groups.items()):
        outcomes = {}
        for kind in ('success', 'failed', 'unverified', 'invalid'):
            records = [r for r, k, _ in rows if k == kind]
            tokens = [token_metrics(r.get('tokenUsage'), plan['profile']['provider']) for r in records]
            outcomes[kind] = {'attempts': len(records),
                'usage': {key: distribution([m[key] for m in tokens if m.get(key) is not None])
                          for key in sorted({key for m in tokens for key in m})},
                'resources': {key: {'distribution': distribution([r[key] for r in records if r.get(key) is not None]),
                                   'sum': sum(r[key] for r in records if r.get(key) is not None),
                                   'measuredAttempts': sum(r.get(key) is not None for r in records)}
                              for key in ('agentSeconds', 'postAcquisitionPreCleanupSeconds', 'runnerInvocationSeconds', 'toolCalls', 'toolOutputBytes')},
                'tokenSums': {key: {'sum': sum(m[key] for m in tokens if m.get(key) is not None),
                                    'measuredAttempts': sum(m.get(key) is not None for m in tokens)}
                              for key in sorted({key for m in tokens for key in m})}}
        result['groups'].append({'stage': stage, 'task': task, 'route': route, 'arm': arm,
            'outcomes': outcomes, 'lifecycle': {key: dict(collections.Counter(c[key] for _, _, c in rows)) for key in CHECKS},
            'routeReviews': dict(collections.Counter((r.get('routeReview') or {}).get('routeAdherence', 'unreviewed') for r, _, _ in rows)),
            'confirmationReviews': dict(collections.Counter((r.get('routeReview') or {}).get('confirmationPolicyAdherence', 'unreviewed') for r, _, _ in rows)),
            'effectPasses': sum((r.get('oracle') or {}).get('passed') is True for r, _, _ in rows),
            'effectPassesWithRouteViolation': sum((r.get('oracle') or {}).get('passed') is True and
                (r.get('routeReview') or {}).get('routeAdherence') == 'violated' for r, _, _ in rows),
            'effectPassesWithConfirmationViolation': sum((r.get('oracle') or {}).get('passed') is True and
                (r.get('routeReview') or {}).get('confirmationPolicyAdherence') == 'violated' for r, _, _ in rows),
            'timeouts': sum(r.get('timedOut') is True for r, _, _ in rows),
            'preUIDiscoveryCalls': distribution([len(r['routeReview']['preUIDiscoveryCalls'])
                for r, _, _ in rows if 'preUIDiscoveryCalls' in (r.get('routeReview') or {})]),
            'reportedTokensBeforeFirstUI': distribution([
                r['routeReview']['usageReportedBeforeFirstUICall']['totalTokens'] for r, _, _ in rows
                if (r.get('routeReview') or {}).get('usageReportedBeforeFirstUICall', {}).get('totalTokens') is not None]),
            'providerErrors': dict(collections.Counter(str(e) for r, _, _ in rows for e in r.get('providerErrors', [])))})
    baseline = {(r['task'], r['repetition']): r for r in plan['rows']
                if r['stage'] == 'paired' and r['route'] == 'machine-control' and r['arm'] == 'discovery'}
    for route, arm in sorted({(r['route'], r['arm']) for r in plan['rows']} - {('machine-control', 'discovery')}):
        pairs = [(baseline[(r['task'], r['repetition'])], r) for r in plan['rows']
                 if r['stage'] == 'paired' and (r['route'], r['arm']) == (route, arm)]
        both = [(successes[a['id']], successes[b['id']]) for a, b in pairs
                if a['id'] in successes and b['id'] in successes]
        result['pairedComparisons'].append({'baseline': 'machine-control/discovery', 'route': route, 'arm': arm,
            'plannedPairs': len(pairs), 'bothUIVerified': len(both),
            'cohorts': {name: {'plannedPairs': sum((a['task'] in HELD_OUT) == held for a, _ in pairs),
                'bothUIVerified': sum((a['task'] in HELD_OUT) == held and a['id'] in successes and b['id'] in successes
                                      for a, b in pairs)} for name, held in [('familiar', False), ('heldOut', True)]},
            'uiPairOutcomes': dict(collections.Counter(
                ('pass' if a['id'] in successes else 'not_verified') + '/' +
                ('pass' if b['id'] in successes else 'not_verified') for a, b in pairs)),
            'successfulPairDeltasCandidateMinusDiscovery': {key: distribution([b[key] - a[key] for a, b in both
                if a.get(key) is not None and b.get(key) is not None]) for key in ('agentSeconds', 'runnerInvocationSeconds', 'toolCalls', 'toolOutputBytes')}})
    return result


def check_source(source, revision=None):
    source = Path(source).resolve()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip():
        raise ValueError('Selected source must be clean, including fixtures and instructions')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
    if revision is not None and revision != head:
        raise ValueError('Selected source differs from fixed revision')
    return head


def execute_runner(command, source, root):
    """Wait for our isolated child even when the controller requests a stop.

    Parent handlers defer SIGINT/SIGTERM. A new session prevents terminal/group
    signals from bypassing those handlers and interrupting child cleanup.
    """
    started = time.monotonic()
    timing = {'schema': 'control-campaign-invocation/v1'}
    try:
        completed = subprocess.run(command, cwd=source, capture_output=True, text=True,
                                   start_new_session=True)
        timing['runnerInvocationSeconds'] = time.monotonic() - started
        timing['returncode'] = completed.returncode
        (root/'runner.stdout').write_text(completed.stdout)
        (root/'runner.stderr').write_text(completed.stderr)
        if completed.returncode:
            raise RuntimeError(f'Existing runner exited {completed.returncode}; inspect private output')
        return completed
    except BaseException as error:
        timing['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        timing.setdefault('runnerInvocationSeconds', time.monotonic() - started)
        write_new(root/'invocation.json', timing)


def runtime_identity(value):
    keys = ('service', 'artifacts', 'configSha256', 'commands')
    identity = {key: value[key] for key in keys}
    if not all(isinstance(identity[key], dict) and identity[key] for key in ('service', 'artifacts', 'commands')):
        raise ValueError('Incomplete runtime fingerprint')
    if not isinstance(identity['configSha256'], str) or not identity['configSha256']:
        raise ValueError('Missing runtime configuration hash')
    return identity


def fingerprint(identity):
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check_runtime(directory, root, *, allow_pin=False):
    """Compare observed installed bytes with one immutable campaign reference."""
    result = {'status': 'missing'}
    paths = list(root.glob('run-*/*/*/runtime.json'))
    references = list(root.glob('run-*/runtime-reference.json'))
    try:
        if len(paths) != 1 or len(references) != 1:
            raise ValueError('Expected one observed runtime and batch reference')
        identity = runtime_identity(json.loads(paths[0].read_text()))
        result['observedFingerprint'] = fingerprint(identity)
        if runtime_identity(json.loads(references[0].read_text())) != identity:
            raise ValueError('Observed runtime differs from batch reference')
        reference = directory/'runtime-reference.json'
        if not reference.exists():
            if not allow_pin:
                raise ValueError('Campaign runtime reference missing; refusing to repin')
            write_new(reference, identity)
            result['status'] = 'pinned'
        else:
            result['status'] = 'matched'
        expected = runtime_identity(json.loads(reference.read_text()))
        result['referenceFingerprint'] = fingerprint(expected)
        if identity != expected:
            result['status'] = 'mismatch'
        result['evidenceHashes'] = {str(path.relative_to(directory)): digest(path)
                                    for path in (paths[0], references[0], reference)}
    except (OSError, ValueError, KeyError, TypeError) as error:
        result.update(status='missing', error=str(error))
    return result


def runtime_qualified(result):
    return (result.get('status') in ('pinned', 'matched') and
            bool(result.get('observedFingerprint')) and
            result.get('observedFingerprint') == result.get('referenceFingerprint'))


def effective_record(attempt):
    record = dict(attempt['record'])
    if attempt.get('driverError'):
        record['driverError'] = attempt['driverError']
    if not runtime_qualified(attempt.get('runtime', {})):
        record['driverError'] = record.get('driverError') or 'Campaign runtime fingerprint unqualified'
    record['runnerInvocationSeconds'] = attempt.get('runnerInvocationSeconds')
    # Existing runner interval ends BEFORE teardown and starts AFTER acquisition.
    record['postAcquisitionPreCleanupSeconds'] = record.get('wallSeconds')
    return record


def run_stage(source, plan, directory, stage, options, harness):
    """Injectable existing runner boundary; no implicit retries or parallel target use."""
    directory = Path(directory)
    for cell in plan['rows']:
        if cell['stage'] != stage:
            continue
        while (directory/'pause').exists() and not STOP_REQUESTED and not (directory/'stop').exists():
            time.sleep(1)
        if STOP_REQUESTED or (directory/'stop').exists():
            raise RuntimeError('Stopped between trials after prior cleanup')
        root = directory / cell['id']
        root.mkdir(mode=0o700)  # Refuse overwriting any previous attempt.
        args = SimpleNamespace(**vars(options), **{k: v for k, v in plan['profile'].items() if k != 'speed'},
            instructions=cell['arm'], revision=plan['revision'], seed=cell['trialSeed'], task_root=source/'tests/experiments'/cell['taskRoot'],
            poll_seconds=1.0)
        attempt = {'cell': cell['id'], 'record': {'error': 'runner did not return'}}
        try:
            task = json.loads((args.task_root/cell['task']/'task.json').read_text())
            attempt['record'] = harness.run_trial(args, task, cell['route'], 1, root)
        except BaseException as error:
            attempt['driverError'] = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            receipts = list(root.glob('run-*/*/*/trial.json'))
            raw = receipts[0] if len(receipts) == 1 else root/'missing-trial.json'
            if raw.is_file():
                attempt['record'] = json.loads(raw.read_text())
                attempt['trial'] = str(raw.parent.relative_to(directory))
                attempt['receiptSha256'] = digest(raw)
            timing = root/'invocation.json'
            if timing.exists():
                attempt['runnerInvocationSeconds'] = json.loads(timing.read_text())['runnerInvocationSeconds']
            attempt['runtime'] = check_runtime(directory, root, allow_pin=cell == plan['rows'][0] and stage == 'pilot')
            write_new(root/'attempt.json', attempt)
        record = effective_record(attempt)
        validate_record(plan, cell, record)
        if (not valid_trial(record) or not clean(record) or
                record.get('fixtureSeed') != cell['fixtureSeed']):
            raise RuntimeError('Unqualified trial or cleanup; preserve attempt and stop for review')


def load_attempts(directory, plan):
    from review_trial import load_receipt
    attempts = []
    for path in sorted(directory.glob('cell-*/attempt.json')):
        attempt = json.loads(path.read_text())
        if attempt.get('cell') != path.parent.name or attempt['cell'] not in {r['id'] for r in plan['rows']}:
            raise ValueError('Attempt tree does not match planned cell')
        if attempt.get('trial'):
            trial = (directory/attempt['trial']).resolve()
            if not trial.is_relative_to(path.parent.resolve()) or digest(trial/'trial.json') != attempt['receiptSha256']:
                raise ValueError('Attempt receipt changed or escaped campaign')
            attempt['record'] = load_receipt(trial)
        for name, expected_hash in attempt.get('runtime', {}).get('evidenceHashes', {}).items():
            evidence_path = (directory/name).resolve()
            if not evidence_path.is_relative_to(directory.resolve()) or digest(evidence_path) != expected_hash:
                raise ValueError('Pinned runtime evidence changed')
        annotation = path.parent/'acceptance.json'
        if annotation.exists():
            evidence = json.loads(annotation.read_text())
            if evidence.get('receiptSha256') != attempt.get('receiptSha256') or not attempt.get('receiptSha256'):
                raise ValueError('Lifecycle review is not receipt-bound')
            attempt['lifecycle'] = evidence['checks']
        attempts.append(attempt)
    return attempts


def pilot_evidence_hashes(directory):
    """Bind the review decision to both original receipts and subsequent reviews."""
    names = {'invocation.json', 'runtime.json', 'runtime-reference.json', 'attempt.json', 'trial.json', 'transcript.jsonl', 'review.json', 'evaluation.json', 'acceptance.json'}
    paths = list(directory.glob('cell-*/**/*')) + [directory/'runtime-reference.json']
    return {str(path.relative_to(directory)): digest(path)
            for path in sorted(paths) if path.is_file() and path.name in names}


def require_pilot_review(directory, plan):
    if not (directory/'continue').is_file():
        raise ValueError('Pilot continue gate is closed')
    runtime_identity(json.loads((directory/'runtime-reference.json').read_text()))
    review = json.loads((directory/'pilot-review.json').read_text())
    attempts = load_attempts(directory, plan)
    expected = {row['id'] for row in plan['rows'] if row['stage'] == 'pilot'}
    if (review.get('campaignSha256') != digest(directory/'campaign.json') or
            review.get('evidenceHashes') != pilot_evidence_hashes(directory) or
            review.get('decision') != 'continue' or not review.get('notes') or
            len(attempts) != len(expected) or {a['cell'] for a in attempts} != expected):
        raise ValueError('Pilot requires a complete hash-bound review')
    cells = {cell['id']: cell for cell in plan['rows']}
    for attempt in attempts:
        record = effective_record(attempt)
        validate_record(plan, cells[attempt['cell']], record)
        route_review = record.get('routeReview') or {}
        if (not valid_trial(record) or not clean(record) or
                route_review.get('routeAdherence') != 'conforming' or
                route_review.get('confirmationPolicyAdherence') not in ('conforming', 'not_applicable')):
            raise ValueError('Pilot requires qualified, clean, route/policy-reviewed trials')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    planning = sub.add_parser('plan', help='Offline; writes a private fixed plan')
    planning.add_argument('--source', type=Path, required=True)
    planning.add_argument('--output', type=Path, required=True)
    planning.add_argument('--provider', choices=('codex', 'claude'), default='codex')
    planning.add_argument('--model', default='gpt-6.1-sol')
    planning.add_argument('--effort', choices=('low', 'medium', 'high'), default='medium')
    planning.add_argument('--route', action='append', help='Default: machine-control only')
    planning.add_argument('--seed', type=int, required=True)
    planning.add_argument('--repetitions', type=int, default=3)
    planning.add_argument('--include-current', action='store_true', help='Optional diagnostic arm')
    running = sub.add_parser('run', help='LIVE; only after separate target authorization')
    running.add_argument('--source', type=Path, required=True)
    running.add_argument('--campaign', type=Path, required=True)
    running.add_argument('--stage', choices=('pilot', 'paired'), required=True)
    running.add_argument('--target', required=True)
    running.add_argument('--credential-file', type=Path, required=True)
    running.add_argument('--gateway-credential-file', type=Path)
    running.add_argument('--ssh-key', type=Path, required=True)
    running.add_argument('--known-hosts', type=Path, required=True)
    running.add_argument('--host-key-alias', required=True)
    running.add_argument('--guest-user', required=True)
    running.add_argument('--project', required=True)
    reporting = sub.add_parser('report', help='Offline; print aggregate without raw evidence')
    reporting.add_argument('campaign', type=Path)
    options = parser.parse_args()
    os.umask(0o077)
    if options.command == 'plan':
        revision = check_source(options.source)
        plan = make_plan(revision, options.provider, options.model, options.effort,
                         options.route or ['machine-control'], options.seed, options.repetitions, options.include_current)
        plan['driverSha256'] = digest(__file__)
        options.output.mkdir(parents=True, mode=0o700)
        write_new(options.output/'campaign.json', plan)
        return
    directory = options.campaign.resolve()
    plan = json.loads((directory/'campaign.json').read_text())
    validate_plan(plan)
    if options.command == 'report':
        report = summarize(plan, load_attempts(directory, plan))
        report['campaignSha256'] = digest(directory/'campaign.json')
        report['evaluatorHashes'] = {name: digest(Path(__file__).parent/name) for name in
            ('control_campaign.py', 'report_batch.py', 'measurements.py', 'review_trial.py', 'agent_profiles.py')}
        print(json.dumps(report, indent=2))
        return
    source = options.source.resolve()
    check_source(source, plan['revision'])
    if digest(__file__) != plan['driverSha256']:
        raise ValueError('Campaign driver changed after planning')
    sys.path.insert(0, str(source/'tests/experiments'))
    from campaign import private_secret
    private_secret(options.credential_file)
    if plan['profile']['provider'] == 'claude':
        if not options.gateway_credential_file:
            parser.error('Claude requires a scoped gateway credential file')
        private_secret(options.gateway_credential_file)
    if options.stage == 'paired':
        require_pilot_review(directory, plan)
    help_text = subprocess.check_output([sys.executable, str(source/'tests/experiments/route_comparison.py'), '--help'], text=True)
    if '--task-root' not in help_text:
        raise ValueError('Runner integration required: selected source must support --task-root')
    def invoke(args, task, route, index, root):
        command = [sys.executable, str(source/'tests/experiments/route_comparison.py'),
            '--task-root', str(args.task_root), '--task', task['id'], '--route', route,
            '--provider', args.provider, '--model', args.model, '--effort', args.effort,
            '--instructions', args.instructions, '--seed', str(args.seed), '--repetitions', '1',
            '--revision', args.revision, '--results', str(root)]
        for name in ('target', 'credential_file', 'ssh_key', 'known_hosts', 'host_key_alias', 'guest_user', 'project'):
            command.extend(['--' + name.replace('_', '-'), str(getattr(args, name))])
        if args.gateway_credential_file:
            command.extend(['--gateway-credential-file', str(args.gateway_credential_file)])
        check_source(source, plan['revision'])
        execute_runner(command, source, root)
        paths = list(root.glob('run-*/*/*/trial.json'))
        if len(paths) != 1:
            raise RuntimeError('Expected exactly one existing-runner receipt')
        return json.loads(paths[0].read_text())
    def stop(signum, frame):
        global STOP_REQUESTED
        STOP_REQUESTED = True  # Let the existing runner finish disposal first.
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    run_stage(source, plan, directory, options.stage, options, SimpleNamespace(run_trial=invoke))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Summarize actual AX/oracle receipts; never enables a production policy."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


def summarize(root: Path) -> dict[str, Any]:
    run = json.loads((root / 'run.json').read_text())
    records_path = root / 'records.json'
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    notification_path = root / 'notifications.json'
    notifications = json.loads(notification_path.read_text()) if notification_path.exists() else []
    if run.get('schema') != 'machine-control/native-identity-run/v1':
        raise ValueError('unknown run schema')
    if not isinstance(records, list) or not isinstance(notifications, list):
        raise ValueError('receipt arrays required')
    snapshots = {r['scenario']: r for r in records if r.get('kind') == 'snapshot'}
    actions = [r for r in records if r.get('kind') == 'action']
    reads, replacements = run['reads'], run['replacements']
    if type(reads) is not int or not 2 <= reads <= 50 or type(replacements) is not int or not 1 <= replacements <= 50:
        raise ValueError('invalid declared corpus size')
    required = {'initial', 'insertion', 'reorder', 'removal', 'window_recreation', 'process_recreation'}
    required.update(f'unchanged_{i}' for i in range(1, reads + 1))
    required.update(f'replacement_{i}' for i in range(1, replacements + 1))
    required_actions = {'initial_current', 'removal_stale', 'window_recreation_stale',
                        'window_recreation_current', 'process_recreation_stale',
                        'process_recreation_current', 'initial_after_process_recreation_stale'}
    required_actions.update(f'replacement_{i}_{kind}' for i in range(1, replacements + 1)
                            for kind in ('current', 'stale'))
    missing = sorted(required - snapshots.keys())
    missing_actions = sorted(required_actions - {a['scenario'] for a in actions})
    duplicate_samples = len(snapshots) != sum(r.get('kind') == 'snapshot' for r in records)
    duplicate_actions = len({a['scenario'] for a in actions}) != len(actions)
    processes = run.get('ownedProcesses', [])
    cleanup = run.get('cleanup', [])
    cleanup_complete = (len(processes) == 2 and len(cleanup) == 2 and
                        {(p['pid'], p['processIncarnation']) for p in processes} ==
                        {(c['pid'], c['processIncarnation']) for c in cleanup} and
                        all(c.get('reaped') is True for c in cleanup))
    violations: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    registrations: Counter[str] = Counter()
    validity: Counter[str] = Counter()
    handle_definitions: dict[str, dict[str, Any]] = {}
    consistency_errors: list[str] = []
    previous: set[str] = set()
    owned = {p['processIncarnation']: p['pid'] for p in processes}
    for sample in snapshots.values():
        scenario = sample['scenario']
        oracle = sample['oracle']
        if (oracle.get('runNonce') != run.get('runNonce') or
                owned.get(oracle['processIncarnation']) != oracle['pid']):
            consistency_errors.append(scenario + ': oracle process/run mismatch')
        controls = {i['incarnation'] for i in oracle['items']}
        window = 'identity-window-' + oracle['windowIncarnation']
        current = {h['handle']: h for h in sample['handles']}
        actual_controls = {h['oracleIncarnation'] for h in current.values() if h['kind'] == 'control'}
        actual_windows = {h['oracleIncarnation'] for h in current.values() if h['kind'] == 'window'}
        if actual_controls != controls or len(actual_controls) != len(oracle['items']) or actual_windows != {window}:
            consistency_errors.append(scenario + ': oracle/AX coverage mismatch')
        if len(current) != len(sample['handles']) or previous.intersection(current):
            consistency_errors.append(scenario + ': duplicate local handle')
        for handle in current.values():
            if handle['processIncarnation'] != oracle['processIncarnation'] or handle['windowIncarnation'] != oracle['windowIncarnation']:
                consistency_errors.append(scenario + ': handle scope mismatch')
            if handle['kind'] == 'control':
                item = next(i for i in oracle['items'] if i['incarnation'] == handle['oracleIncarnation'])
                if handle['native'].get('AXIdentifier') != item['identifier']:
                    consistency_errors.append(scenario + ': identifier join mismatch')
            registrations[str(handle['destroyRegistration'])] += 1
            handle_definitions[handle['handle']] = handle
        pairs: set[tuple[str, str]] = set()
        for pair in sample['comparisons']:
            key = (pair['prior'], pair['current'])
            if key in pairs or key[0] not in previous or key[1] not in current:
                consistency_errors.append(scenario + ': invalid comparison pair')
                continue
            pairs.add(key)
            old, new = handle_definitions[key[0]], current[key[1]]
            same_process = old['processIncarnation'] == new['processIncarnation']
            same_window = old['windowIncarnation'] == new['windowIncarnation']
            same = same_process and same_window and old['oracleIncarnation'] == new['oracleIncarnation']
            if (pair['sameOracleIncarnation'] != same or pair['sameProcessEpoch'] != same_process or
                    pair['sameWindowEpoch'] != same_window):
                consistency_errors.append(scenario + ': comparison oracle mismatch')
            counters['comparisons'] += 1
            if same:
                counters['surviving_incarnation_pairs'] += 1
                if not pair['nativeEqual']:
                    violations.append(dict(scenario=scenario, finding='survivor_native_inequality', **pair))
            if pair['nativeEqual'] and not pair['hashEqual']:
                violations.append(dict(scenario=scenario, finding='equal_hash_disagreement', **pair))
            if pair['nativeEqual'] and not same:
                counters['cross_incarnation_equal_pairs'] += 1
                if same_process and same_window:
                    violations.append(dict(scenario=scenario, finding='same_scope_cross_incarnation_equal', **pair))
                else:
                    counters['cross_scope_equal_pairs'] += 1
        if len(pairs) != len(previous) * len(current):
            consistency_errors.append(scenario + ': incomplete comparison matrix')
        valid_handles: set[str] = set()
        for retained in sample['retainedValidity']:
            handle = retained['handle']
            if handle in valid_handles or handle not in previous:
                consistency_errors.append(scenario + ': invalid validity handle')
                continue
            valid_handles.add(handle)
            old = handle_definitions[handle]
            still_present = (old['processIncarnation'] == oracle['processIncarnation'] and
                             old['windowIncarnation'] == oracle['windowIncarnation'] and
                             old['oracleIncarnation'] in controls | {window})
            if retained['oracleStillPresent'] != still_present:
                consistency_errors.append(scenario + ': validity oracle mismatch')
            validity[f"{'present' if still_present else 'retired'}:AXRole={retained['roleReadError']}"] += 1
        if valid_handles != previous:
            consistency_errors.append(scenario + ': incomplete validity matrix')
        previous.update(current)

    current_action_failures = []
    stale_effects = []
    for action in actions:
        if action['handle'] not in handle_definitions:
            consistency_errors.append(action['scenario'] + ': action handle missing')
            continue
        before, after = action['before']['effects'], action['after']['effects']
        handle = handle_definitions[action['handle']]
        actual_current = (handle['processIncarnation'] == action['before']['processIncarnation'] and
                          handle['windowIncarnation'] == action['before']['windowIncarnation'] and
                          handle['oracleIncarnation'] in {i['incarnation'] for i in action['before']['items']})
        if (actual_current != action['expectedCurrent'] or action['oracleIncarnation'] != handle['oracleIncarnation'] or
                action['expectedCurrent'] != action['scenario'].endswith('_current')):
            consistency_errors.append(action['scenario'] + ': action identity/expectation mismatch')
        for state in (action['before'], action['after']):
            if (state.get('runNonce') != run.get('runNonce') or
                    owned.get(state['processIncarnation']) != state['pid']):
                consistency_errors.append(action['scenario'] + ': action process/run mismatch')
        if (action['before']['processIncarnation'] != action['after']['processIncarnation'] or
                action['before']['windowIncarnation'] != action['after']['windowIncarnation'] or
                action['before']['items'] != action['after']['items']):
            consistency_errors.append(action['scenario'] + ': action oracle changed scope/tree')
        deltas = {key: after.get(key, 0) - before.get(key, 0) for key in before.keys() | after.keys()
                  if after.get(key, 0) != before.get(key, 0)}
        if action['effectDeltas'] != deltas:
            consistency_errors.append(action['scenario'] + ': effect delta mismatch')
        if action['expectedCurrent']:
            if action['axError'] != 0 or deltas != {action['oracleIncarnation']: 1}:
                current_action_failures.append(action['scenario'])
        elif deltas:
            present = {i['incarnation'] for i in action['after']['items']}
            stale_effects.append(dict(scenario=action['scenario'], axError=action['axError'], deltas=deltas,
                                     affectedCurrentIncarnations=sorted(present & deltas.keys())))

    replacements_checked = []
    prior = snapshots.get('reorder')
    for index in range(1, replacements + 1):
        current = snapshots.get(f'replacement_{index}')
        if prior and current:
            before = next(i for i in prior['oracle']['items'] if i['logical'] == 'a')
            after = next(i for i in current['oracle']['items'] if i['logical'] == 'a')
            before_native = next(h['native'] for h in prior['handles'] if h['oracleIncarnation'] == before['incarnation'])
            after_native = next(h['native'] for h in current['handles'] if h['oracleIncarnation'] == after['incarnation'])
            same_native = all(key in before_native and key in after_native and before_native[key] == after_native[key]
                              for key in ('AXTitle', 'AXPosition', 'AXSize'))
            replacements_checked.append(dict(scenario=current['scenario'],
                differentIncarnation=before['incarnation'] != after['incarnation'],
                sameIdentifier=before['identifier'] == after['identifier'],
                sameNativePresentation=same_native,
                sameLabel=before['label'] == after['label'], sameFrame=before['frame'] == after['frame']))
        prior = current
    replacement_controls_valid = (len(replacements_checked) == replacements and
                                 all(r['differentIncarnation'] and r['sameIdentifier'] and r['sameLabel'] and
                                     r['sameFrame'] and r['sameNativePresentation']
                                     for r in replacements_checked))
    scopes_valid = False
    if all(name in snapshots for name in ('removal', 'window_recreation', 'process_recreation')):
        before = snapshots['removal']['oracle']
        window = snapshots['window_recreation']['oracle']
        process = snapshots['process_recreation']['oracle']
        scopes_valid = (before['processIncarnation'] == window['processIncarnation'] != process['processIncarnation'] and
                        before['windowIncarnation'] != window['windowIncarnation'] != process['windowIncarnation'])
    transitions: dict[tuple[str, int], dict[str, Any]] = {}
    for sample in snapshots.values():
        for event in sample['oracle'].get('events', []):
            if event['kind'] in ('removed', 'deallocated', 'windowClosed'):
                transitions[(sample['oracle']['processIncarnation'], event['sequence'])] = event
    lifetimes = []
    for (process, _), event in transitions.items():
        incarnation = ('identity-window-' + event['incarnation'] if event['kind'] == 'windowClosed'
                       else event['incarnation'])
        handles = {key for key, value in handle_definitions.items()
                   if value['processIncarnation'] == process and value['oracleIncarnation'] == incarnation}
        callbacks = [n for n in notifications if n['name'] == 'AXUIElementDestroyed' and
                     handles.intersection(n['equalRetainedHandles'])]
        retired_errors = sorted({v['roleReadError'] for sample in snapshots.values()
                                 for v in sample['retainedValidity']
                                 if v['handle'] in handles and not v['oracleStillPresent']})
        lifetimes.append(dict(processIncarnation=process, incarnation=incarnation, event=event,
                              observedHandleCount=len(handles),
                              registrationErrors=sorted({handle_definitions[h]['destroyRegistration'] for h in handles}),
                              destructionCallbackCount=len(callbacks), retiredRoleReadErrors=retired_errors,
                              callbackOffsetsFromEventSeconds=[n['uptime'] - event['uptime'] for n in callbacks]))
    complete = (run['status'] == 'complete' and not missing and not missing_actions and not duplicate_samples and
                not duplicate_actions and cleanup_complete and not consistency_errors and
                replacement_controls_valid and scopes_valid)
    qualified = complete and not violations and not current_action_failures
    return dict(schema='machine-control/native-identity-summary/v1',
        status='bounded_candidate_observed' if qualified else 'incomplete' if not complete else 'candidate_requires_revision',
        complete=complete, missingSnapshots=missing, missingActions=missing_actions,
        consistencyErrors=consistency_errors, duplicateSamples=duplicate_samples, duplicateActions=duplicate_actions,
        cleanupComplete=cleanup_complete, replacementControls=replacements_checked, scopeTransitionsValid=scopes_valid,
        counters=dict(counters), nativeIdentityViolations=violations,
        currentActionFailures=current_action_failures, rawStaleActionEffects=stale_effects,
        destroyRegistrationErrors=dict(registrations), retainedRoleReadErrors=dict(validity),
        lifetimeEventCoverage=lifetimes,
        notificationCount=len(notifications), destructionNotificationCount=sum(n['name'] == 'AXUIElementDestroyed' for n in notifications),
        policyCandidate=('process and window incarnation epoch + native CFEqual + fresh complete current-tree membership; '
                         'invalidate on epoch, uncertain reads or ambiguous equality; revalidate before dispatch') if qualified else None,
        limits=['Owned AppKit fixture only; not general provider qualification or a production identity implementation',
                'Process/window incarnation epochs here are independent oracle fields; deriving trustworthy resident epochs remains implementation work',
                'No guarantee of never-reused tokens, complete notification delivery, or absence of races between preflight and dispatch',
                'Hash is diagnostic/bucketing only; labels, frames, identifiers and positions are not native identity keys',
                'Old-proxy action probes intentionally bypass production guards inside the owned fixture; preserve every effect',
                'No native latency, tokenizer, model cost or task-efficiency claim'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    try:
        report = summarize(args.root)
    except (ValueError, TypeError, KeyError, OSError, StopIteration) as error:
        report = dict(schema='machine-control/native-identity-summary/v1', status='invalid_receipts', error=str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report['status'] == 'bounded_candidate_observed' else 1)

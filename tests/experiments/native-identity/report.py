#!/usr/bin/env python3
"""Summarize actual AX/oracle receipts; never enables a production policy."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ALREADY_REGISTERED = -25209
NATIVE_FIELDS = ('AXRole', 'AXIdentifier', 'AXTitle', 'AXPosition', 'AXSize')


def registration_statuses(handles: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(h['destroyRegistration'] for h in handles)
    return dict(success=statuses[0], alreadyRegistered=statuses[ALREADY_REGISTERED],
                errors={str(k): v for k, v in statuses.items() if k not in (0, ALREADY_REGISTERED)})


def validate_corpus(root: Path, run: dict[str, Any], records: list[dict[str, Any]],
                    snapshots: dict[str, Any], notifications: list[dict[str, Any]],
                    errors: list[str]) -> tuple[list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Check this owned fixture's script, not a general AX tree or OS contract."""
    reads, replacements = run['reads'], run['replacements']
    schedule = [('snapshot', 'initial'), ('action', 'initial_current')]
    sources = {'initial_current': ('initial', 'a')}
    schedule += [('snapshot', f'unchanged_{i}') for i in range(1, reads + 1)]
    schedule += [('snapshot', 'insertion'), ('snapshot', 'reorder')]
    prior = 'reorder'
    for i in range(1, replacements + 1):
        name = f'replacement_{i}'
        schedule += [('snapshot', name), ('action', name + '_stale'), ('action', name + '_current')]
        sources[name + '_stale'] = (prior, 'a')
        sources[name + '_current'] = (name, 'a')
        prior = name
    schedule += [('snapshot', 'removal'), ('action', 'removal_stale'),
                 ('snapshot', 'window_recreation'), ('action', 'window_recreation_stale'),
                 ('action', 'window_recreation_current'), ('snapshot', 'process_recreation'),
                 ('action', 'process_recreation_stale'), ('action', 'process_recreation_current'),
                 ('action', 'initial_after_process_recreation_stale')]
    sources.update(removal_stale=(prior, 'b'), window_recreation_stale=('removal', 'a'),
                   window_recreation_current=('window_recreation', 'a'),
                   process_recreation_stale=('window_recreation', 'a'),
                   process_recreation_current=('process_recreation', 'a'),
                   initial_after_process_recreation_stale=('initial', 'a'))
    expected_records = [('observerCreated', None)]
    for entry in schedule:
        if entry == ('snapshot', 'process_recreation'):
            expected_records.append(('observerCreated', None))
        expected_records.append(entry)
    actual = [(r['kind'], r.get('scenario')) for r in records]
    if actual != expected_records:
        errors.append('corpus: unexpected scenario chronology or record kind')

    def scope(state):
        return state['processIncarnation'], state['windowIncarnation']

    # Incarnations and order come from the oracle; native equality never uses
    # these slot identifiers or presentation values as identity keys.
    previous = None
    previous_sample = None
    seen_incarnations: set[str] = set()
    seen_windows: set[str] = set()
    for kind, name in schedule:
        if kind != 'snapshot' or name not in snapshots:
            continue
        state = snapshots[name]['oracle']
        owned_processes = run.get('ownedProcesses', [])
        expected_process = 1 if name == 'process_recreation' else 0
        if (len(owned_processes) != 2 or
                state['processIncarnation'] != owned_processes[expected_process]['processIncarnation']):
            errors.append(name + ': unexpected process launch epoch')
        items = state['items']
        logical = [i['logical'] for i in items]
        ids = [i['incarnation'] for i in items]
        if len(set(logical)) != len(items) or len(set(ids)) != len(items):
            errors.append(name + ': duplicate oracle slot/incarnation')
        if any(i['identifier'] != 'identity-slot-' + i['logical'] for i in items):
            errors.append(name + ': unexpected oracle slot identifier')
        if name == 'initial':
            valid = logical == ['a', 'b', 'c']
        elif previous is None:
            valid = False
        else:
            old = previous['items']
            old_by_slot = {i['logical']: i['incarnation'] for i in old}
            by_slot = dict(zip(logical, ids))
            old_order = [i['logical'] for i in old]
            same_scope = scope(state) == scope(previous)
            if name.startswith('unchanged_'):
                valid = same_scope and items == old
                old_native = {h['oracleIncarnation']: h['native'] for h in previous_sample['handles']}
                if {h['oracleIncarnation']: h['native'] for h in snapshots[name]['handles']} != old_native:
                    errors.append(name + ': unchanged native presentation changed')
            elif name == 'insertion':
                valid = (same_scope and logical == ['a', 'inserted', 'b', 'c'] and
                         all(by_slot.get(k) == v for k, v in old_by_slot.items()) and
                         by_slot.get('inserted') not in seen_incarnations)
            elif name == 'reorder':
                valid = same_scope and logical == list(reversed(old_order)) and by_slot == old_by_slot
            elif name.startswith('replacement_'):
                valid = (same_scope and logical == old_order and by_slot.get('a') not in seen_incarnations and
                         all(by_slot.get(k) == v for k, v in old_by_slot.items() if k != 'a'))
            elif name == 'removal':
                valid = (same_scope and logical == [k for k in old_order if k != 'b'] and
                         by_slot == {k: v for k, v in old_by_slot.items() if k != 'b'})
            else:
                same_process = state['processIncarnation'] == previous['processIncarnation']
                valid = (logical == ['a', 'b', 'c'] and not seen_incarnations.intersection(ids) and
                         state['windowIncarnation'] not in seen_windows and
                         same_process == (name == 'window_recreation'))
        if not valid:
            errors.append(name + ': fixture transition mismatch')
        seen_incarnations.update(ids)
        seen_windows.add(state['windowIncarnation'])
        previous = state
        previous_sample = snapshots[name]

    evidence: list[tuple[str, dict[str, Any]]] = []
    latest: dict[str, dict[str, Any]] = {}
    owned = {p['processIncarnation']: p['pid'] for p in run.get('ownedProcesses', [])}
    last_uptime = -1

    def observe(state, source, final=False):
        nonlocal last_uptime
        count = len(errors)
        process = state['processIncarnation']
        if (state.get('schema') != 'machine-control/native-identity-oracle/v1' or
                state.get('runNonce') != run.get('runNonce') or owned.get(process) != state['pid']):
            errors.append(source + ': oracle process/run/schema mismatch')
        if not final:
            if state['uptime'] < last_uptime:
                errors.append(source + ': cross-process oracle chronology mismatch')
            last_uptime = state['uptime']
        events = state['events']
        times = [e['uptime'] for e in events]
        if ([e['sequence'] for e in events] != list(range(1, len(events) + 1)) or
                any(not math.isfinite(t) or t < 0 or t > state['uptime'] for t in times) or
                times != sorted(times) or not math.isfinite(state['uptime']) or
                type(state['revision']) is not int):
            errors.append(source + ': invalid oracle event chronology')
        created = [e['incarnation'] for e in events if e['kind'] == 'created']
        windows = {e['incarnation'] for e in events if e['kind'] == 'windowCreated'}
        retired = {e['incarnation'] for e in events if e['kind'] in ('removed', 'deallocated')}
        if (len(set(created)) != len(created) or
                not retired.issubset(created) or
                any(e['incarnation'] not in windows for e in events if e['kind'] == 'windowClosed') or
                any(i['incarnation'] not in created or i['incarnation'] in retired for i in state['items']) or
                state['windowIncarnation'] not in windows):
            errors.append(source + ': oracle lifetime/item mismatch')
        effects = state['effects']
        if (any(type(v) is not int or v <= 0 for v in effects.values()) or
                dict(Counter(e['incarnation'] for e in events if e['kind'] == 'press')) != effects):
            errors.append(source + ': effect/event mismatch')
        if process in latest:
            old = latest[process]
            if (state['uptime'] < old['uptime'] or state['revision'] < old['revision'] or
                    (not final and state['revision'] == old['revision']) or
                    events[:len(old['events'])] != old['events']):
                errors.append(source + ': oracle chronology/prefix mismatch')
            if final and (scope(state) != scope(old) or state['items'] != old['items'] or
                          effects != old['effects'] or state['revision'] != old['revision'] or
                          any(e['kind'] not in ('deallocated', 'quit') for e in events[len(old['events']):])):
                errors.append(source + ': final state changed scope/tree/effects')
        elif final:
            errors.append(source + ': final state has no observed process')
        if not final or len(errors) == count:
            latest[process] = state
            evidence.append((source, state))
        return len(errors) == count

    active = None
    last_effects = None
    observers = []
    for index, record in enumerate(records):
        kind = record['kind']
        if kind == 'observerCreated':
            observers.append(record)
            if record['axError'] != 0 or owned.get(record['processIncarnation']) != record['pid']:
                errors.append('observer: creation failed or process mismatch')
            continue
        if kind == 'snapshot':
            state = record['oracle']
            if last_effects is not None and active is not None and scope(state)[0] == scope(active)[0] and state['effects'] != last_effects:
                errors.append(record['scenario'] + ': unexplained effect between records')
            observe(state, f'records[{index}].oracle')
            active, last_effects = state, state['effects']
            if not any(o['processIncarnation'] == state['processIncarnation'] for o in observers):
                errors.append(record['scenario'] + ': snapshot before observer creation')
        elif kind == 'action':
            name = record['scenario']
            before, after = record['before'], record['after']
            if (active is None or scope(before) != scope(active) or before['items'] != active['items'] or
                    before['effects'] != last_effects):
                errors.append(name + ': action not bound to preceding snapshot/effects')
            if name in sources:
                source, logical = sources[name]
                sample = snapshots.get(source)
                expected = [] if sample is None else [h['handle'] for h in sample['handles']
                    if h['kind'] == 'control' and h['oracleIncarnation'] in
                    {i['incarnation'] for i in sample['oracle']['items'] if i['logical'] == logical}]
                if expected != [record['handle']]:
                    errors.append(name + ': action source snapshot/slot mismatch')
            observe(before, f'records[{index}].before')
            observe(after, f'records[{index}].after')
            last_effects = after['effects']
    if ([o['processIncarnation'] for o in observers] !=
            [p['processIncarnation'] for p in run.get('ownedProcesses', [])]):
        errors.append('observer: expected one creation per owned process in launch order')

    final_states = []
    for index, process in enumerate(run.get('ownedProcesses', []), 1):
        source = f'process-{index}/state.json'
        path = root / source
        if not path.exists():
            final_states.append(dict(source=source, status='absent'))
            continue
        state = json.loads(path.read_text())
        bound = (state['processIncarnation'] == process['processIncarnation'] and state['pid'] == process['pid'])
        if not bound:
            errors.append(source + ': final state does not match owned process slot')
        valid = bound and observe(state, source, final=True)
        final_states.append(dict(source=source, status='validated' if valid else 'invalid'))

    last_time = -1
    definitions = {h['handle']: h for s in snapshots.values() for h in s['handles']}
    for index, notification in enumerate(notifications):
        handles = notification['equalRetainedHandles']
        scopes = {(definitions[h]['processIncarnation'], definitions[h]['windowIncarnation'],
                   definitions[h]['oracleIncarnation']) for h in handles if h in definitions}
        if (notification['name'] != 'AXUIElementDestroyed' or not handles or len(scopes) != 1 or
                len(set(handles)) != len(handles) or any(h not in definitions for h in handles) or
                not math.isfinite(notification['uptime']) or notification['uptime'] < last_time):
            errors.append(f'notifications[{index}]: ambiguous handle correlation or chronology')
        last_time = notification['uptime']
    return evidence, final_states


def validate_traversal(sample: dict[str, Any], errors: list[str]) -> None:
    name = sample['scenario']
    items = sample['oracle']['items']
    traversal = sample.get('traversal', [])
    slots = [n for n in traversal if n.get('AXIdentifier', '').startswith('identity-slot-')]
    expected = [i['identifier'] for i in items]
    if Counter(n['AXIdentifier'] for n in slots) != Counter(expected):
        errors.append(name + ': native traversal slot coverage mismatch')
        return
    windows = [n for n in traversal if n.get('AXRole') == 'AXWindow']
    depths = [n.get('depth') for n in traversal]
    if (len(windows) != 1 or not traversal or windows[0] is not traversal[0] or
            windows[0].get('AXIdentifier') != 'identity-window' or depths[0] != 0 or
            len(traversal) > 2000 or any(type(d) is not int or not 0 <= d <= 20 for d in depths) or
            any(d <= 0 or d > before + 1 for before, d in zip(depths, depths[1:]))):
        errors.append(name + ': native traversal window root mismatch')
        return
    native = {n['AXIdentifier']: n for n in slots + windows}
    for handle in sample['handles']:
        node = native.get(handle['native'].get('AXIdentifier'))
        role = 'AXButton' if handle['kind'] == 'control' else 'AXWindow'
        if (node is None or node.get('AXRole') != role or
                any(node.get(k + 'Error') != 0 or node.get(k) != handle['native'].get(k) or
                    handle['native'].get(k + 'Error') != 0 for k in NATIVE_FIELDS)):
            errors.append(name + ': native traversal/retained attributes mismatch')
    transforms = []
    for item in items:
        node = native[item['identifier']]
        frame = item['frame']
        position, size = node['AXPosition'], node['AXSize']
        values = list(frame.values()) + position + size
        if (len(position) != 2 or len(size) != 2 or any(not math.isfinite(v) for v in values) or
                min(frame['width'], frame['height'], *size) <= 0 or node['AXTitle'] != item['label']):
            errors.append(name + ': invalid native/oracle presentation')
        transforms.append((position[0] - frame['x'], position[1] + frame['y'] + frame['height'],
                           size[0] - frame['width'], size[1] - frame['height']))
    # AX uses top-left screen coordinates and AppKit bottom-left coordinates;
    # the owned equal-sized buttons also have a common accessibility inset.
    # Infer only a common per-snapshot transform, never an identity key.
    if transforms and any(any(abs(a - b) > 0.01 for a, b in zip(t, transforms[0])) for t in transforms):
        errors.append(name + ': native/oracle relative geometry mismatch')
    if ([i['identifier'] for i in sorted(items, key=lambda i: -i['frame']['y'])] != expected or
            [n['AXIdentifier'] for n in sorted(slots, key=lambda n: n['AXPosition'][1])] != expected):
        errors.append(name + ': native/oracle layout order mismatch')


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
                        len({p['processIncarnation'] for p in processes}) == 2 and
                        {(p['pid'], p['processIncarnation']) for p in processes} ==
                        {(c['pid'], c['processIncarnation']) for c in cleanup} and
                        all(c.get('reaped') is True for c in cleanup))
    violations: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    registrations: Counter[str] = Counter()
    validity: Counter[str] = Counter()
    handle_definitions: dict[str, dict[str, Any]] = {}
    consistency_errors: list[str] = []
    if not notification_path.exists():
        consistency_errors.append('notifications.json: required receipt missing')
    evidence, final_states = validate_corpus(root, run, records, snapshots, notifications, consistency_errors)
    previous: set[str] = set()
    owned = {p['processIncarnation']: p['pid'] for p in processes}
    for sample in snapshots.values():
        scenario = sample['scenario']
        oracle = sample['oracle']
        validate_traversal(sample, consistency_errors)
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
            if (handle['processIncarnation'] != oracle['processIncarnation'] or
                    handle['windowIncarnation'] != oracle['windowIncarnation'] or handle['pid'] != oracle['pid']):
                consistency_errors.append(scenario + ': handle scope mismatch')
            if handle['kind'] == 'control':
                item = next(i for i in oracle['items'] if i['incarnation'] == handle['oracleIncarnation'])
                if handle['native'].get('AXIdentifier') != item['identifier']:
                    consistency_errors.append(scenario + ': identifier join mismatch')
            if handle['destroyRegistration'] == ALREADY_REGISTERED and not any(
                    h['processIncarnation'] == handle['processIncarnation'] and
                    h['windowIncarnation'] == handle['windowIncarnation'] and
                    h['oracleIncarnation'] == handle['oracleIncarnation'] and h['destroyRegistration'] == 0
                    for h in handle_definitions.values()):
                consistency_errors.append(scenario + ': duplicate registration without prior successful registration')
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
    event_sources: dict[tuple[str, int], list[str]] = {}
    for source, state in evidence:
        for event in state.get('events', []):
            if event['kind'] in ('removed', 'deallocated', 'windowClosed'):
                key = (state['processIncarnation'], event['sequence'])
                transitions[key] = event
                event_sources.setdefault(key, []).append(source)
    lifetimes = []
    for (process, _), event in transitions.items():
        incarnation = ('identity-window-' + event['incarnation'] if event['kind'] == 'windowClosed'
                       else event['incarnation'])
        handles = {key for key, value in handle_definitions.items()
                   if value['processIncarnation'] == process and value['oracleIncarnation'] == incarnation}
        callback_indices = [i for i, n in enumerate(notifications) if n['name'] == 'AXUIElementDestroyed' and
                            handles.intersection(n['equalRetainedHandles'])]
        callbacks = [notifications[i] for i in callback_indices]
        retired_errors = sorted({v['roleReadError'] for sample in snapshots.values()
                                 for v in sample['retainedValidity']
                                 if v['handle'] in handles and not v['oracleStillPresent']})
        lifetimes.append(dict(processIncarnation=process, incarnation=incarnation, event=event,
                              evidenceSources=event_sources[(process, event['sequence'])],
                              observedHandleCount=len(handles),
                              registration=registration_statuses([handle_definitions[h] for h in handles]),
                              registrationErrors=sorted({handle_definitions[h]['destroyRegistration'] for h in handles
                                  if handle_definitions[h]['destroyRegistration'] not in (0, ALREADY_REGISTERED)}),
                              callbackIndices=callback_indices,
                              destructionCallbackCount=len(callbacks), retiredRoleReadErrors=retired_errors,
                              callbackOffsetsFromEventSeconds=[n['uptime'] - event['uptime'] for n in callbacks]))
    object_coverage = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for handle in handle_definitions.values():
        key = (handle['processIncarnation'], handle['windowIncarnation'], handle['oracleIncarnation'])
        grouped.setdefault(key, []).append(handle)
    for (process, window, incarnation), handles in grouped.items():
        keys = {h['handle'] for h in handles}
        indices = [i for i, n in enumerate(notifications) if keys.intersection(n['equalRetainedHandles'])]
        object_coverage.append(dict(processIncarnation=process, windowIncarnation=window, incarnation=incarnation,
                                    registration=registration_statuses(handles), callbackIndices=indices,
                                    lifetimeEvents=sorted({e['kind'] for (p, _), e in transitions.items()
                                        if p == process and (('identity-window-' + e['incarnation'])
                                            if e['kind'] == 'windowClosed' else e['incarnation']) == incarnation})))
    complete = (run['status'] == 'complete' and not missing and not missing_actions and not duplicate_samples and
                not duplicate_actions and cleanup_complete and not consistency_errors and
                replacement_controls_valid and scopes_valid)
    qualified = complete and not violations and not current_action_failures
    tool_dir = Path(__file__).resolve().parent
    evaluator_hashes = {name: hashlib.sha256((tool_dir / name).read_bytes()).hexdigest()
                        for name in ('report.py', 'test_report.py')}
    original_hashes = run.get('build', {}).get('source_sha256', {})
    return dict(schema='machine-control/native-identity-summary/v1',
        evaluator=dict(sourceSha256=evaluator_hashes,
                       originalBuildSourceSha256={name: original_hashes.get(name) for name in evaluator_hashes},
                       matchesOriginalBuild={name: evaluator_hashes[name] == original_hashes.get(name)
                                             for name in evaluator_hashes}),
        status='bounded_candidate_observed' if qualified else 'incomplete' if not complete else 'candidate_requires_revision',
        complete=complete, missingSnapshots=missing, missingActions=missing_actions,
        consistencyErrors=consistency_errors, duplicateSamples=duplicate_samples, duplicateActions=duplicate_actions,
        cleanupComplete=cleanup_complete, replacementControls=replacements_checked, scopeTransitionsValid=scopes_valid,
        counters=dict(counters), nativeIdentityViolations=violations,
        currentActionFailures=current_action_failures, rawStaleActionEffects=stale_effects,
        destroyRegistrationStatuses=dict(registrations),
        destroyRegistration=registration_statuses(list(handle_definitions.values())),
        destroyRegistrationErrors={k: v for k, v in registrations.items() if int(k) not in (0, ALREADY_REGISTERED)},
        retainedRoleReadErrors=dict(validity),
        lifetimeEventCoverage=lifetimes, notificationObjectCoverage=object_coverage,
        finalProcessStates=final_states, notificationReceiptsPresent=notification_path.exists(),
        notificationCount=len(notifications), destructionNotificationCount=sum(n['name'] == 'AXUIElementDestroyed' for n in notifications),
        policyCandidate=('process and window incarnation epoch + native CFEqual + fresh complete current-tree membership; '
                         'invalidate on epoch, uncertain reads or ambiguous equality; revalidate before dispatch') if qualified else None,
        limits=['Owned AppKit fixture only; not general provider qualification or a production identity implementation',
                'Process/window incarnation epochs here are independent oracle fields; deriving trustworthy resident epochs remains implementation work',
                'No guarantee of never-reused tokens, complete notification delivery, or absence of races between preflight and dispatch',
                'NotificationAlreadyRegistered is duplicate registration, not failed installation; absent callbacks do not establish loss',
                'Lifetime rows can share callbackIndices; count unique notification receipts, not the sum of per-event callback counts',
                'Optional final process states extend lifetime evidence only after identity, chronology, event-prefix and unchanged tree/effect checks',
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

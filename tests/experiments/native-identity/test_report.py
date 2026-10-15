"""Parser/evaluator controls only: these fabricated receipts are not AX evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build import build
from report import summarize


def corpus(*, insert=True, reorder=True, remove=True, replace=True):
    run = dict(schema='machine-control/native-identity-run/v1', status='complete', reads=2,
               replacements=1, runNonce='fixture-run', ownedProcesses=[
                   dict(pid=100, processIncarnation='p1'), dict(pid=101, processIncarnation='p2')],
               cleanup=[dict(pid=100, processIncarnation='p1', reaped=True),
                        dict(pid=101, processIncarnation='p2', reaped=True)])
    records, handles = [], {}
    process, window = 'p1', 'w1'
    items = [('a', 'a1'), ('b', 'b1'), ('c', 'c1')]
    effects, events = {}, []
    clock, revision = 0, 0
    registered = set()

    def event(kind, incarnation):
        nonlocal clock
        clock += 1
        events.append(dict(sequence=len(events) + 1, kind=kind, incarnation=incarnation, uptime=float(clock)))

    def state():
        nonlocal clock, revision
        clock += 1
        revision += 1
        return dict(schema='machine-control/native-identity-oracle/v1', runNonce='fixture-run',
                    pid=100 if process == 'p1' else 101, processIncarnation=process, windowIncarnation=window,
                    revision=revision, uptime=float(clock), events=deepcopy(events), effects=deepcopy(effects),
                    items=[dict(logical=logical, incarnation=id, identifier='identity-slot-' + logical, label='Same label',
                                frame=dict(x=20, y=400 - index * 40, width=220, height=32))
                           for index, (logical, id) in enumerate(items)])

    def snapshot(scenario):
        oracle = state()
        current, comparisons, validity = [], [], []
        for item in oracle['items'] + [dict(incarnation='identity-window-' + window, identifier='identity-window')]:
            id = item['incarnation']
            kind = 'window' if item['identifier'] == 'identity-window' else 'control'
            frame = item.get('frame', dict(x=0, y=0, width=360, height=500))
            native = dict(AXIdentifier=item['identifier'], AXTitle='Same label',
                          AXRole='AXWindow' if kind == 'window' else 'AXButton',
                          AXPosition=[frame['x'] - 1, 800 - frame['y'] - frame['height'] - 1],
                          AXSize=[frame['width'] + 2, frame['height'] + 2])
            native.update({key + 'Error': 0 for key in list(native)})
            registration_key = (process, window, id)
            handle = dict(handle=f'h{len(handles) + len(current) + 1}', oracleIncarnation=id,
                          processIncarnation=process, windowIncarnation=window,
                          pid=oracle['pid'], kind=kind, destroyRegistration=-25209 if registration_key in registered else 0,
                          native=native)
            registered.add(registration_key)
            current.append(handle)
            for old in handles.values():
                same = (old['oracleIncarnation'] == id and old['processIncarnation'] == process and
                        old['windowIncarnation'] == window)
                comparisons.append(dict(prior=old['handle'], current=handle['handle'], sameOracleIncarnation=same,
                    sameProcessEpoch=old['processIncarnation'] == process, sameWindowEpoch=old['windowIncarnation'] == window,
                    nativeEqual=same, hashEqual=same))
        for old in handles.values():
            present = (old['processIncarnation'] == process and old['windowIncarnation'] == window and
                       old['oracleIncarnation'] in {i['oracleIncarnation'] for i in current})
            validity.append(dict(handle=old['handle'], oracleStillPresent=present, roleReadError=0 if present else -25202))
        # Deliberately keep enumeration in slot order while layout reverses.
        ordered = [current[-1]] + sorted(current[:-1], key=lambda h: h['native']['AXIdentifier'])
        traversal = [dict(h['native'], depth=0 if h['kind'] == 'window' else 1) for h in ordered]
        records.append(dict(kind='snapshot', scenario=scenario, oracle=oracle, handles=current,
                            comparisons=comparisons, retainedValidity=validity, traversal=traversal))
        handles.update({h['handle']: h for h in current})
        return next(h for h in current if h['oracleIncarnation'] == dict(items)['a'])

    def action(handle, scenario, expected):
        before = state()
        if expected:
            effects[handle['oracleIncarnation']] = effects.get(handle['oracleIncarnation'], 0) + 1
            event('press', handle['oracleIncarnation'])
        after = state()
        records.append(dict(kind='action', scenario=scenario, handle=handle['handle'],
            oracleIncarnation=handle['oracleIncarnation'], expectedCurrent=expected, axError=0 if expected else -25202,
            effectDeltas={handle['oracleIncarnation']: 1} if expected else {}, before=before, after=after))

    def create():
        for _, id in items:
            event('created', id)
        event('windowCreated', window)
        records.append(dict(kind='observerCreated', pid=100 if process == 'p1' else 101,
                            processIncarnation=process, axError=0))

    create()
    initial = snapshot('initial'); action(initial, 'initial_current', True)
    snapshot('unchanged_1'); snapshot('unchanged_2')
    if insert:
        items.insert(1, ('inserted', 'i1')); event('created', 'i1')
    snapshot('insertion')
    if reorder:
        items.reverse()
    old = snapshot('reorder')
    if replace:
        index = next(i for i, (logical, _) in enumerate(items) if logical == 'a')
        event('removed', items[index][1]); event('deallocated', items[index][1])
        items[index] = ('a', 'a2'); event('created', 'a2')
    current = snapshot('replacement_1')
    action(old, 'replacement_1_stale', False); action(current, 'replacement_1_current', True)
    removed = next(h for h in reversed(list(handles.values())) if h['oracleIncarnation'] == 'b1')
    if remove:
        items = [i for i in items if i[0] != 'b']; event('removed', 'b1'); event('deallocated', 'b1')
    current = snapshot('removal'); action(removed, 'removal_stale', False)
    old = current; event('windowClosed', window)
    window = 'w2'; items = [('a', 'a3'), ('b', 'b2'), ('c', 'c2')]
    for _, id in items:
        event('created', id)
    event('windowCreated', window)
    current = snapshot('window_recreation'); action(old, 'window_recreation_stale', False)
    action(current, 'window_recreation_current', True)
    old = current; process = 'p2'; window = 'w3'; items = [('a', 'a4'), ('b', 'b3'), ('c', 'c3')]
    effects, events, revision = {}, [], 0
    create()
    current = snapshot('process_recreation'); action(old, 'process_recreation_stale', False)
    action(current, 'process_recreation_current', True)
    action(initial, 'initial_after_process_recreation_stale', False)
    return run, records


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run, self.records = corpus()
        self.notifications = []

    def report(self):
        (self.root / 'run.json').write_text(json.dumps(self.run))
        (self.root / 'records.json').write_text(json.dumps(self.records))
        (self.root / 'notifications.json').write_text(json.dumps(self.notifications))
        return summarize(self.root)

    def sample(self, name):
        return next(r for r in self.records if r.get('scenario') == name)

    def assert_incomplete(self, fragment):
        result = self.report()
        self.assertEqual(result['status'], 'incomplete')
        self.assertIsNone(result['policyCandidate'])
        self.assertTrue(any(fragment in e for e in result['consistencyErrors']), result['consistencyErrors'])
        return result

    def test_complete_control_yields_only_bounded_policy_candidate(self):
        result = self.report()
        self.assertEqual(result['status'], 'bounded_candidate_observed')
        self.assertEqual(result['notificationCount'], 0)
        self.assertIn('fresh complete current-tree membership', result['policyCandidate'])

    def test_replayed_noop_transitions_do_not_qualify(self):
        # Rebuild complete, internally consistent matrices around a skipped
        # operation: this catches coverage gates, not merely broken pair data.
        for option, name in [('insert', 'insertion'), ('reorder', 'reorder'),
                             ('replace', 'replacement_1'), ('remove', 'removal')]:
            with self.subTest(operation=option):
                self.run, self.records = corpus(**{option: False})
                self.assert_incomplete(name + ': fixture transition mismatch')

    def test_mislabeled_insertion_and_unchanged_cannot_qualify(self):
        a, b = self.sample('insertion'), self.sample('unchanged_2')
        a['scenario'], b['scenario'] = b['scenario'], a['scenario']
        self.assert_incomplete('scenario chronology')

    def test_oracle_only_reorder_cannot_qualify(self):
        sample = self.sample('reorder')
        order = [i['logical'] for i in self.sample('insertion')['oracle']['items']]
        sample['oracle']['items'].sort(key=lambda i: order.index(i['logical']))
        self.assert_incomplete('fixture transition mismatch')

    def test_native_enumeration_need_not_follow_layout_order(self):
        insertion, reorder = self.sample('insertion'), self.sample('reorder')
        self.assertEqual([n['AXIdentifier'] for n in insertion['traversal']],
                         [n['AXIdentifier'] for n in reorder['traversal']])
        self.assertNotEqual(insertion['oracle']['items'], reorder['oracle']['items'])
        self.assertEqual(self.report()['status'], 'bounded_candidate_observed')

    def test_missing_duplicate_or_mismatched_native_traversal_fails(self):
        for mutation in ('missing', 'duplicate', 'attribute', 'layout', 'depth'):
            with self.subTest(mutation=mutation):
                self.run, self.records = corpus()
                sample = self.sample('reorder')
                if mutation == 'missing':
                    sample['traversal'].pop()
                elif mutation == 'duplicate':
                    sample['traversal'].append(deepcopy(sample['traversal'][1]))
                elif mutation == 'attribute':
                    sample['traversal'][1]['AXTitle'] = 'Unrelated button'
                elif mutation == 'depth':
                    sample['traversal'][1]['depth'] = 3
                else:
                    # Both native copies agree, but the oracle's reversed
                    # positions were never applied to the actual AX buttons.
                    before = {n['AXIdentifier']: n for n in self.sample('insertion')['traversal']}
                    for node in sample['traversal']:
                        node['AXPosition'] = before[node['AXIdentifier']]['AXPosition']
                    for h in sample['handles']:
                        h['native']['AXPosition'] = before[h['native']['AXIdentifier']]['AXPosition']
                self.assert_incomplete('native')

    def test_action_chronology_and_prescribed_source_are_checked(self):
        a, b = self.records.index(self.sample('replacement_1_stale')), self.records.index(self.sample('replacement_1_current'))
        self.records[a], self.records[b] = self.records[b], self.records[a]
        self.assert_incomplete('scenario chronology')
        self.run, self.records = corpus()
        action = self.sample('replacement_1_stale')
        # Same surviving incarnation as the intended stale proxy, but from an
        # earlier read: oracle membership alone cannot establish provenance.
        handle = next(h for h in self.sample('initial')['handles'] if h['oracleIncarnation'] == 'a1')
        action['handle'] = handle['handle']
        self.assert_incomplete('action source snapshot/slot mismatch')

    def test_action_before_tree_and_oracle_time_cannot_be_rewritten(self):
        self.sample('replacement_1_current')['before']['items'].reverse()
        self.assert_incomplete('action not bound')
        self.run, self.records = corpus()
        self.sample('unchanged_2')['oracle']['uptime'] = 0
        self.assert_incomplete('chronology')

    def test_process_restart_cannot_reset_the_system_uptime_or_move_observer(self):
        # Preserve each new-process state's internally valid event timing and
        # increasing revisions while moving the whole process before p1.
        for record in self.records:
            states = [record['oracle']] if record['kind'] == 'snapshot' else (
                [record['before'], record['after']] if record['kind'] == 'action' else [])
            for state in states:
                if state['processIncarnation'] == 'p2':
                    state['uptime'] -= 40
                    for event in state['events']:
                        event['uptime'] -= 40
        self.assert_incomplete('cross-process oracle chronology')
        self.run, self.records = corpus()
        observer = next(r for r in self.records if r['kind'] == 'observerCreated' and r['processIncarnation'] == 'p2')
        self.records.remove(observer)
        self.records.insert(1, observer)
        self.assert_incomplete('scenario chronology')

    def test_unchanged_presentation_and_event_prefix_must_survive(self):
        self.sample('unchanged_2')['oracle']['items'][0]['frame']['x'] += 1
        self.assert_incomplete('fixture transition mismatch')
        self.run, self.records = corpus()
        self.sample('unchanged_2')['oracle']['events'][0]['incarnation'] = 'invented'
        self.assert_incomplete('prefix mismatch')

    def test_missing_notification_receipt_differs_from_observed_empty_array(self):
        self.assertTrue(self.report()['complete'])
        (self.root / 'notifications.json').unlink()
        result = summarize(self.root)
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(result['notificationReceiptsPresent'])
        self.assertIn('notifications.json: required receipt missing', result['consistencyErrors'])

    def test_duplicate_registration_is_not_a_failed_installation(self):
        result = self.report()
        self.assertGreater(result['destroyRegistration']['success'], 0)
        self.assertGreater(result['destroyRegistration']['alreadyRegistered'], 0)
        self.assertEqual(result['destroyRegistrationErrors'], {})
        self.assertEqual(result['destroyRegistration']['errors'], {})
        self.assertEqual(result['notificationCount'], 0)
        self.assertTrue(result['complete'])  # Absent callbacks are not loss.
        self.sample('initial')['handles'][0]['destroyRegistration'] = -25209
        self.assert_incomplete('duplicate registration without prior successful')

    def test_real_registration_failure_is_reported_separately(self):
        self.sample('process_recreation')['handles'][0]['destroyRegistration'] = -25206
        result = self.report()
        self.assertEqual(result['destroyRegistration']['errors'], {'-25206': 1})
        self.assertEqual(result['destroyRegistrationErrors'], {'-25206': 1})
        self.assertTrue(result['complete'])  # Identity evidence does not depend on observer coverage.

    def test_optional_final_state_extends_only_matching_process_lifetimes(self):
        final = deepcopy(self.sample('window_recreation_current')['after'])
        final['uptime'] += 2
        final['events'].append(dict(sequence=len(final['events']) + 1, kind='deallocated',
                                    incarnation='a2', uptime=final['uptime'] - 1))
        folder = self.root / 'process-1'
        folder.mkdir()
        path = folder / 'state.json'
        path.write_text(json.dumps(final))
        handle = next(h['handle'] for h in self.sample('removal')['handles'] if h['oracleIncarnation'] == 'a2')
        self.notifications = [dict(name='AXUIElementDestroyed', equalRetainedHandles=[handle], uptime=final['uptime'])]
        result = self.report()
        self.assertTrue(result['complete'], result['consistencyErrors'])
        lifetime = next(e for e in result['lifetimeEventCoverage']
                        if e['incarnation'] == 'a2' and e['event']['kind'] == 'deallocated')
        self.assertEqual(lifetime['evidenceSources'], ['process-1/state.json'])
        self.assertEqual(lifetime['callbackIndices'], [0])
        for mutation in ('identity', 'prefix', 'scope', 'time', 'effects', 'revision', 'new_operation'):
            with self.subTest(mutation=mutation):
                bad = deepcopy(final)
                if mutation == 'identity':
                    bad['processIncarnation'] = 'unowned'
                elif mutation == 'prefix':
                    bad['events'][0]['incarnation'] = 'rewritten'
                elif mutation == 'scope':
                    bad['windowIncarnation'] = 'old-window'
                elif mutation == 'time':
                    bad['uptime'] = 0
                elif mutation == 'effects':
                    bad['effects']['a2'] = 100
                elif mutation == 'revision':
                    bad['revision'] += 1
                else:
                    bad['events'].append(dict(sequence=len(bad['events']) + 1, kind='created',
                                               incarnation='unobserved', uptime=bad['uptime']))
                path.write_text(json.dumps(bad))
                result = self.assert_incomplete('process-1/state.json')
                self.assertFalse(any(e['incarnation'] == 'a2' and e['event']['kind'] == 'deallocated'
                                     for e in result['lifetimeEventCoverage']))

    def test_ambiguous_notification_join_is_not_counted_as_qualified_evidence(self):
        handles = self.sample('initial')['handles']
        self.notifications = [dict(name='AXUIElementDestroyed', equalRetainedHandles=[h['handle'] for h in handles[:2]], uptime=1000)]
        self.assert_incomplete('ambiguous handle correlation')

    def test_evaluator_provenance_does_not_relabel_original_build(self):
        self.run['build'] = dict(source_sha256={'report.py': 'original-report', 'test_report.py': 'original-tests'})
        result = self.report()
        provenance = result['evaluator']
        self.assertEqual(provenance['originalBuildSourceSha256'], self.run['build']['source_sha256'])
        self.assertEqual(provenance['matchesOriginalBuild'], {'report.py': False, 'test_report.py': False})
        self.assertEqual(len(provenance['sourceSha256']['report.py']), 64)

    def test_missing_reorder_or_cleanup_cannot_qualify(self):
        self.records = [r for r in self.records if r.get('scenario') != 'reorder']
        self.run['cleanup'][0]['reaped'] = False
        result = self.report()
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(result['cleanupComplete'])

    def test_survivor_inequality_and_same_scope_alias_reject_candidate(self):
        sample = next(r for r in self.records if r.get('scenario') == 'unchanged_1')
        same = next(p for p in sample['comparisons'] if p['sameOracleIncarnation'])
        same['nativeEqual'] = False
        different = next(p for p in sample['comparisons'] if not p['sameOracleIncarnation'])
        different['nativeEqual'] = different['hashEqual'] = True
        result = self.report()
        self.assertEqual(result['status'], 'candidate_requires_revision')
        self.assertEqual(len(result['nativeIdentityViolations']), 2)

    def test_cross_epoch_alias_is_reported_and_excluded_from_scope_policy(self):
        sample = next(r for r in self.records if r.get('scenario') == 'process_recreation')
        sample['comparisons'][0].update(nativeEqual=True, hashEqual=True)
        result = self.report()
        self.assertEqual(result['status'], 'bounded_candidate_observed')
        self.assertEqual(result['counters']['cross_scope_equal_pairs'], 1)

    def test_identical_frame_requirement_and_effect_oracle_are_enforced(self):
        sample = next(r for r in self.records if r.get('scenario') == 'replacement_1')
        sample['oracle']['items'][-1]['frame']['width'] += 1
        current = next(r for r in self.records if r.get('scenario') == 'initial_current')
        current['after']['effects'] = {}; current['effectDeltas'] = {}
        result = self.report()
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['currentActionFailures'], ['initial_current'])
        self.assertFalse(result['replacementControls'][0]['sameFrame'])

    def test_stale_callback_effect_is_preserved_not_hidden_as_refusal(self):
        action = next(r for r in self.records if r.get('scenario') == 'replacement_1_stale')
        action.update(axError=0, effectDeltas={'a2': 1})
        action['after']['effects'] = {'a2': 1}
        result = self.report()
        self.assertEqual(result['rawStaleActionEffects'][0]['affectedCurrentIncarnations'], ['a2'])

    def test_forged_or_missing_pairs_cannot_qualify(self):
        sample = next(r for r in self.records if r.get('scenario') == 'unchanged_1')
        sample['comparisons'].pop()
        sample['oracle']['pid'] = 999
        result = self.report()
        self.assertEqual(result['status'], 'incomplete')
        self.assertTrue(result['consistencyErrors'])

    def test_destroy_callback_correlates_to_independent_removed_incarnation(self):
        sample = next(r for r in self.records if r.get('scenario') == 'replacement_1')
        event = next(e for e in sample['oracle']['events'] if e['kind'] == 'removed' and e['incarnation'] == 'a1')
        self.notifications = [dict(name='AXUIElementDestroyed', equalRetainedHandles=['h1'], uptime=event['uptime'] + 0.25)]
        result = self.report()
        self.assertTrue(result['complete'], result['consistencyErrors'])
        lifetime = result['lifetimeEventCoverage'][0]
        self.assertEqual(lifetime['incarnation'], 'a1')
        self.assertEqual(lifetime['destructionCallbackCount'], 1)
        self.assertEqual(lifetime['callbackOffsetsFromEventSeconds'], [0.25])
        same_object = [e for e in result['lifetimeEventCoverage'] if e['incarnation'] == 'a1']
        self.assertEqual([e['event']['kind'] for e in same_object], ['removed', 'deallocated'])
        self.assertEqual([e['callbackIndices'] for e in same_object], [[0], [0]])
        self.assertEqual(result['destructionNotificationCount'], 1)

    def test_build_only_compiles_and_signs_without_launching(self):
        def execute(command, **kwargs):
            if command[0] == 'swiftc':
                Path(command[-1]).write_bytes(b'compiled-fixture')
        output = self.root / 'build'
        with patch('build.subprocess.run', side_effect=execute) as run, \
                patch('build.subprocess.check_output', return_value='offline compiler'):
            build(output)
        self.assertTrue((output / 'IdentityFixture.app/Contents/Info.plist').exists())
        self.assertTrue((output / 'IdentityProbe.app/Contents/Info.plist').exists())
        self.assertEqual([c.args[0][0] for c in run.call_args_list], ['swiftc', 'swiftc', 'codesign', 'codesign'])
        self.assertEqual(len(json.loads((output / 'build.json').read_text())['binary_sha256']), 2)


if __name__ == '__main__':
    unittest.main()

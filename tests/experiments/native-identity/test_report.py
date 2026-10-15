"""Parser/evaluator controls only: these fabricated receipts are not AX evidence."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build import build
from report import summarize


def corpus():
    run = dict(schema='machine-control/native-identity-run/v1', status='complete', reads=2,
               replacements=1, runNonce='fixture-run', ownedProcesses=[
                   dict(pid=100, processIncarnation='p1'), dict(pid=101, processIncarnation='p2')],
               cleanup=[dict(pid=100, processIncarnation='p1', reaped=True),
                        dict(pid=101, processIncarnation='p2', reaped=True)])
    records, handles = [], {}
    process, window = 'p1', 'w1'
    items = [('a', 'a1'), ('b', 'b1'), ('c', 'c1')]

    def state():
        return dict(runNonce='fixture-run', pid=100 if process == 'p1' else 101,
                    processIncarnation=process, windowIncarnation=window,
                    items=[dict(logical=logical, incarnation=id, identifier='identity-slot-' + logical, label='Same label',
                                frame=dict(x=20, y=40, width=220, height=32)) for logical, id in items], effects={})

    def snapshot(scenario):
        current, comparisons, validity = [], [], []
        for id, kind in [(i, 'control') for _, i in items] + [('identity-window-' + window, 'window')]:
            native_id = ('identity-slot-' + next(logical for logical, incarnation in items if incarnation == id)
                         if kind == 'control' else 'identity-window')
            handle = dict(handle=f'h{len(handles) + len(current) + 1}', oracleIncarnation=id,
                          processIncarnation=process, windowIncarnation=window,
                          kind=kind, destroyRegistration=0,
                          native=dict(AXIdentifier=native_id, AXTitle='Same label', AXPosition=[20, 40], AXSize=[220, 32]))
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
        records.append(dict(kind='snapshot', scenario=scenario, oracle=state(), handles=current,
                            comparisons=comparisons, retainedValidity=validity))
        handles.update({h['handle']: h for h in current})
        return next(h for h in current if h['oracleIncarnation'] == dict(items)['a'])

    def action(handle, scenario, expected):
        before, after = state(), state()
        if expected:
            after['effects'] = {handle['oracleIncarnation']: 1}
        records.append(dict(kind='action', scenario=scenario, handle=handle['handle'],
            oracleIncarnation=handle['oracleIncarnation'], expectedCurrent=expected, axError=0 if expected else -25202,
            effectDeltas=deepcopy(after['effects']), before=before, after=after))

    initial = snapshot('initial'); action(initial, 'initial_current', True)
    snapshot('unchanged_1'); snapshot('unchanged_2')
    items.insert(1, ('inserted', 'i1')); snapshot('insertion')
    items.reverse(); old = snapshot('reorder')
    items[-1] = ('a', 'a2'); current = snapshot('replacement_1')
    action(old, 'replacement_1_stale', False); action(current, 'replacement_1_current', True)
    removed = next(h for h in reversed(list(handles.values())) if h['oracleIncarnation'] == 'b1')
    items = [i for i in items if i[0] != 'b']; current = snapshot('removal')
    action(removed, 'removal_stale', False)
    old = current; window = 'w2'; items = [('a', 'a3'), ('b', 'b2'), ('c', 'c2')]
    current = snapshot('window_recreation'); action(old, 'window_recreation_stale', False)
    action(current, 'window_recreation_current', True)
    old = current; process = 'p2'; window = 'w3'; items = [('a', 'a4'), ('b', 'b3'), ('c', 'c3')]
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

    def report(self):
        (self.root / 'run.json').write_text(json.dumps(self.run))
        (self.root / 'records.json').write_text(json.dumps(self.records))
        (self.root / 'notifications.json').write_text('[]')
        return summarize(self.root)

    def test_complete_control_yields_only_bounded_policy_candidate(self):
        result = self.report()
        self.assertEqual(result['status'], 'bounded_candidate_observed')
        self.assertEqual(result['notificationCount'], 0)
        self.assertIn('fresh complete current-tree membership', result['policyCandidate'])

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
        sample['oracle']['events'] = [dict(sequence=1, kind='removed', incarnation='a1', uptime=1.0)]
        self.report()
        (self.root / 'notifications.json').write_text(json.dumps([
            dict(name='AXUIElementDestroyed', equalRetainedHandles=['h1'], uptime=1.25)]))
        result = summarize(self.root)
        lifetime = result['lifetimeEventCoverage'][0]
        self.assertEqual(lifetime['incarnation'], 'a1')
        self.assertEqual(lifetime['destructionCallbackCount'], 1)
        self.assertEqual(lifetime['callbackOffsetsFromEventSeconds'], [0.25])

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

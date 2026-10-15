"""Offline acceptance-harness checks; no native process, transport or UI starts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import native_identity_resident_acceptance as acceptance


class CleanupAcceptanceTests(unittest.TestCase):
    def exercise(self, *, close_error=None, reap_error=None, status='awaiting_cleanup'):
        events = []
        report = dict(status=status, records=[])
        if status == 'failed':
            report['failure'] = 'AssertionError: original acceptance failure'

        class Session:
            def close(self):
                events.append(('close', report['status']))
                if close_error:
                    raise close_error

        class Fixture:
            def close(self):
                events.append(('reap', report['status']))
                if reap_error:
                    raise reap_error
                return [dict(pid=i, reaped=True) for i in (1, 2, 3)]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'acceptance.json'

            def checkpoint(kind):
                report['records'].append(dict(kind=kind))
                path.write_text(json.dumps(report))

            caught = None
            try:
                acceptance.finish(report, Session(), Fixture(), checkpoint)
            except BaseException as error:
                caught = error
            return json.loads(path.read_text()), events, caught

    def test_failed_session_close_persists_failure_and_reaps_all_children(self):
        error = RuntimeError('claim release failed')
        report, events, caught = self.exercise(close_error=error)
        self.assertIs(caught, error)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['sessionCloseFailure'], 'RuntimeError: claim release failed')
        self.assertNotIn('sessionCloseReturned', report)
        self.assertEqual([e[0] for e in events], ['close', 'reap'])
        self.assertTrue(all(r['reaped'] for r in report['cleanup']))
        self.assertEqual(len(report['cleanup']), 3)
        self.assertEqual(report['records'][-1], dict(kind='finished'))

    def test_complete_only_after_both_cleanup_steps_succeed(self):
        report, events, caught = self.exercise()
        self.assertIsNone(caught)
        self.assertEqual(events, [('close', 'awaiting_cleanup'), ('reap', 'awaiting_cleanup')])
        self.assertEqual(report['status'], 'complete')
        self.assertTrue(report['sessionCloseReturned'])

    def test_reap_failure_is_persisted_and_rethrown(self):
        error = TimeoutError('child did not exit')
        report, _, caught = self.exercise(reap_error=error)
        self.assertIs(caught, error)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['cleanupFailure'], 'TimeoutError: child did not exit')
        self.assertTrue(report['sessionCloseReturned'])

    def test_both_cleanup_failures_retained_and_first_rethrown(self):
        first = RuntimeError('close failed')
        report, _, caught = self.exercise(close_error=first, reap_error=RuntimeError('reap failed'))
        self.assertIs(caught, first)
        self.assertEqual(report['sessionCloseFailure'], 'RuntimeError: close failed')
        self.assertEqual(report['cleanupFailure'], 'RuntimeError: reap failed')
        self.assertEqual(report['status'], 'failed')

    def test_cleanup_cannot_promote_existing_acceptance_failure(self):
        report, _, caught = self.exercise(status='failed')
        self.assertIsNone(caught)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['failure'], 'AssertionError: original acceptance failure')


class NativeRouteAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.result = dict(operation='action', actualRoute='guest.user/macos.ax',
                           accepted=True, delivery='confirmed')
        owner = self

        class Transport:
            def call(self, request):
                owner.requests.append(deepcopy(request))
                return deepcopy(owner.result)

        self.session = acceptance.Session(Transport(), target='fixture', auto_observe=False, emit=lambda _: None)
        self.app = acceptance.App(self.session, 'fixture', 'Fixture')
        self.app.elements = {1: dict(reference='fresh-reference', actions=['AXPress'])}

    def test_current_press_uses_only_fresh_semantic_reference(self):
        result = acceptance.semantic_press(self.app, 1)
        acceptance.assert_native_action(result.raw)
        self.assertEqual(self.requests, [dict(operation='action', reference='fresh-reference', action='press')])

    def test_absent_axpress_refuses_before_dispatch_instead_of_click_fallback(self):
        for actions in ([], ['press'], ['AXShowMenu']):
            with self.subTest(actions=actions):
                self.app.elements[1]['actions'] = actions
                with self.assertRaisesRegex(AssertionError, 'export AXPress'):
                    acceptance.semantic_press(self.app, 1)
        self.assertEqual(self.requests, [])

    def test_coordinate_delivery_and_exact_effect_cannot_qualify_semantic_action(self):
        result = dict(self.result, operation='input.click')
        with self.assertRaisesRegex(AssertionError, 'non-semantic'):
            acceptance.assert_native_action(result)

    def test_other_route_cannot_qualify_even_when_operation_and_delivery_match(self):
        for route in ('guest.user/macos.cua', 'fixture', None):
            with self.subTest(route=route):
                with self.assertRaisesRegex(AssertionError, 'bypassed native AX'):
                    acceptance.assert_native_action(dict(self.result, actualRoute=route))

    def test_native_route_still_requires_acceptance_and_confirmed_delivery(self):
        for change in (dict(accepted=False), dict(delivery='refused'), dict(delivery='uncertain')):
            with self.subTest(change=change):
                with self.assertRaises(AssertionError):
                    acceptance.assert_native_action(dict(self.result, **change))


class ObservedWarmupTests(unittest.TestCase):
    unchanged = 'Fixture:\nNo change. Existing numbers remain valid.'

    def controls(self, sample=0):
        return {logical: dict(number=i, identity=f'native-{logical}', identityGeneration='window-1',
            incarnation=f'owned-{logical}', reference=f's{sample}:{logical}')
            for i, logical in enumerate(('a', 'b', 'c'), 1)}

    def exercise(self, presentations, *, max_attempts=20, timeout=5, mutate=None, read_seconds=0):
        self.events, self.observations, self.now = [], [], 0.0
        initial = self.controls()

        def checkpoint(kind, **values):
            self.events.append(dict(kind=kind, **values))

        def observe(name):
            index = len(self.observations)
            controls = self.controls(index + 1)
            if mutate:
                mutate(controls)
            rendered = presentations[index % len(presentations)]
            self.now += read_seconds
            # Match the production observe contract: retain before validation.
            self.observations.append(dict(name=name, controls=deepcopy(controls), rendered=rendered))
            return controls, rendered

        def sleep(seconds):
            self.now += seconds

        return acceptance.observed_warmup(observe, initial, checkpoint, max_attempts=max_attempts,
            timeout=timeout, clock=lambda: self.now, sleep=sleep)

    def test_native_chrome_can_settle_without_losing_owned_control_continuity(self):
        controls = self.exercise(['Fixture:\n+ [12] group', self.unchanged, self.unchanged])
        self.assertEqual([o['name'] for o in self.observations], ['warmup-1', 'warmup-2', 'warmup-3'])
        self.assertIn('+ [12] group', self.observations[0]['rendered'])
        self.assertEqual(controls['a']['reference'], 's3:a')
        self.assertEqual([e['consecutiveUnchanged'] for e in self.events if e['kind'] == 'warmupSample'], [0, 1, 2])
        self.assertEqual(self.events[-1]['kind'], 'warmupComplete')

    def test_change_resets_streak_and_success_requires_two_consecutive_unchanged_reads(self):
        self.exercise([self.unchanged, 'Fixture:\nchanged', self.unchanged, self.unchanged], max_attempts=4)
        self.assertEqual(len(self.observations), 4)
        self.assertEqual([e['consecutiveUnchanged'] for e in self.events if e['kind'] == 'warmupSample'], [1, 0, 1, 2])

    def test_never_settling_presentation_stops_at_attempt_limit(self):
        with self.assertRaisesRegex(AssertionError, 'attempt limit'):
            self.exercise(['Fixture:\nchanged'], max_attempts=3)
        self.assertEqual(len(self.observations), 3)
        self.assertNotIn('warmupComplete', [e['kind'] for e in self.events])

    def test_deadline_stops_reads_even_before_attempt_limit(self):
        with self.assertRaisesRegex(AssertionError, 'deadline'):
            self.exercise(['Fixture:\nchanged'], timeout=.25)
        self.assertEqual(len(self.observations), 2)
        self.assertLessEqual(self.now, .25)

    def test_read_finishing_after_deadline_cannot_qualify(self):
        with self.assertRaisesRegex(AssertionError, 'deadline'):
            self.exercise([self.unchanged], timeout=.25, read_seconds=.2)
        self.assertEqual(len(self.observations), 1)
        self.assertEqual(self.events[-1]['kind'], 'warmupSample')

    def test_missing_or_unstable_control_fails_even_if_presentation_says_unchanged(self):
        changes = [lambda controls: controls.pop('b')]
        for field in ('identity', 'number', 'identityGeneration', 'incarnation', 'reference'):
            value = 's0:a' if field == 'reference' else 'changed'
            changes.append(lambda controls, field=field, value=value: controls['a'].update({field: value}))
        for change in changes:
            with self.subTest(change=change):
                with self.assertRaises(AssertionError):
                    self.exercise([self.unchanged], mutate=change)
                self.assertEqual(len(self.observations), 1)
                self.assertNotIn('warmupComplete', [e['kind'] for e in self.events])

    def test_missing_initial_owned_control_refuses_before_warmup_reads(self):
        initial = self.controls(); del initial['c']
        with self.assertRaisesRegex(AssertionError, 'all owned fixture controls'):
            acceptance.observed_warmup(lambda _: self.fail('Unexpected read'), initial,
                                       lambda *args, **kwargs: self.fail('Unexpected checkpoint'))


class GeometricReorderTests(unittest.TestCase):
    def samples(self):
        order = ['a', 'inserted', 'b', 'c']

        def sample(keys, snapshot):
            return {logical: dict(number=order.index(logical) + 1, identity=f'ax-{logical}',
                identityGeneration='window', incarnation=f'fixture-{logical}', reference=f'{snapshot}:{logical}',
                bounds=dict(x=99, y=327 + 40 * index, width=222, height=34),
                oracleFrame=dict(x=100, y=408 - 40 * index, width=220, height=32))
                for index, logical in enumerate(keys)}

        return sample(order, 'before'), sample(list(reversed(order)), 'after')

    def test_actual_geometry_reversal_with_stable_identity_and_opposite_vertical_axes(self):
        before, after = self.samples()
        result = acceptance.assert_geometric_reorder(before, after)
        self.assertEqual(result['beforeOrder'], ['a', 'inserted', 'b', 'c'])
        self.assertEqual(result['afterOrder'], ['c', 'b', 'inserted', 'a'])
        self.assertEqual(result['verticalAxisOffset'], 768)
        self.assertEqual(result['nativeCentersAfter']['a'], (210, 464))

    def test_noop_or_oracle_order_only_change_cannot_qualify(self):
        before, after = self.samples()
        with self.assertRaisesRegex(AssertionError, 'did not reverse'):
            acceptance.assert_geometric_reorder(before, before)
        for fields in (('bounds',), ('oracleFrame',), ('bounds', 'oracleFrame')):
            broken = deepcopy(after)
            for logical in broken:
                for field in fields:
                    broken[logical][field] = before[logical][field]
            with self.subTest(fields=fields), self.assertRaisesRegex(AssertionError, 'Geometry disagrees'):
                acceptance.assert_geometric_reorder(before, broken)

    def test_malformed_empty_nonfinite_or_ambiguous_geometry_refuses(self):
        before, after = self.samples()
        for field in ('bounds', 'oracleFrame'):
            for malformed in (None, {}, dict(x=0, y=0, width=0, height=1),
                              dict(x=True, y=0, width=1, height=1),
                              dict(x=0, y=float('nan'), width=1, height=1),
                              dict(x=0, y=0, width=1, height=float('inf')),
                              dict(x=1.7e308, y=0, width=1.7e308, height=1)):
                broken = deepcopy(after); broken['a'][field] = malformed
                with self.subTest(field=field, malformed=malformed), self.assertRaises(AssertionError):
                    acceptance.assert_geometric_reorder(before, broken)
            broken = deepcopy(after); broken['a'][field] = deepcopy(broken['inserted'][field])
            with self.subTest(field=field), self.assertRaises(AssertionError):
                acceptance.assert_geometric_reorder(before, broken)

    def test_inconsistent_native_oracle_centers_and_changed_control_authority_refuse(self):
        before, after = self.samples()
        for field, component in (('bounds', 'x'), ('bounds', 'y'), ('oracleFrame', 'x'), ('oracleFrame', 'y')):
            broken = deepcopy(after); broken['a'][field][component] += 5
            with self.subTest(field=field, component=component), self.assertRaisesRegex(AssertionError, 'centers disagree'):
                acceptance.assert_geometric_reorder(before, broken)
        for field in ('identity', 'number', 'identityGeneration', 'incarnation', 'reference'):
            broken = deepcopy(after)
            broken['a'][field] = before['a'][field] if field == 'reference' else 'different'
            with self.subTest(field=field), self.assertRaises(AssertionError):
                acceptance.assert_geometric_reorder(before, broken)
        broken = deepcopy(after); del broken['b']
        with self.assertRaisesRegex(AssertionError, 'control set changed'):
            acceptance.assert_geometric_reorder(before, broken)

    def test_refreshed_app_bounds_must_match_the_exact_current_native_reference(self):
        element = dict(reference='s2:a', identifier='slot-a', bounds=dict(x=1, y=2, width=3, height=4))
        self.assertEqual(acceptance.refreshed_native_bounds(element, [deepcopy(element)]), element['bounds'])
        stale = deepcopy(element); stale['bounds']['y'] = 1
        with self.assertRaisesRegex(AssertionError, 'stale native bounds'):
            acceptance.refreshed_native_bounds(stale, [element])
        for raw in ([], [dict(element, reference='s1:a')], [element, element], [dict(element, identifier='slot-b')]):
            with self.subTest(raw=raw), self.assertRaises(AssertionError):
                acceptance.refreshed_native_bounds(element, raw)

    def test_semantic_no_change_still_refreshes_app_bounds_from_native_snapshot(self):
        before, after = self.samples()
        # AX enumeration is unchanged while owned screen geometry reverses.
        enumeration = ['a', 'b', 'c', 'inserted']
        snapshots = [dict(accepted=True, generation='runtime', actualRoute='guest.user/macos.ax',
            data=dict(elementIdentityGeneration='window', elements=[
                dict(reference=sample[k]['reference'], identifier=f'slot-{k}', elementIdentity=sample[k]['identity'],
                     role='AXButton', label='Identical', depth=0, bounds=sample[k]['bounds'])
                for k in enumeration])) for sample in (before, after)]

        class Transport:
            def call(self, _):
                return deepcopy(snapshots.pop(0))

        session = acceptance.Session(Transport(), target='fixture', emit=lambda _: None, auto_observe=False)
        app = acceptance.App(session, 'fixture', 'Fixture')
        app.tree()
        previous = deepcopy(app.elements)
        self.assertIn('No change', app.tree())
        self.assertEqual(app.elements.keys(), previous.keys())
        for number, element in app.elements.items():
            self.assertEqual(element['elementIdentity'], previous[number]['elementIdentity'])
            self.assertNotEqual(element['reference'], previous[number]['reference'])
            self.assertNotEqual(element['bounds'], previous[number]['bounds'])
            acceptance.refreshed_native_bounds(element, app.last_observation['data']['elements'])


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Guest-only production acceptance using the existing owned AppKit fixture.

Not run by offline unit discovery. Controller doctor/claim, credential handoff,
guest deployment and workspace disposal remain the coordinator's responsibility.
This acquires its own guest-local retained claim/admission/audit connection.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'client'))
from agent_session import App, Session, SessionError, StaleElement
from agent_session_transport import connect


def require_axpress(element):
    assert 'AXPress' in element.get('actions', []), 'Native control must export AXPress'


def semantic_press(app, number):
    require_axpress(app.elements[number])
    # Explicit semantic dispatch: App.press may fall back to coordinates.
    return app.action(number, 'press', observe=False)


def assert_native_action(result):
    assert result.get('operation') == 'action', 'Current action used a non-semantic operation'
    assert result.get('actualRoute') == 'guest.user/macos.ax', 'Current action bypassed native AX'
    assert result.get('accepted') is True and result.get('delivery') == 'confirmed'


def frame_center(frame):
    assert isinstance(frame, dict), 'Missing geometry'
    assert all(type(frame.get(k)) in (int, float) and math.isfinite(frame[k])
               for k in ('x', 'y', 'width', 'height')), 'Nonfinite or malformed geometry'
    assert frame['width'] > 0 and frame['height'] > 0, 'Empty geometry'
    center = (frame['x'] + frame['width'] / 2, frame['y'] + frame['height'] / 2)
    assert all(math.isfinite(v) for v in center), 'Nonfinite geometry center'
    return center


def refreshed_native_bounds(element, native_elements):
    matches = [e for e in native_elements if e.get('reference') == element['reference']]
    assert len(matches) == 1, 'Missing or ambiguous native bounds source'
    native = matches[0]
    assert native.get('identifier') == element.get('identifier'), 'Native bounds source slot differs'
    frame_center(native.get('bounds'))
    assert element.get('bounds') == native['bounds'], 'App.elements retained stale native bounds'
    return deepcopy(native['bounds'])


def assert_geometric_reorder(before, after, *, tolerance=1.0):
    """Join fixture screen centers to AX centers with opposite vertical axes.

    AX child enumeration and compact semantic rows may remain unchanged. This
    proves only the fixture's geometric permutation, not complete pixel state.
    """
    assert len(before) >= 2 and before.keys() == after.keys(), 'Reorder control set changed'
    before_order, after_order = list(before), list(after)
    assert after_order == list(reversed(before_order)), 'Fixture oracle order did not reverse'
    native_centers, oracle_centers = [], []
    for controls in (before, after):
        native = {k: frame_center(v.get('bounds')) for k, v in controls.items()}
        oracle = {k: frame_center(v.get('oracleFrame')) for k, v in controls.items()}
        # The owned fixture is a vertical stack: native top-left Y grows down;
        # AppKit screen Y grows up. Reject ties instead of inventing an order.
        for centers, reverse in ((native, False), (oracle, True)):
            ordered = sorted(centers, key=lambda k: centers[k][1], reverse=reverse)
            assert ordered == list(controls), 'Geometry disagrees with fixture oracle order'
            assert all(abs(centers[a][1] - centers[b][1]) > 2 * tolerance
                       for a, b in zip(ordered, ordered[1:])), 'Ambiguous vertical geometry'
        native_centers.append(native); oracle_centers.append(oracle)
    first = before_order[0]
    offset = native_centers[0][first][1] + oracle_centers[0][first][1]
    for native, oracle in zip(native_centers, oracle_centers):
        for logical in before:
            assert abs(native[logical][0] - oracle[logical][0]) <= tolerance, 'Native/oracle X centers disagree'
            assert abs(native[logical][1] + oracle[logical][1] - offset) <= tolerance, 'Native/oracle Y centers disagree'
    for field in ('identity', 'number', 'identityGeneration', 'incarnation'):
        assert all(before[k][field] == after[k][field] for k in before), f'Reorder changed {field}'
    assert all(before[k]['reference'] != after[k]['reference'] for k in before), 'Reorder action refs did not refresh'
    assert any(abs(native_centers[0][k][1] - native_centers[1][k][1]) > tolerance for k in before), 'Native geometry did not reorder'
    assert any(abs(oracle_centers[0][k][1] - oracle_centers[1][k][1]) > tolerance for k in before), 'Oracle geometry did not reorder'
    return dict(beforeOrder=before_order, afterOrder=after_order,
                nativeCentersBefore=native_centers[0], nativeCentersAfter=native_centers[1],
                oracleCentersBefore=oracle_centers[0], oracleCentersAfter=oracle_centers[1],
                verticalAxisOffset=offset, centerTolerance=tolerance)


def observed_warmup(observe, initial, checkpoint, *, timeout=5.0, max_attempts=20,
                    clock=time.monotonic, sleep=time.sleep):
    """Await two unchanged samples, preserving every read and control identity."""
    assert timeout > 0 and max_attempts >= 2
    assert set(initial) == {'a', 'b', 'c'}, 'Warmup requires all owned fixture controls'
    baseline = deepcopy(initial)
    previous = initial
    start = clock()
    deadline = start + timeout
    consecutive = 0
    checkpoint('warmupStarted', timeoutSeconds=timeout, maxAttempts=max_attempts,
               requiredConsecutiveUnchanged=2)
    for attempt in range(1, max_attempts + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            raise AssertionError('Warmup deadline reached before stable presentation')
        sleep(min(.1, remaining))
        if clock() >= deadline:
            raise AssertionError('Warmup deadline reached before stable presentation')
        # observe() checkpoints raw/oracle/rendered evidence before validating it.
        controls, rendered = observe(f'warmup-{attempt}')
        assert controls.keys() == baseline.keys(), 'Owned fixture controls changed during warmup'
        for logical in baseline:
            for field in ('identity', 'number', 'identityGeneration', 'incarnation'):
                assert controls[logical][field] == baseline[logical][field], f'Warmup {logical} {field} changed'
            assert controls[logical]['reference'] != previous[logical]['reference'], 'Warmup action ref was not refreshed'
        unchanged = 'No change. Existing numbers remain valid.' in rendered.splitlines()
        consecutive = consecutive + 1 if unchanged else 0
        elapsed = clock() - start
        checkpoint('warmupSample', attempt=attempt, unchanged=unchanged,
                   consecutiveUnchanged=consecutive, elapsedSeconds=elapsed)
        if clock() >= deadline:
            raise AssertionError('Warmup deadline reached before stable presentation')
        if consecutive == 2:
            checkpoint('warmupComplete', attempts=attempt, elapsedSeconds=elapsed)
            return controls
        previous = controls
    raise AssertionError('Warmup attempt limit reached before stable presentation')


def finish(report, session, fixture, checkpoint):
    """Persist cleanup failures, reap children even if close fails, then rethrow."""
    errors = []
    for key, cleanup in (
        ('sessionCloseFailure', session.close if session else None),
        ('cleanupFailure', fixture.close if fixture else None),
    ):
        try:
            value = cleanup() if cleanup else None
            if key == 'sessionCloseFailure' and session:
                report['sessionCloseReturned'] = True
            elif key == 'cleanupFailure':
                report['cleanup'] = value if fixture else []
        except BaseException as error:
            report.update(status='failed')
            report[key] = f'{type(error).__name__}: {error}'
            errors.append(error)
    if report['status'] == 'awaiting_cleanup':
        report['status'] = 'complete'
    checkpoint('finished')
    if errors:
        raise errors[0]


class Fixture:
    def __init__(self, app: Path, output: Path):
        self.app, self.output = app, output
        self.nonce = str(uuid.uuid4())
        self.children = []
        self.process = None
        self.root = None
        self.epoch = None
        self.epochs = {}
        self.manifest = json.loads((app.parent / 'build.json').read_text())
        self.binary = app / 'Contents/MacOS/IdentityFixture'
        expected = self.manifest['binary_sha256']['IdentityFixture.app/Contents/MacOS/IdentityFixture']
        if hashlib.sha256(self.binary.read_bytes()).hexdigest() != expected:
            raise ValueError('Owned fixture binary does not match build manifest')

    def state(self):
        value = json.loads((self.root / 'state.json').read_text())
        assert value['pid'] == self.process.pid and value['runNonce'] == self.nonce, 'Wrong fixture process'
        assert self.epoch is None or self.epoch == value['processIncarnation'], 'Process oracle changed unexpectedly'
        return value

    def wait(self, predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = self.state()
            except (FileNotFoundError, json.JSONDecodeError):
                value = None
            if value is not None and predicate(value):
                return value
            time.sleep(.02)
        raise AssertionError('Owned fixture oracle deadline')

    def start(self):
        self.root = self.output / f'process-{len(self.children) + 1}'
        self.root.mkdir(mode=0o700)
        self.epoch = None
        with (self.root / 'fixture.log').open('wb') as log:
            self.process = subprocess.Popen([str(self.binary), '--disposable-guest', '--root',
                str(self.root), '--run-nonce', self.nonce], stdout=log, stderr=log)
        self.children.append(self.process)
        value = self.wait(lambda _: True)
        self.epoch = value['processIncarnation']
        self.epochs[self.process] = self.epoch

    def command(self, operation, **values):
        id = uuid.uuid4().hex
        temporary = self.root / 'command.tmp'
        temporary.write_text(json.dumps(dict(id=id, operation=operation, runNonce=self.nonce, **values)))
        temporary.replace(self.root / 'command.json')
        state = self.wait(lambda s: s['lastCommand'] == id)
        assert not state.get('commandError'), state.get('commandError')
        return state

    def restart(self):
        self.command('quit')
        self.process.wait(timeout=5)
        self.start()

    def close(self):
        receipts = []
        for process in self.children:
            forced = False
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                forced = True; process.kill(); process.wait(timeout=3)
            receipts.append(dict(pid=process.pid, processIncarnation=self.epochs.get(process),
                                 reaped=process.poll() is not None, status=process.returncode, forced=forced))
        return receipts


def run(options):
    assert options.output.is_absolute() and options.fixture.is_absolute(), 'Absolute paths required'
    options.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    report = dict(schema='machine-control/native-identity-resident-acceptance/v1', status='started', records=[])
    fixture = None
    session = None

    def checkpoint(kind, **values):
        report['records'].append(dict(kind=kind, **values))
        temporary = options.output / 'acceptance.tmp'
        temporary.write_text(json.dumps(report, indent=2, sort_keys=True))
        temporary.replace(options.output / 'acceptance.json')

    try:
        fixture = Fixture(options.fixture, options.output)
        report['fixtureBuild'] = fixture.manifest
        transport = connect(options.target, reason='Qualify native observation identity and fresh action membership',
                            claimant_authority=options.claimant_authority, claimant_id=options.claimant_id)
        session = Session(transport, target=options.target, emit=lambda _: None, auto_observe=False)
        fixture.start()
        app = App(session, str(fixture.process.pid), 'Native Identity Fixture')

        def observe(name):
            oracle = fixture.command('barrier')
            rendered = app.tree()
            raw = deepcopy(app.last_observation)
            checkpoint('observation', scenario=name, oracle=oracle, raw=raw, rendered=rendered)
            assert raw['actualRoute'] == 'guest.user/macos.ax'
            assert raw['data']['application']['processId'] == fixture.process.pid
            assert raw['data']['observationComplete'], raw['data'].get('observationIncompleteReason')
            assert raw['data']['elementIdentityGeneration']
            assert raw['data']['elementIdentityLifetime'] == 'consecutive_qualified_observations'
            assert raw['data']['actionReferenceLifetime'] == 'latest_snapshot'
            controls = {}
            for item in oracle['items']:
                assert item['logical'] not in controls, 'Duplicate fixture oracle slot'
                matches = [(n, e) for n, e in app.elements.items() if e.get('identifier') == item['identifier']]
                assert len(matches) == 1, 'Exact oracle slot join missing or ambiguous'
                n, element = matches[0]
                assert element.get('elementIdentity'), 'Native identity was not exported'
                controls[item['logical']] = dict(number=n, identity=element['elementIdentity'],
                    reference=element['reference'], incarnation=item['incarnation'],
                    identityGeneration=raw['data']['elementIdentityGeneration'],
                    bounds=refreshed_native_bounds(element, raw['data']['elements']),
                    oracleFrame=deepcopy(item['frame']))
            return controls, rendered

        def assert_scope_reset(previous, current):
            for logical in previous.keys() & current.keys():
                assert current[logical]['identityGeneration'] != previous[logical]['identityGeneration']
                assert current[logical]['identity'] != previous[logical]['identity']
                assert current[logical]['number'] != previous[logical]['number']

        def stale(reference, name):
            before = fixture.command('barrier')
            try:
                result = session.call(dict(operation='action', provider='macos-native', reference=reference, action='press'))
            except SessionError as error:
                result = error.result
            after = fixture.command('barrier')
            checkpoint('staleAction', scenario=name, result=result, before=before, after=after)
            assert result and result['accepted'] is False and result['errorCode'] == 'stale_reference'
            assert result['delivery'] == 'refused', 'Refusal must be before dispatch'
            assert before['effects'] == after['effects'], 'Retired or current control received a stale effect'

        def press(control, name):
            before = fixture.command('barrier')
            result = semantic_press(app, control['number'])
            after = fixture.command('barrier')
            expected = dict(before['effects'])
            expected[control['incarnation']] = expected.get(control['incarnation'], 0) + 1
            checkpoint('currentAction', scenario=name, result=result.raw, before=before, after=after)
            assert_native_action(result.raw)
            assert after['effects'] == expected

        controls, _ = observe('initial')
        controls = observed_warmup(observe, controls, checkpoint)
        for index in range(10):
            previous = controls
            controls, rendered = observe(f'unchanged-{index}')
            assert 'No change' in rendered
            for logical in controls:
                assert controls[logical]['identity'] == previous[logical]['identity']
                assert controls[logical]['number'] == previous[logical]['number']
                assert controls[logical]['reference'] != previous[logical]['reference']
            stale(previous['a']['reference'], 'previous-snapshot-ref')
        press(controls['a'], 'unchanged-current')
        for operation in ('insert', 'reorder'):
            previous = controls
            fixture.command(operation)
            controls, rendered = observe(operation)
            if operation == 'insert':
                assert 'No change' not in rendered
            else:
                geometry = assert_geometric_reorder(previous, controls)
                checkpoint('reorderGeometry', **geometry)
            for logical in previous:
                assert controls[logical]['identity'] == previous[logical]['identity']
                assert controls[logical]['number'] == previous[logical]['number']
        for index in range(5):
            previous = controls
            fixture.command('replace', logical='a')
            controls, _ = observe(f'replace-{index}')
            assert controls['a']['identity'] != previous['a']['identity']
            for logical in controls.keys() - {'a'}:
                assert controls[logical]['identity'] == previous[logical]['identity']
            stale(previous['a']['reference'], 'replaced-snapshot-ref')
            press(controls['a'], 'replacement-current')
        # Exercise the leaf membership guard before a newer snapshot can expire
        # the reference. Keep this separate from observation continuity checks.
        previous = controls
        fixture.command('replace', logical='a')
        stale(previous['a']['reference'], 'replacement-before-next-snapshot')
        controls, _ = observe('after-replacement-refusal')
        press(controls['a'], 'immediate-replacement-current')
        previous = controls
        fixture.command('remove', logical='b')
        stale(previous['b']['reference'], 'removed-before-next-snapshot')
        controls, _ = observe('removal')
        assert 'b' not in controls
        old = controls['a']
        fixture.command('recreateWindow')
        stale(old['reference'], 'retired-window-control-before-next-snapshot')
        controls, _ = observe('window-recreation')
        assert controls['a']['identity'] != old['identity']
        press(controls['a'], 'window-current')
        # No refusal before these reads: automatic scope reset must stand on
        # its own rather than relying on stale() clearing continuity.
        previous = controls
        fixture.command('recreateWindow')
        controls, _ = observe('window-recreation-observation-first')
        assert_scope_reset(previous, controls)
        press(controls['a'], 'window-observation-first-current')
        old = controls['a']
        fixture.restart()
        app.target = str(fixture.process.pid)
        stale(old['reference'], 'process-exit-before-next-snapshot')
        controls, _ = observe('process-recreation')
        assert controls['a']['identity'] != old['identity']
        press(controls['a'], 'process-current')
        previous = controls
        fixture.restart()
        app.target = str(fixture.process.pid)
        controls, _ = observe('process-recreation-observation-first')
        assert_scope_reset(previous, controls)
        press(controls['a'], 'process-observation-first-current')
        for budget in (dict(maxDepth=0), dict(maxElements=1)):
            old = controls['a']
            request = dict(operation='snapshot', provider='macos-native', target=app.target,
                           maxDepth=30, maxElements=400, projection='full')
            request.update(budget)
            raw = session.call(request)
            checkpoint('incompleteObservation', budget=budget, raw=raw)
            assert raw['data']['truncated'] and not raw['data'].get('elementIdentityGeneration')
            assert raw['data']['elementIdentityLifetime'] == 'unavailable'
            assert raw['data']['actionReferenceLifetime'] == 'latest_snapshot'
            assert all(not e.get('elementIdentity') for e in raw['data']['elements'])
            stale(old['reference'], 'reference-before-incomplete-read')
            controls, _ = observe('after-incomplete')
            assert controls['a']['identity'] != old['identity']
        # A partial observation must not make an independently provable current
        # control unusable merely because later siblings were not traversed.
        full = app.last_observation['data']['elements']
        slot_ids = {i['identifier']: i['incarnation'] for i in fixture.state()['items']}
        index, target = next((i, e) for i, e in enumerate(full) if e.get('identifier') in slot_ids)
        assert index + 1 < len(full), 'Fixture must have a later sibling for truncation'
        raw = session.call(dict(operation='snapshot', provider='macos-native', target=app.target,
                                projection='full', maxDepth=30, maxElements=index + 1))
        assert raw['data']['truncated'] and not raw['data'].get('elementIdentityGeneration')
        partial = next(e for e in raw['data']['elements'] if e.get('identifier') == target['identifier'])
        require_axpress(partial)
        before = fixture.command('barrier')
        result = session.call(dict(operation='action', provider='macos-native', reference=partial['reference'], action='press'))
        after = fixture.command('barrier')
        expected = dict(before['effects']); id = slot_ids[target['identifier']]
        expected[id] = expected.get(id, 0) + 1
        checkpoint('partialObservationAction', raw=raw, result=result, before=before, after=after)
        assert_native_action(result)
        assert after['effects'] == expected
        # Incomplete reads cannot resurrect the number used before them.
        assert old['number'] not in app.elements
        try:
            app.press(old['number'], observe=False)
            raise AssertionError('Removed number dispatched')
        except StaleElement:
            pass
        report['status'] = 'awaiting_cleanup'
    except BaseException as error:
        report.update(status='failed', failure=f'{type(error).__name__}: {error}')
        raise
    finally:
        finish(report, session, fixture, checkpoint)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-guest', action='store_true', required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=['host'], default='host')
    parser.add_argument('--claimant-authority')
    parser.add_argument('--claimant-id')
    run(parser.parse_args())

#!/usr/bin/env python3
"""Qualify Python activation and capture against the owned native fixture.

Run only in a disposable guest prepared by prepare.py. Controller lifecycle,
claims, credential handoff and disposal remain the caller's responsibility.
This uses the supported candidate's claim/admission/audit path; fixture commands
simulate independent application changes and are not agent task actions.
"""
import argparse
import json
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'client'))
from agent_session import Session, StaleElement
from agent_session_transport import connect

APP = 'org.machine-control.efficiency.target'


def state(root, kind='target'):
    return json.loads((root / kind / 'state.json').read_text())


def wait_state(root, predicate):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        value = state(root)
        if predicate(value):
            return value
        time.sleep(.02)
    raise AssertionError('Independent fixture effect did not arrive')


def command(root, operation, **values):
    identifier = uuid.uuid4().hex
    temporary = root / 'target' / 'command.tmp'
    temporary.write_text(json.dumps({'id': identifier, 'operation': operation, **values}))
    temporary.replace(root / 'target' / 'command.json')
    return wait_state(root, lambda value: value['lastCommand'] == identifier)


def element(app, *, label=None, role=None):
    matches = [e for e in app.elements.values()
               if (label is None or e.get('label') == label) and (role is None or e.get('role') == role)]
    assert len(matches) == 1, 'Fixture control must resolve exactly'
    return matches[0]


def point(capture, element):
    """Known fixture geometry grounds the input; the captured PNG supplies scale."""
    window = capture.raw['data']['window']['bounds']
    bounds = element['bounds']
    return ((bounds['x'] + bounds['width'] / 2 - window['x']) * capture.width / window['width'],
            (bounds['y'] + bounds['height'] / 2 - window['y']) * capture.height / window['height'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--target', default='host')
    parser.add_argument('--disposable-guest', action='store_true', required=True)
    options = parser.parse_args()
    root = options.root.resolve()
    before_sentinel = state(root, 'sentinel')
    command(root, 'reset')
    command(root, 'rows', count=100)
    images = []
    transport = connect(options.target, reason='Qualify capture-bound pointer input against owned fixtures')
    report = {}
    with Session(transport, target=options.target, emit=lambda value: None, emit_image=images.append) as mc:
        sentinel = mc.app('org.machine-control.efficiency.sentinel', observe=False)
        sentinel.activate(observe=False)
        background = wait_state(root, lambda value: value['frontPid'] == before_sentinel['pid'])
        app = mc.app(APP)
        assert state(root)['frontPid'] == background['frontPid'], 'Lookup implicitly changed foreground'
        report['lookupPreservesForeground'] = True
        old_capture = app.screenshot()
        before = state(root)
        activation = app.activate()
        activated = wait_state(root, lambda value: value['frontPid'] == value['pid'] and value['keyWindow'])
        assert activation.raw.get('focusConsequence') == 'target_application_activated'
        assert activated['cursor'] == before['cursor']
        report['activationEffect'] = True
        report['activationCursorUnchanged'] = True
        attempts = mc.action_attempts
        try:
            old_capture.click(old_capture.width / 2, old_capture.height / 2)
            raise AssertionError('Capture reused after activation')
        except StaleElement:
            assert mc.action_attempts == attempts
            report['activationInvalidatesCapture'] = True

        capture = app.screenshot()
        x, y = point(capture, element(app, label='Increment', role='AXButton'))
        before = state(root)
        capture.click(x, y)
        clicked = wait_state(root, lambda value: value['revision'] == before['revision'] + 1)
        assert clicked['counters'].get('buttonMouseDown', 0) > before['counters'].get('buttonMouseDown', 0)
        assert clicked['counters'].get('accessibilityPress', 0) == before['counters'].get('accessibilityPress', 0)
        report['captureClickEffect'] = True
        try:
            capture.click(x, y)
            raise AssertionError('Capture reused after an action')
        except StaleElement:
            report['actionInvalidatesCapture'] = True

        app.tree(full=True)
        capture = app.screenshot()
        x, y = point(capture, element(app, role='AXScrollArea'))
        before = state(root)
        maximum = before['scrollDocumentHeight'] - before['scrollViewportHeight']
        assert maximum > 0, 'Fixture must have scrollable content'
        direction = 'up' if before['scrollY'] < maximum / 2 else 'down'
        capture.scroll(x, y, direction, pixels=180)
        scrolled = wait_state(root, lambda value: abs(value['scrollY'] - before['scrollY']) > 1)
        report['captureScrollEffect'] = True
        report['scrollDelta'] = scrolled['scrollY'] - before['scrollY']

        capture = app.screenshot()
        attempts = mc.action_attempts
        command(root, 'move', x=100, y=130)
        try:
            capture.click(capture.width / 2, capture.height / 2)
            raise AssertionError('Moved capture was accepted')
        except StaleElement:
            assert mc.action_attempts == attempts
            report['externalMoveRefusedBeforeInput'] = True
        after_sentinel = state(root, 'sentinel')
        assert after_sentinel['text'] == before_sentinel['text']
        assert after_sentinel['revision'] == before_sentinel['revision']
        report['sentinelContentUnchanged'] = True
        report['imageCount'] = len(images)
        report['imagePixels'] = [capture.width, capture.height]
        report['windowPoints'] = [capture.raw['data']['window']['bounds'][key] for key in ('width', 'height')]
    report['sessionClosed'] = mc.closed
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

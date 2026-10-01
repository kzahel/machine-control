#!/usr/bin/env python3
"""Exercise an installed signed candidate in a claimed dedicated Mac testbed.

Requires a separate, running appliance resident and the deployed AppKit
fixture. Drives approval only through native AX input from that resident.
The caller owns candidate installation, policy, power, and claim cleanup.
Never run this on a personal workstation.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time
import uuid

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--target', required=True)
p.add_argument('--claim', required=True)
p.add_argument('--candidate-app', required=True)
p.add_argument('--candidate-socket', required=True)
p.add_argument('--operator-app', help='Separate guest appliance app; defaults to installed native app')
p.add_argument('--operator-socket', help='Separate appliance socket; required with --operator-app')
args = p.parse_args()
if bool(args.operator_app) != bool(args.operator_socket):
    p.error('--operator-app and --operator-socket must be supplied together')
mc = [str(Path(__file__).resolve().parents[2] / 'bin/machine-control'),
      '--target', args.target, '--claim', args.claim]
binary = args.candidate_app + '/Contents/MacOS/macui'
fixture = 'org.machine-control.fixture'


def call(*argv):
    return subprocess.check_output(mc + list(argv), text=True, timeout=60)


def candidate(request):
    return json.loads(call('os', '--', binary, 'request', args.candidate_socket,
                           json.dumps(request)))


def base(request):
    if args.operator_app:
        script = ' '.join(map(shlex.quote, [args.operator_app + '/Contents/MacOS/macui',
            'request', args.operator_socket, json.dumps(request)]))
    else:
        script = ('"$HOME/Applications/Machine Control.app/Contents/MacOS/macui" '
                  'request "$HOME/Library/Application Support/MachineControl/control.sock" '
                  + shlex.quote(json.dumps(request)))
    return json.loads(call('os', '--', '/bin/zsh', '-c', script))


def accepted(result):
    assert result['accepted'], result.get('errorCode', result)
    assert result['hostInterference'] == 'none'
    return result.get('data', {})


def press(pid, label, role='AXButton'):
    # WebKit publishes its AX tree asynchronously after activation and
    # React updates. Poll read-only state; never repeat an uncertain press.
    for _ in range(5):
        elements = accepted(base(dict(operation='snapshot', target=str(pid),
            query=label, projection='compact', maxDepth=30, maxElements=500)))['elements']
        matches = [e for e in elements if e['label'] == label and e['role'] == role]
        if matches:
            break
        time.sleep(0.2)
    assert len(matches) == 1, (label, len(matches))
    accepted(base(dict(operation='action', reference=matches[0]['reference'], action='press')))


def tray(pid, label):
    elements = accepted(base(dict(operation='snapshot', target=str(pid),
        projection='compact', maxDepth=30, maxElements=600)))['elements']
    items = [e for e in elements if e['role'] == 'AXMenuBarItem'
             and e.get('bounds', {}).get('height', 0) > 0
             and 'AXPress' in e['actions']]
    assert len(items) == 1, ('tray', len(items))
    # NSStatusItem's AXPress acknowledges delivery without opening the menu.
    # Use native guest pointer input at its freshly observed bounds, then
    # require the menu item and the resulting page/state as effect evidence.
    bounds = items[0]['bounds']
    accepted(base(dict(operation='input.click', target=str(pid),
        x=round(bounds['x'] + bounds['width'] / 2),
        y=round(bounds['y'] + bounds['height'] / 2),
        coordinateSpace='global_display_points')))
    press(pid, label, 'AXMenuItem')


def request(scopes):
    payload = dict(operation='grant.request', requestId=str(uuid.uuid4()),
        scopes=scopes, reason='Verify signed desktop candidate',
        durationSeconds=300, timeoutSeconds=120)
    child = subprocess.Popen(mc + ['os', '--', binary, 'request', args.candidate_socket,
        json.dumps(payload)], stdout=subprocess.PIPE, text=True)
    try:
        for _ in range(10):
            if candidate(dict(operation='grant.status'))['data']['pendingRequest']:
                return child
            time.sleep(0.2)
        raise AssertionError('Approval did not appear')
    except BaseException:
        child.terminate()
        child.wait(timeout=10)
        raise


def finish(child):
    stdout, _ = child.communicate(timeout=30)
    return json.loads(stdout)


def oracle():
    return json.loads(call('testbed', '--', 'fixture-state'))


pending = None
pid = accepted(candidate(dict(operation='status')))['processId']
assert accepted(base(dict(operation='status')))['deployment']['policy']['grantMode'] == 'standing'
assert accepted(candidate(dict(operation='grant.status')))['policy']['grantMode'] == 'approval'
accepted(base(dict(operation='application.activate', target=str(pid))))
try:
    accepted(candidate(dict(operation='grant.revoke')))
    assert candidate(dict(operation='snapshot', target=fixture))['errorCode'] == 'approval_required'
    assert candidate(dict(operation='grant.approve'))['errorCode'] == 'unsupported_operation'
    press(pid, 'Access')
    pending = request(['observe', 'control'])
    press(pid, 'Deny')
    assert finish(pending)['errorCode'] == 'approval_denied'
    pending = None

    pending = request(['observe', 'control'])
    press(pid, 'Control apps and input', 'AXCheckBox')
    press(pid, 'Allow access')
    assert accepted(finish(pending))['grant']['scopes'] == ['observe']
    pending = None
    accepted(candidate(dict(operation='snapshot', target=fixture)))
    assert not candidate(dict(operation='input.key', target=fixture, key='tab'))['accepted']
    press(pid, 'Stop access')

    press(pid, 'Enable access')
    assert candidate(dict(operation='input.key', target=str(pid), key='tab'))['errorCode'] == 'self_target_refused'
    assert candidate(dict(operation='authorization.begin'))['errorCode'] == 'operation_not_permitted_by_policy'
    before = oracle()['count']
    elements = accepted(candidate(dict(operation='snapshot', target=fixture,
        query='Increment', projection='compact')))['elements']
    reference = next(e['reference'] for e in elements
                     if e['role'] == 'AXButton' and e['label'] == 'Increment')
    accepted(candidate(dict(operation='action', reference=reference, action='press')))
    assert oracle()['count'] == before + 1

    pending = request(['browser'])
    assert candidate(dict(operation='input.key', target=fixture, key='tab'))['errorCode'] == 'approval_prompt_visible'
    press(pid, 'Deny')
    assert finish(pending)['errorCode'] == 'approval_denied'
    pending = None
    press(pid, 'Stop access')
    assert candidate(dict(operation='snapshot', target=fixture))['errorCode'] == 'approval_required'
    tray(pid, 'Settings…')
    # The setting-row button proves the menu navigated to the right page.
    for _ in range(10):
        elements = accepted(base(dict(operation='snapshot', target=str(pid),
            query='Check for updates', projection='compact', maxDepth=30,
            maxElements=500)))['elements']
        if any(e['label'] == 'Check for updates' and e['role'] == 'AXButton' for e in elements):
            break
        time.sleep(0.2)
    else:
        raise AssertionError('Settings tray command did not open Settings')
    tray(pid, 'Check for Updates…')
    for _ in range(110):
        elements = accepted(base(dict(operation='snapshot', target=str(pid),
            projection='compact', maxDepth=30, maxElements=600)))['elements']
        if any((e.get('label') or e.get('value')) == 'Up to date.' for e in elements):
            break
        time.sleep(0.2)
    else:
        raise AssertionError('Tray update check did not report up to date')
    tray(pid, 'Open Machine Control')
    press(pid, 'Enable access')
    tray(pid, 'Stop access')
    assert accepted(candidate(dict(operation='grant.status')))['grant'] is None
    print('Tray Settings, production update check, Open, and Stop passed')
    print('Visible denial, narrowed approval, fixture effect, self/protected refusal, prompt pause, and Stop passed')
finally:
    # A failed assertion must not leave an approval waiting or access armed.
    if candidate(dict(operation='grant.status'))['data']['pendingRequest']:
        press(pid, 'Deny')
    accepted(candidate(dict(operation='grant.revoke')))
    if pending is not None:
        if pending.poll() is None:
            pending.terminate()
        pending.wait(timeout=10)

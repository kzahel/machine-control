#!/usr/bin/env python3
"""Signed three-profile acceptance on a claimed dedicated Mac testbed.

Caller owns installation, workstation policy, TCC consent and restoration.
Keep the standing observer and deterministic AppKit fixture running. This
runner launches only the supplied candidate, uses native AX for approval,
and terminates its candidate in finally. Never use on a personal workstation.
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
p.add_argument('--candidate-client', required=True)
p.add_argument('--profile', choices=['personal', 'minimal', 'appliance'], required=True)
p.add_argument('--operator-app')
p.add_argument('--operator-socket')
a = p.parse_args()
if bool(a.operator_app) != bool(a.operator_socket):
    p.error('Observer app and socket must be supplied together')
mc = [str(Path(__file__).resolve().parents[2] / 'bin/machine-control'), '--target', a.target, '--claim', a.claim]
binary = a.candidate_app + '/Contents/MacOS/macui'
pid = None
pending = None
guest_claim = None
fixture = 'org.machine-control.fixture'


def call(*args):
    return subprocess.check_output(mc + list(args), text=True, timeout=60)


def shell(args):
    return call('os', '--', '/bin/zsh', '-c', args)


def request(value, packaged=False):
    if packaged:
        args = ['os', '--', '/usr/bin/env', 'MACHINE_CONTROL_HOST_SOCKET=' + a.candidate_socket,
                a.candidate_client, '--target', 'host', '--claim', guest_claim,
                'desktop', 'raw', json.dumps(value)]
    else:
        args = ['os', '--', binary, 'request', a.candidate_socket, json.dumps(value)]
    result = subprocess.run(mc + args, text=True, capture_output=True, timeout=60)
    assert result.returncode in (0, 1), result.stderr
    return json.loads(result.stdout)


def base(value):
    if a.operator_app:
        args = [a.operator_app + '/Contents/MacOS/macui', 'request', a.operator_socket, json.dumps(value)]
        return json.loads(call('os', '--', *args))
    return json.loads(shell('"$HOME/Applications/Machine Control.app/Contents/MacOS/macui" request '
        '"$HOME/Library/Application Support/MachineControl/control.sock" ' + shlex.quote(json.dumps(value))))


def accepted(value):
    assert value['accepted'], value
    assert value['hostInterference'] == 'none', value
    return value.get('data', {})


def wait(test, description):
    last = None
    for _ in range(25):
        try:
            last = test()
            if last:
                return last
        except (subprocess.CalledProcessError, json.JSONDecodeError, AssertionError) as error:
            last = str(error)
        time.sleep(0.2)
    raise AssertionError((description, last))


def status():
    return accepted(request(dict(operation='status')))


def elements(label=None):
    value = dict(operation='snapshot', target=str(pid), projection='compact', maxDepth=30, maxElements=600)
    if label:
        value['query'] = label
    return accepted(base(value))['elements']


def press(label, role='AXButton'):
    matches = wait(lambda: [e for e in elements(label) if e['label'] == label and e['role'] == role], label)
    assert len(matches) == 1, (label, len(matches))
    accepted(base(dict(operation='action', reference=matches[0]['reference'], action='press')))


def tray(label):
    items = [e for e in elements() if e['role'] == 'AXMenuBarItem'
             and e.get('bounds', {}).get('height', 0) > 0 and 'AXPress' in e['actions']]
    assert len(items) == 1, ('candidate tray', len(items))
    b = items[0]['bounds']
    accepted(base(dict(operation='input.click', target=str(pid),
        x=round(b['x'] + b['width'] / 2), y=round(b['y'] + b['height'] / 2), coordinateSpace='global_display_points')))
    press(label, 'AXMenuItem')


def settings():
    # Second launch must forward to the existing runtime, including appliance.
    shell(' '.join(map(shlex.quote, [binary, 'serve', a.candidate_socket, '--settings'])) + ' >/dev/null 2>&1')
    wait(lambda: status()['presentation']['settingsWebViews'] == 1, 'Settings opened')
    assert status()['processId'] == pid


def close_settings():
    accepted(base(dict(operation='window.close', target=str(pid))))
    wait(lambda: status()['presentation']['settingsWebViews'] == 0, 'Settings destroyed')
    assert status()['processId'] == pid


def approval(scopes):
    global pending
    value = dict(operation='grant.request', requestId=str(uuid.uuid4()), scopes=scopes,
        reason='Verify native runtime presentation', durationSeconds=300, timeoutSeconds=120)
    pending = subprocess.Popen(mc + ['os', '--', binary, 'request', a.candidate_socket, json.dumps(value)],
        stdout=subprocess.PIPE, text=True)
    wait(lambda: accepted(request(dict(operation='grant.status')))['pendingRequest'], 'native approval')


def decide(label):
    global pending
    press(label)
    output, _ = pending.communicate(timeout=30)
    pending = None
    return json.loads(output)


def preference(*args):
    return json.loads(call('os', '--', a.candidate_client, 'presentation', *args, '--socket', a.candidate_socket))


try:
    assert accepted(base(dict(operation='status')))['deployment']['policy']['grantMode'] == 'standing'
    preference('set', a.profile)
    log = str(Path(a.candidate_socket).parent / 'candidate.log')
    shell('nohup ' + ' '.join(map(shlex.quote, [binary, 'serve', a.candidate_socket]))
          + ' </dev/null >' + shlex.quote(log) + ' 2>&1 &')
    initial = wait(status, 'candidate started')
    pid = initial['processId']
    assert initial['deployment']['policy']['grantMode'] == 'approval', initial['deployment']
    assert initial['presentation']['profile'] == a.profile, initial['presentation']
    expected = 1 if a.profile == 'personal' else 0
    wait(lambda: status()['presentation']['settingsWebViews'] == expected, 'profile startup')
    if expected:
        close_settings()
    settings(); close_settings(); settings(); close_settings()

    # Approval works with no Settings WebView. Saving a profile during approval
    # defers its live application without dismissing or replacing the prompt.
    approval(['observe', 'control'])
    preference('set', 'minimal' if a.profile != 'minimal' else 'personal')
    assert status()['presentation']['profile'] == a.profile
    assert status()['presentation']['settingsWebViews'] == 0
    assert decide('Deny')['errorCode'] == 'approval_denied'
    preference('set', a.profile)
    wait(lambda: status()['presentation']['profile'] == a.profile, 'saved mode restored')
    approval(['observe', 'control'])
    assert accepted(decide('Allow View Only'))['grant']['scopes'] == ['observe']
    accepted(request(dict(operation='snapshot', target=fixture)))
    assert not request(dict(operation='input.key', target=fixture, key='tab'))['accepted']
    accepted(request(dict(operation='grant.revoke')))

    approval(['observe', 'control'])
    approved = accepted(decide('Allow'))['grant']
    assert request(dict(operation='input.key', target=str(pid), key='tab'))['errorCode'] == 'self_target_refused'
    assert request(dict(operation='authorization.begin'))['errorCode'] == 'operation_not_permitted_by_policy'
    before = json.loads(call('testbed', '--', 'fixture-state'))['count']
    snapshot = accepted(request(dict(operation='snapshot', target=fixture, query='Increment', projection='compact')))
    reference = next(e['reference'] for e in snapshot['elements'] if e['role'] == 'AXButton' and e['label'] == 'Increment')
    accepted(request(dict(operation='action', reference=reference, action='press')))
    assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 1

    acquired = json.loads(call('os', '--', a.candidate_client, '--target', 'host', 'claim', 'acquire',
        '--duration', '30m', '--claimant-authority', 'mc-conformance', '--claimant-id', 'presentation',
        '--reason', 'Verify packaged local and outside access'))
    guest_claim = acquired['data']['claim']['claimId']
    local = accepted(request(dict(operation='snapshot', target=fixture, query='Increment', projection='compact'), packaged=True))
    local_ref = next(e['reference'] for e in local['elements'] if e['role'] == 'AXButton' and e['label'] == 'Increment')
    accepted(request(dict(operation='action', reference=local_ref, action='press'), packaged=True))
    assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 2
    capture = accepted(request(dict(operation='capture', scope='window', target=fixture), packaged=True))
    assert call('os', '--', '/usr/bin/xxd', '-l', '8', '-p', capture['artifactPath']).strip() == '89504e470d0a1a0a'
    call('os', '--', '/bin/rm', '-f', capture['artifactPath'])

    # Supported reset is live, preserves authority, and never requires deleting
    # a special file. Settings itself survives a profile change.
    settings()
    preference('reset')
    wait(lambda: status()['presentation']['profile'] == 'personal', 'reset applied')
    assert accepted(request(dict(operation='grant.status')))['grant']['grantId'] == approved['grantId']
    assert status()['presentation']['settingsWebViews'] == 1
    close_settings()
    tray('Stop access')
    assert accepted(request(dict(operation='grant.status')))['grant'] is None
    assert request(dict(operation='snapshot', target=fixture))['errorCode'] == 'approval_required'
    settings()
    print(json.dumps({'schema':'machine-control-mac-presentation-acceptance/v1', 'profile':a.profile,
        'startup':True, 'lazySettings':True, 'singleInstanceRecovery':True, 'nativeApproval':True,
        'deferredPreference':True, 'outsideAndLocalEffects':True, 'capture':True, 'liveReset':True, 'stop':True}, sort_keys=True))
finally:
    if pending is not None:
        try:
            press('Deny')
        finally:
            if pending.poll() is None:
                pending.terminate()
            pending.wait(timeout=10)
    if pid is not None:
        try:
            request(dict(operation='grant.revoke'))
            accepted(base(dict(operation='application.terminate', target=str(pid))))
        except (subprocess.SubprocessError, AssertionError, OSError):
            call('os', '--', '/bin/kill', '-TERM', str(pid))
    if guest_claim is not None:
        call('os', '--', a.candidate_client, '--target', 'host', 'claim', 'release', guest_claim)

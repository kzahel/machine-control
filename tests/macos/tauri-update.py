#!/usr/bin/env python3
"""Exercise a signed installed update in a claimed dedicated Mac testbed.

Requires a separate standing-policy observer and the deployed AppKit fixture.
The caller authenticates and installs the sender, configures workstation policy,
claims the target, and restores application, policy, power, and claim afterward.
Never run this on a personal workstation. Legacy reopening is opt-in and is
reported separately from automatic relaunch acceptance.
"""
import argparse
import json
from pathlib import Path
import subprocess
import time

p = argparse.ArgumentParser(description=__doc__)
for name in ('target', 'claim', 'candidate-app', 'candidate-socket',
             'operator-app', 'operator-socket', 'initial-version', 'expected-version'):
    p.add_argument('--' + name, required=True)
p.add_argument('--legacy-reopen', action='store_true',
               help='Allow one native reopen for the known 0.3.3/0.3.4 sender defect')
p.add_argument('--capture-dir', type=Path, help='Private controller evidence directory')
p.add_argument('--verify-restart-before', action='store_true')
p.add_argument('--verify-restart-after', action='store_true')
p.add_argument('--candidate-client', help='Exact installed CLI path; requires --host-claim')
p.add_argument('--host-claim', help='Caller-owned guest-local target-use claim')
p.add_argument('--host-state', help='Optional isolated guest-local claim store')
args = p.parse_args()
if bool(args.candidate_client) != bool(args.host_claim):
    p.error('--candidate-client and --host-claim must be supplied together')
if args.host_state and not args.candidate_client:
    p.error('--host-state requires --candidate-client')
if args.legacy_reopen and args.initial_version not in ('0.3.3', '0.3.4'):
    p.error('Legacy reopening is limited to the affected published sender versions')
mc = [str(Path(__file__).resolve().parents[2] / 'bin/machine-control'),
      '--target', args.target, '--claim', args.claim]


def call(*argv):
    q = subprocess.run(mc + list(argv), capture_output=True, text=True, timeout=60)
    if q.returncode:
        raise RuntimeError('Target command failed')
    return q.stdout


def resident(app, socket, request):
    return json.loads(call('os', '--', app + '/Contents/MacOS/macui',
                           'request', socket, json.dumps(request)))


def candidate(request):
    if args.candidate_client:
        environment = ['MACHINE_CONTROL_HOST_SOCKET=' + args.candidate_socket]
        if args.host_state:
            environment.append('MACHINE_CONTROL_HOST_STATE_DIR=' + args.host_state)
        response = subprocess.run(mc + ['os', '--', '/usr/bin/env', *environment,
            args.candidate_client, '--target', 'host', '--claim', args.host_claim,
            'desktop', 'raw', json.dumps(request)], capture_output=True, text=True, timeout=60)
        if response.returncode not in (0, 1):
            raise RuntimeError('Installed CLI transport failed')
        try:
            value = json.loads(response.stdout)
        except ValueError as error:
            raise RuntimeError('Installed CLI unavailable during replacement') from error
        if value.get('schema') == 'machine-control-client-error/v0':
            raise RuntimeError('Installed CLI resident unavailable during replacement')
        return value
    return resident(args.candidate_app, args.candidate_socket, request)


def client_identity():
    identity = json.loads(call('os', '--', args.candidate_client, 'agent', 'identity'))
    assert identity['clientProtocol'] == 1 and identity['distribution'] == 'desktop'
    return identity


def observer(request):
    return resident(args.operator_app, args.operator_socket, request)


def accepted(result):
    assert result['accepted'], result.get('errorCode')
    assert result['hostInterference'] == 'none'
    return result.get('data', {})


def elements(pid, query=''):
    return accepted(observer(dict(operation='snapshot', target=str(pid),
        query=query, projection='compact', maxDepth=30, maxElements=600)))['elements']


def press(pid, label):
    for _ in range(10):
        matches = [e for e in elements(pid, label)
                   if e.get('label') == label and e['role'] == 'AXButton']
        if len(matches) == 1:
            break
        time.sleep(0.2)
    assert len(matches) == 1, (label, len(matches))
    assert matches[0]['enabled'], label
    accepted(observer(dict(operation='action', reference=matches[0]['reference'],
                           action='press')))


def version():
    return call('os', '--', '/usr/bin/defaults', 'read',
                args.candidate_app + '/Contents/Info', 'CFBundleShortVersionString').strip()


def verify_restart():
    before = candidate(dict(operation='status'))
    pid = accepted(before)['processId']
    accepted(observer(dict(operation='application.activate', target=str(pid))))
    press(pid, 'Access')
    press(pid, 'Enable access')
    assert accepted(candidate(dict(operation='grant.status')))['grant']
    press(pid, 'Permissions')
    press(pid, 'Restart')
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            after = candidate(dict(operation='status'))
            state = accepted(after)
            if state['processId'] != pid:
                break
        except RuntimeError:
            pass
        time.sleep(0.25)
    else:
        raise AssertionError('Permissions Restart did not relaunch')
    assert after['generation'] != before['generation']
    assert state['semanticState'] == 'ready' and state['captureState'] == 'ready'
    assert accepted(candidate(dict(operation='grant.status')))['grant'] is None


if args.verify_restart_before:
    verify_restart()


old = candidate(dict(operation='status'))
old_client = client_identity() if args.candidate_client else None
pid = accepted(old)['processId']
assert version() == args.initial_version
if old_client:
    assert old_client['version'] == args.initial_version
assert accepted(candidate(dict(operation='grant.status')))['grant'] is None
accepted(observer(dict(operation='application.activate', target=str(pid))))
press(pid, 'Access')
press(pid, 'Enable access')
assert accepted(candidate(dict(operation='grant.status')))['grant']
reference = next(e['reference'] for e in accepted(candidate(dict(operation='snapshot',
    target='org.machine-control.fixture', query='Increment', projection='compact')))['elements']
    if e['role'] == 'AXButton' and e['label'] == 'Increment')
press(pid, 'Settings')
press(pid, 'Check for updates')
deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    update = accepted(candidate(dict(operation='update.status')))['update']
    if update['phase'] == 'error':
        raise AssertionError('Native update discovery failed: ' + str(update['error']))
    snapshot = elements(pid)
    installs = [e for e in snapshot if e['role'] == 'AXButton'
                and e['label'] == 'Install and restart']
    if (update['phase'] == 'available'
            and update['availableVersion'] == args.expected_version
            and len(installs) == 1):
        break
    time.sleep(0.2)
else:
    raise AssertionError('Installed sender did not discover the expected signed update')
install = installs[0]
assert not install['enabled'], 'Update installation was enabled with active access'
print('PASS native discovery identifies the receiver and visible installation is disabled during active access', flush=True)
press(pid, 'Access')
press(pid, 'Stop access')
press(pid, 'Settings')
if args.capture_dir:
    args.capture_dir.mkdir(parents=True, exist_ok=True)
    capture = accepted(observer(dict(operation='capture', scope='window', target=str(pid))))
    with (args.capture_dir / 'update-available.png').open('wb') as image:
        subprocess.run(mc + ['os', '--', '/bin/cat', capture['artifactPath']],
                       stdout=image, check=True, timeout=60)
    call('os', '--', '/bin/rm', capture['artifactPath'])
press(pid, 'Install and restart')
deadline = time.monotonic() + 90
reopened = False
while time.monotonic() < deadline:
    try:
        new = candidate(dict(operation='status'))
        state = accepted(new)
        if state['processId'] != pid and version() == args.expected_version:
            break
    except RuntimeError:
        # A missing socket is expected briefly while the application relaunches.
        if args.legacy_reopen and not reopened and deadline - time.monotonic() < 65:
            assert version() == args.expected_version, 'Expected bundle was not installed'
            call('os', '--', '/usr/bin/open', args.candidate_app)
            reopened = True
    time.sleep(0.5)
else:
    raise AssertionError('Installed update did not relaunch the expected version')
assert new['generation'] != old['generation']
assert state['semanticState'] == 'ready' and state['captureState'] == 'ready'
assert accepted(candidate(dict(operation='grant.status')))['grant'] is None
if old_client:
    replacement_client = client_identity()
    assert replacement_client['version'] == args.expected_version
    assert replacement_client['version'] != old_client['version']
    print('PASS installed CLI identity replaced with the signed app and claim still authorizes native status', flush=True)
pid = state['processId']
accepted(observer(dict(operation='application.activate', target=str(pid))))
press(pid, 'Access')
press(pid, 'Enable access')
assert candidate(dict(operation='action', reference=reference, action='press'))['errorCode'] == 'stale_reference'
press(pid, 'Stop access')
if args.verify_restart_after:
    verify_restart()
print(json.dumps(dict(initialVersion=args.initial_version, version=args.expected_version,
    relaunch='native_reopen' if reopened else 'automatic', permissionsRetained=True,
    accessOff=True, generationChanged=True, staleReferenceRefused=True,
    installedClient=bool(args.candidate_client),
    restartBefore=args.verify_restart_before, restartAfter=args.verify_restart_after)), flush=True)

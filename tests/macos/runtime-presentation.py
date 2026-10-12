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
p.add_argument('--standing-policy', action='store_true', help='Bounded standing-policy preservation and Stop/Resume trial instead of workstation approval acceptance')
p.add_argument('--verify-temporary-restart', action='store_true', help='First prove that a temporary launch override expires on signed Restart')
p.add_argument('--verify-log-folder', action='store_true', help='Observe Open log folder in Finder; requires no existing Finder windows')
p.add_argument('--browser-suite', help='Guest root containing the browser runner, extension and CDP client; candidate must own the canonical resident socket')
p.add_argument('--browser-chrome', help='Separate Chrome for Testing executable in the guest')
a = p.parse_args()
if bool(a.operator_app) != bool(a.operator_socket):
    p.error('Observer app and socket must be supplied together')
if bool(a.browser_suite) != bool(a.browser_chrome):
    p.error('Browser suite and separate test browser must be supplied together')
mc = [str(Path(__file__).resolve().parents[2] / 'bin/machine-control'), '--target', a.target, '--claim', a.claim]
binary = a.candidate_app + '/Contents/MacOS/macui'
pid = None
pending = None
guest_claim = None
notice_child = None
fixture = 'org.machine-control.fixture'


def call(*args, timeout=60):
    return subprocess.check_output(mc + list(args), text=True, timeout=timeout)


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
    assert result.stdout.strip(), ("Empty candidate reply", result.returncode, result.stderr)
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
    # AXWindows can start with an AXHelpTag for the tray tooltip. Bind this
    # test to the actual Settings window's close button using its AX subrole.
    def close_button():
        tree = accepted(base(dict(operation='snapshot', target=str(pid),
            maxDepth=30, maxElements=600)))['elements']
        windows = [e for e in tree if e['role'] == 'AXWindow' and e['label'] == 'Machine Control']
        buttons = [e for e in tree if e.get('subrole') == 'AXCloseButton']
        return buttons if len(windows) == 1 and len(buttons) == 1 else None
    button = wait(close_button, 'native Settings close button')[0]
    accepted(base(dict(operation='action', reference=button['reference'], action='press')))
    wait(lambda: status()['presentation']['settingsWebViews'] == 0, 'Settings destroyed')
    assert status()['processId'] == pid


def approval(scopes):
    global pending
    value = dict(operation='grant.request', requestId=str(uuid.uuid4()), scopes=scopes,
        reason='Verify native runtime presentation', durationSeconds=900, timeoutSeconds=120)
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
    launch = [binary, 'serve', a.candidate_socket]
    if a.verify_temporary_restart:
        launch += ['--presentation', 'minimal' if a.profile == 'personal' else 'personal']
    shell('nohup ' + ' '.join(map(shlex.quote, launch))
          + ' </dev/null >' + shlex.quote(log) + ' 2>&1 &')
    initial = wait(status, 'candidate started')
    pid = initial['processId']
    assert request(dict(operation='status'))['generation'] == request(dict(operation='grant.status'))['generation']
    assert initial['deployment']['policy']['grantMode'] == ('standing' if a.standing_policy else 'approval'), initial['deployment']
    assert initial['deployment']['policy']['source'] == 'policy_file', initial['deployment']
    assert initial['deployment']['policy']['issue'] is None, initial['deployment']
    if a.verify_temporary_restart:
        assert initial['presentation']['temporaryOverride']
        assert initial['presentation']['profile'] != a.profile
        assert preference('status')['profile'] == a.profile
        settings(); press('Permissions'); press('Restart')
        initial = wait(lambda: (value if (value := status())['processId'] != pid else None), 'temporary override restart')
        pid = initial['processId']
        assert not initial['presentation']['temporaryOverride']
        assert preference('status')['profile'] == a.profile
        print('Temporary override expired on signed Restart without changing saved preference', flush=True)
    assert initial['presentation']['profile'] == a.profile, initial['presentation']
    print("Signed startup and runtime identity passed", flush=True)
    expected = 1 if a.profile == 'personal' else 0
    wait(lambda: status()['presentation']['settingsWebViews'] == expected, 'profile startup')
    if expected:
        close_settings()
    settings(); close_settings(); settings(); close_settings()
    print("Lazy Settings and single-instance recovery passed", flush=True)

    if a.standing_policy:
        policy = initial['deployment']['policy']
        before = json.loads(call('testbed', '--', 'fixture-state'))['count']
        snapshot = accepted(request(dict(operation='snapshot', target=fixture, query='Increment', projection='compact')))
        reference = next(e['reference'] for e in snapshot['elements'] if e['role'] == 'AXButton' and e['label'] == 'Increment')
        accepted(request(dict(operation='action', reference=reference, action='press')))
        assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 1
        tray('Stop access')
        assert request(dict(operation='snapshot', target=fixture))['errorCode'] == 'access_paused'
        assert status()['deployment']['policy'] == policy
        settings(); press('Access'); press('Resume access')
        wait(lambda: not status()['deployment']['availability']['paused'], 'standing Resume')
        assert request(dict(operation='action', reference=reference, action='press'))['errorCode'] == 'stale_reference'
        preference('reset')
        wait(lambda: status()['presentation']['profile'] == 'personal', 'standing personal recovery')
        assert status()['deployment']['policy'] == policy
        assert status()['deployment']['grant'] is None
        assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 1
        print(json.dumps({'schema':'machine-control-mac-standing-presentation-acceptance/v1',
            'profile':a.profile, 'standingPolicyPreserved':True, 'independentEffect':True,
            'stopResume':True, 'staleReferences':True, 'personalRecovery':True}, sort_keys=True))
        raise SystemExit(0)

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

    scopes = ['observe', 'control', 'browser', 'devtools'] if a.browser_suite else ['observe', 'control']
    approval(scopes)
    approved = accepted(decide('Allow'))['grant']
    assert request(dict(operation='input.key', target=str(pid), key='tab'))['errorCode'] == 'self_target_refused'
    assert request(dict(operation='authorization.begin'))['errorCode'] == 'operation_not_permitted_by_policy'
    reset = accepted(request(dict(operation='snapshot', target=fixture, query='Reset', projection='compact')))
    reset_ref = next(e['reference'] for e in reset['elements'] if e['role'] == 'AXButton' and e['label'] == 'Reset')
    accepted(request(dict(operation='action', reference=reset_ref, action='press')))
    baseline = json.loads(call('testbed', '--', 'fixture-state'))
    assert baseline['count'] == 0 and baseline['text'] == '', baseline
    before = baseline['count']
    snapshot = accepted(request(dict(operation='snapshot', target=fixture, query='Increment', projection='compact')))
    reference = next(e['reference'] for e in snapshot['elements'] if e['role'] == 'AXButton' and e['label'] == 'Increment')
    accepted(request(dict(operation='action', reference=reference, action='press')))
    assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 1

    print("Native approvals and outside fixture effect passed", flush=True)
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

    native = accepted(request(dict(operation='snapshot', target=fixture, projection='compact'), packaged=True))
    field = next(e['reference'] for e in native['elements'] if e['identifier'] == 'fixture.text')
    accepted(request(dict(operation='action', reference=field, action='focus'), packaged=True))
    # Reset establishes an empty editor. The minimal fixture has no Select
    # All menu binding; Cmd+A exercises the modifier-to-literal transition.
    oracle = json.loads(call('testbed', '--', 'fixture-state'))
    assert oracle['text'] == '', oracle
    accepted(request(dict(operation='input.key', target=fixture, key='cmd-a', deliveryMode='foreground'), packaged=True))
    text = 'presentation-' + a.profile
    accepted(request(dict(operation='input.text', target=fixture, text=text, deliveryMode='foreground'), packaged=True))
    typed = json.loads(call('testbed', '--', 'fixture-state'))
    assert typed['text'] == text and typed['keyEventCount'] > oracle['keyEventCount'], typed
    bounds = typed['surfaceBounds']
    accepted(request(dict(operation='input.click', target=fixture,
        x=round(bounds['x'] + bounds['width'] / 2), y=round(bounds['y'] + bounds['height'] / 2),
        coordinateSpace='global_display_points', deliveryMode='foreground'), packaged=True))
    clicked = json.loads(call('testbed', '--', 'fixture-state'))
    assert clicked['mouseDownCount'] == typed['mouseDownCount'] + 1, clicked
    print('Native keyboard, text and pointer effects independently observed', flush=True)

    if a.browser_suite:
        assert status()['presentation']['settingsWebViews'] == 0
        root = a.browser_suite
        output = call('os', '--', a.candidate_app + '/Contents/Resources/mc-cli/python/bin/python3', '-B',
            root + '/tests/browser/indicators-live.py', '--chrome', a.browser_chrome,
            '--extension', root + '/providers/chrome-extension', '--host-executable', binary,
            '--socket', a.candidate_socket, '--cdp-client', root + '/platforms/chromeos/cdp.py',
            '--claim', guest_claim, '--client', a.candidate_client,
            '--output', root + '/browser-result.json', timeout=240)
        browser_result = json.loads(output.strip().splitlines()[-1])
        assert browser_result['passed'], browser_result
        assert status()['presentation']['settingsWebViews'] == 0
        print('Browser effects, capture and provider reconnect passed with Settings absent', flush=True)

    settings(); press('Settings'); press('Check for updates')
    def discovered_update():
        value = accepted(request(dict(operation='update.status')))['update']
        if value['phase'] == 'error':
            raise RuntimeError('Signed update discovery failed: ' + str(value['error']))
        return value if value['phase'] == 'available' else None
    update = wait(discovered_update, 'signed update discovery')
    install = wait(lambda: [e for e in elements('Install and restart') if e['role'] == 'AXButton'
                           and e['label'] == 'Install and restart'], 'update installation control')
    assert len(install) == 1 and not install[0]['enabled'], install
    assert update['availableVersion'] != update['currentVersion']
    print('Signed update discovery and active-access installation exclusion passed', flush=True)
    press('Access'); press('Pause access')
    wait(lambda: accepted(request(dict(operation='grant.status')))['availability']['paused'], 'operator pause')
    assert request(dict(operation='snapshot', target=fixture))['errorCode'] == 'access_paused'
    press('Resume access')
    wait(lambda: not accepted(request(dict(operation='grant.status')))['availability']['paused'], 'operator resume')
    close_settings()
    notice_child = subprocess.Popen(mc + ['os', '--', '/usr/bin/env',
        'MACHINE_CONTROL_HOST_SOCKET=' + a.candidate_socket, a.candidate_client,
        '--target', 'host', '--claim', guest_claim, 'control', 'call',
        json.dumps(dict(operation='snapshot', target=fixture)), '--reason', 'Verify native notice without Settings', '--scope', 'observe'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    heading = 'Computer control is about to start'
    wait(lambda: any(heading in (e['label'], e.get('value')) for e in elements(heading)), 'native admission notice')
    output, error = notice_child.communicate(timeout=120)
    assert notice_child.returncode == 0, error
    accepted(json.loads(output)); notice_child = None
    assert status()['presentation']['settingsWebViews'] == 0
    print('Operator Pause/Resume and native admission notice passed', flush=True)

    # Supported reset is live, preserves authority, and never requires deleting
    # a special file. Settings itself survives a profile change.
    settings()
    choices = wait(lambda: [e for e in elements('Presentation mode') if e['role'] == 'AXPopUpButton'], 'presentation selector')
    assert len(choices) == 1
    accepted(base(dict(operation='action', reference=choices[0]['reference'], action='press')))
    selected = 'personal' if a.profile == 'minimal' else 'minimal'
    accepted(base(dict(operation='input.key', target=str(pid), key='p' if selected == 'personal' else 'm')))
    accepted(base(dict(operation='input.key', target=str(pid), key='enter')))
    wait(lambda: status()['presentation']['profile'] == selected, 'Settings mode selection applied')
    assert preference('status')['profile'] == selected
    assert accepted(request(dict(operation='grant.status')))['grant']['grantId'] == approved['grantId']
    preference('reset')
    wait(lambda: status()['presentation']['profile'] == 'personal', 'reset applied')
    assert accepted(request(dict(operation='grant.status')))['grant']['grantId'] == approved['grantId']
    assert status()['presentation']['settingsWebViews'] == 1
    close_settings()
    tray('Stop access')
    assert accepted(request(dict(operation='grant.status')))['grant'] is None
    assert request(dict(operation='snapshot', target=fixture))['errorCode'] == 'approval_required'
    settings()
    preference('set', a.profile)
    wait(lambda: status()['presentation']['profile'] == a.profile, 'profile saved before restart')
    old_pid = pid
    old_generation = request(dict(operation='status'))['generation']
    press('Permissions'); press('Restart')
    changed = wait(lambda: (value if (value := status())['processId'] != old_pid else None), 'signed restart')
    pid = changed['processId']
    assert changed['presentation']['profile'] == a.profile
    assert changed['deployment']['policy']['source'] == 'policy_file'
    assert changed['deployment']['policy']['issue'] is None
    assert changed['nativeSemanticState'] == 'ready' and changed['nativeCaptureState'] == 'ready'
    assert request(dict(operation='status'))['generation'] != old_generation
    assert accepted(request(dict(operation='grant.status')))['grant'] is None
    wait(lambda: status()['presentation']['settingsWebViews'] == expected, 'restart presentation')
    if expected: close_settings()
    approval(['observe', 'control']); accepted(decide('Allow'))
    assert request(dict(operation='action', reference=reference, action='press'))['errorCode'] == 'stale_reference'
    assert json.loads(call('testbed', '--', 'fixture-state'))['count'] == before + 2
    tray('Stop access')
    settings()
    if a.verify_log_folder:
        finder = 'com.apple.finder'
        def finder_windows():
            return accepted(base(dict(operation='windows', target=finder)))['windows']
        assert not finder_windows(), 'Log-folder fixture requires no existing Finder windows'
        opened_id = None
        press('Activity'); press('Open log folder')
        try:
            opened = wait(finder_windows, 'native log folder opened in Finder')
            assert len(opened) == 1 and opened[0]['title'] == 'MachineControl', opened
            opened_id = opened[0]['windowId']
        finally:
            # The precondition and unique new window keep cleanup task-owned.
            remaining = finder_windows()
            if opened_id is not None and len(remaining) == 1 and remaining[0]['windowId'] == opened_id:
                accepted(base(dict(operation='window.close', target=finder)))
        wait(lambda: not finder_windows(), 'owned Finder window closed')
        print('Open log folder independently observed in Finder and cleaned up', flush=True)
    print(json.dumps({'schema':'machine-control-mac-presentation-acceptance/v1', 'profile':a.profile,
        'restartAndSignedPermissions':True, 'staleReferences':True, 'pauseResume':True, 'nativeNotice':True,
        'updateDiscoveryAndExclusion':True, 'browserWithoutSettings':bool(a.browser_suite),
        'nativeInputEffects':True,
        'temporaryRestart':a.verify_temporary_restart,
        'logFolder':a.verify_log_folder,
        'startup':True, 'lazySettings':True, 'singleInstanceRecovery':True, 'nativeApproval':True,
        'deferredPreference':True, 'outsideAndLocalEffects':True, 'capture':True, 'settingsSelector':True, 'liveReset':True, 'stop':True}, sort_keys=True))
finally:
    if notice_child is not None:
        if notice_child.poll() is None: notice_child.terminate()
        notice_child.wait(timeout=15)
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
        except (subprocess.SubprocessError, AssertionError, OSError, ValueError):
            subprocess.run(mc + ["os", "--", "/bin/kill", "-TERM", str(pid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if guest_claim is not None:
        call('os', '--', a.candidate_client, '--target', 'host', 'claim', 'release', guest_claim)

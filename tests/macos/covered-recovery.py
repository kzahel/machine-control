"""Production-helper recovery campaign inside a disposable claimed VirtualMac.

Native operator UI owns setup and arming. The controller consumes at most one
strict authorization lease through the existing one-shot credential transport.
All covered cells finish locked; the common workspace receipt owns disposal.
"""
import json
import hashlib
import os
from pathlib import Path
import signal
import select
import re
import subprocess
import time
import uuid


def prepare(c):
    call, poll, press, exchange = (c[k] for k in ['call', 'poll', 'press', 'exchange'])
    assert c['disposable']
    sip = subprocess.check_output(['csrutil', 'status']).decode()
    print('QUALIFICATION ' + json.dumps({'sipEnabled': 'disabled' not in sip.lower() and 'enabled' in sip.lower(),
        'onlineDisplays': call('status')['lockedUse']['onlineDisplays']}), flush=True)
    assert call('status')['unlock']['installation'] == 'missing'
    press('Permissions', 'AXButton')
    press('Set up Machine Control helper', 'AXButton')
    approval_requested = False
    def approve():
        nonlocal approval_requested
        assert not approval_requested, 'A second native authorization attempt is forbidden'
        approval_requested = True
        def switch():
            rows = c['tree']('', 'com.apple.systempreferences')
            matches = [e for e in rows if e.get('role') in {'AXCheckBox', 'AXSwitch'}
                       and e.get('label') == 'Machine Control'
                       and str(e.get('value', '')).lower() in {'0', 'false'}]
            if len(matches) == 1:
                return matches[0]
            return None
        try:
            element = poll(switch, 'exact Machine Control background service switch', timeout=20)
        except AssertionError:
            print('HELPER_APPROVAL_UI ' + json.dumps([
                {'role': e.get('role'), 'label': e.get('label')}
                for e in c['tree']('', 'com.apple.systempreferences')]), flush=True)
            raise
        result = exchange(c['observer'], 'action', reference=element['reference'],
                          action='press', provider='macos-native')
        assert result.get('accepted'), result.get('errorCode')
        lease = poll(lambda: _lease(c), 'strict Login Items authorization sheet', timeout=15)
        print('MC_CREDENTIAL_LEASE ' + json.dumps({'leaseId': lease}), flush=True)
    last = None
    retried = False
    def prepared():
        nonlocal last, retried
        status = call('status')
        current = status['lockedUse']
        diagnostic = {key: current.get(key) for key in ['setupState', 'setupError', 'helperApproval', 'permissionReady']}
        diagnostic['installation'] = status['unlock'].get('installation')
        diagnostic['callerEligibility'] = status['unlock'].get('callerEligibility')
        if diagnostic != last:
            print('HELPER_PREPARATION ' + json.dumps(diagnostic), flush=True)
            last = diagnostic
        if current['setupState'] == 'approval' and current['helperApproval'] == 'requires_approval':
            if not approval_requested:
                approve()
        if current['permissionReady']:
            return current
        if current['setupState'] == 'idle' and current['setupError'] and current['helperApproval'] == 'granted':
            if retried or not any(code in current['setupError'] for code in ['helper did not start', 'unlock_helper_unreachable', 'unlock_not_installed']):
                raise AssertionError('Native helper preparation: ' + current['setupError'])
            retried = True
            press('Set up Machine Control helper', 'AXButton')
        return None
    ready = poll(prepared, 'production helper and capture readiness', timeout=240)
    assert ready['helperHealthy'] and ready['helperApproval'] == 'granted'
    c['check']('native Permissions prepares the production helper without arming ordinary access',
               call('grant.status')['grant'] is None)
    press('Access', 'AXButton')
    c['toggle']('Also while the screen is locked')
    poll(lambda: call('status')['lockedUse']['enabled'], 'prepared locked-use preference')
    # The fixture has an independent file oracle. Its executable is built only
    # in the disposable guest, and its exact process is reaped in cleanup.
    applications = exchange(c['observer'], 'applications', provider='macos-native')
    assert applications.get('accepted')
    existing = [app for app in applications['data']['applications'] if app.get('bundleId') == 'org.machine-control.fixture']
    assert len(existing) <= 1, 'Ambiguous inherited fixture processes'
    for app in existing:
        result = exchange(c['observer'], 'application.terminate', target=str(app['processId']), provider='macos-native')
        assert result.get('accepted'), 'Could not stop the inherited disposable fixture'
    fixture = c['root'] / 'covered-fixture'
    subprocess.run(['xcrun', 'swiftc', str(c['source_root'] /
        'platforms/macos/guests/macos/fixture/MachineControlFixture.swift'),
        '-o', str(fixture)], check=True, capture_output=True, timeout=90)
    c['fixture_binary'] = fixture


def launch_fixture(c):
    fixture = c['fixture_binary']
    poll = c['poll']
    c['fixture'] = subprocess.Popen([str(fixture)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    c['fixture_state'] = Path.home() / 'Library/Caches/machine-control-fixture/state.json'
    poll(lambda: c['fixture_state'].exists() and
         json.loads(c['fixture_state'].read_text())['pid'] == c['fixture'].pid,
         'independent native fixture startup')


def _lease(c):
    assert c['exchange'](c['observer'], 'status')['data']['deployment']['policy']['grantMode'] == 'standing'
    response = c['exchange'](c['observer'], 'authorization.begin', expectedRequester='Login Items',
                             contextId='covered-helper-' + uuid.uuid4().hex, timeoutMs=120000)
    return response.get('data', {}).get('leaseId') if response.get('accepted') else None


def run(c):
    call, raw, poll, check = (c[k] for k in ['call', 'raw', 'poll', 'check'])
    owner = None
    suspended = None

    def fresh_status():
        def observe():
            result = raw('status')
            if result.get('accepted'):
                return result['data']
            assert result.get('errorCode') == 'control_generation_changed', result.get('errorCode')
            return None
        # Only this read is repeated: a lock/unlock transition invalidates its
        # captured generation. Never replay an input or unknown effect.
        # One status can consume its native observation budget while unlock
        # replaces its generation. Leave time for a fresh read after that
        # typed refusal; no action or unknown effect is repeated.
        return poll(observe, 'fresh generation-bound status', timeout=30)

    c['fresh_status'] = fresh_status

    last_recovery = None
    def state(observed=None):
        nonlocal last_recovery
        if observed is None:
            observed = fresh_status()
        value = observed['lockedUse']
        diagnostic = {key: value.get(key) for key in ['phase', 'permissionReady', 'helperHealthy',
            'helperApproval', 'enabled', 'setupState', 'pauseReason', 'recoveryCondition', 'recoveryDelaySeconds', 'lastEndedReason']}
        diagnostic['installation'] = observed['unlock'].get('installation')
        diagnostic['callerEligibility'] = observed['unlock'].get('callerEligibility')
        for key in ['readiness', 'relockAvailable', 'coveredSession', 'lockedUsePaused']:
            diagnostic[key] = observed['unlock'].get(key)
        if diagnostic != last_recovery:
            print('COVERED_RECOVERY ' + json.dumps(diagnostic), flush=True)
            last_recovery = diagnostic
        return value

    def guardian():
        rows = subprocess.check_output(['ps', '-axo', 'pid=,command=']).decode().splitlines()
        matches = [int(row.split(None, 1)[0]) for row in rows
                   if str(c['resident']) + ' locked-use-guardian' in row]
        assert len(matches) <= 1, 'Ambiguous guardian process'
        return matches[0] if matches else None

    def raw_time():
        # Same clock as the root's pausedUptime, independent of Python's
        # platform-dependent monotonic epoch and macOS sleep adjustments.
        return float(subprocess.check_output([str(c['root'] / 'guardian-startup-watch'), '--raw-time']))

    def pause_marker():
        result = subprocess.run(['sudo', '-n', '/usr/bin/plutil', '-convert', 'json', '-o', '-',
            '/var/db/machine-control-unlock/locked-use-paused.plist'],
            capture_output=True, timeout=5)
        if result.returncode:
            assert b'sudo:' not in result.stderr, 'Root pause reader is unavailable'
            return None
        marker = json.loads(result.stdout)
        assert marker['recoveryDelaySeconds'] in {30, 60, 120, 240, 300}, 'Unexpected root fault cooldown'
        assert isinstance(marker['pausedUptime'], (float, int)) and marker['pausedUptime'] > 0
        return marker

    def start():
        nonlocal owner
        assert c['locked'](), 'Each task must start independently locked'
        def recovered():
            assert c['locked'](), 'Console unlocked during autonomous recovery wait'
            observed = fresh_status()
            root = observed['unlock']
            covered = root.get('coveredSession')
            ready = (state(observed)['phase'] == 'ready' and not root.get('lockedUsePaused', True)
                     and isinstance(covered, (bool, int)) and covered == 0
                     and {'observe', 'control'}.issubset((call('grant.status').get('grant') or {}).get('scopes', [])))
            if ready:
                assert raw_time() >= c.get('not_before', 0), 'Root recovered before the advertised cooldown'
            return ready
        poll(recovered,
             'fresh same-console root recovery', timeout=100)
        owner = subprocess.Popen([str(c['resident']), 'request', str(Path.home() /
            'Library/Application Support/MachineControl/control.sock'), json.dumps({
            'operation': 'session.control', 'durationSeconds': 120, 'claimId': c['claim']})],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def active():
            current = state()
            if owner.poll() is not None:
                output, _ = owner.communicate()
                raise AssertionError('Covered startup ended: ' + output.decode() + ' ' + json.dumps(current))
            return current if current['phase'] == 'active' else None
        return poll(active, 'covered activation', timeout=45)

    def ended():
        nonlocal owner
        poll(c['locked'], 'independently observed OS relock', timeout=45)
        poll(lambda: state()['controlSessionId'] is None, 'covered owner cleanup', timeout=45)
        if owner:
            owner.communicate(timeout=15)
            owner = None
        grant = call('grant.status').get('grant') or {}
        consent = Path.home() / 'Library/Application Support/MachineControl/operator-consent.json'
        check('covered ending retains the original until-stopped operator consent',
              grant.get('origin') == 'person' and grant.get('lifetime') == 'until_stopped'
              and hashlib.sha256(consent.read_bytes()).digest() == c['consent_digest'])
        # Scope restoration deliberately issues a fresh generation/ID. Saved
        # consent and its lifetime are the authority oracle, never a reused ID.
        c['original_id'] = grant['grantId']

    def effect():
        before = json.loads(c['fixture_state'].read_text())
        assert before['pid'] == c['fixture'].pid
        tree = call('snapshot', target=str(c['fixture'].pid), provider='macos-native')
        buttons = [e for e in tree['elements'] if e.get('role') == 'AXButton' and e.get('label') == 'Increment']
        assert len(buttons) == 1
        call('action', reference=buttons[0]['reference'], action='press', provider='macos-native')
        poll(lambda: json.loads(c['fixture_state'].read_text())['count'] == before['count'] + 1,
             'independent covered AX effect')
        bounds = buttons[0]['bounds']
        call('input.click', target=str(c['fixture'].pid), provider='macos-native',
             coordinateSpace='global_display_points', x=int(bounds['x'] + bounds['width']/2),
             y=int(bounds['y'] + bounds['height']/2))
        poll(lambda: json.loads(c['fixture_state'].read_text())['count'] == before['count'] + 2,
             'independent covered pointer effect')
        call('input.key', target=str(c['fixture'].pid), provider='macos-native', key='a')
        poll(lambda: json.loads(c['fixture_state'].read_text())['keyEventCount'] > before['keyEventCount'],
             'independent covered keyboard effect')
        capture = call('capture', scope='display', provider='macos-native')
        image = Path(capture['artifactPath']).read_bytes()
        assert capture['coversExcluded'] and image.startswith(b'\x89PNG\r\n\x1a\n')
        output = c['evidence'] / ('covered-fixture-' + str(before['count'] + 2) + '.png')
        with os.fdopen(os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(image)
        check('covered native semantics, pointer, keyboard and excluded-cover capture have independent effects')

    def crash(stall=False, stop_resident=False):
        nonlocal suspended
        start()
        pid = guardian()
        assert pid
        if stall:
            suspended = pid
        observed_pause = None
        assert pause_marker() is None, 'Previous root pause must be cleared before injection'
        def root_log():
            return subprocess.check_output(['sudo', '-n', '/usr/bin/log', 'show', '--last', '2m',
                '--style', 'compact', '--predicate', 'process == "mc-unlock-broker" AND '
                '(eventMessage BEGINSWITH "Console " OR eventMessage BEGINSWITH "Covered ending")'], timeout=15).decode()
        before_log = root_log() if stop_resident else ''
        before_lines = set(before_log.splitlines())
        resident_stopped = False
        def locked_with_pause():
            nonlocal observed_pause
            if observed_pause is None:
                observed_pause = pause_marker()
            return c['locked']()
        fault_at = raw_time()
        try:
            if stop_resident:
                path = subprocess.check_output([str(c['root'] / 'guardian-startup-watch'), '--pidpath', str(c['pid'])]).decode().strip()
                assert Path(path).resolve() == Path(c['resident']).resolve(), 'Resident identity changed; no signal sent'
                os.kill(c['pid'], signal.SIGSTOP); resident_stopped = True
            os.kill(pid, signal.SIGSTOP if stall else signal.SIGKILL)
            poll(locked_with_pause, 'safety path independently relocks', timeout=18)
            locked_at = raw_time()
            if observed_pause is None:
                observed_pause = poll(pause_marker, 'independent root fault marker', timeout=5)
            pause_at = observed_pause['pausedUptime']
            assert -1 <= pause_at - fault_at <= 10, 'Root did not detect the injected fault promptly'
            assert locked_at - pause_at <= 10, 'Root fault-to-lock exceeded ten seconds'
            if stall:
                assert locked_at - fault_at < 20, 'Resident silence fallback cannot qualify root relock'
            print('ROOT_FAULT_PAUSE ' + json.dumps({'recoveryDelaySeconds':observed_pause['recoveryDelaySeconds'],
                'guardianStopped':stall, 'residentStopped':stop_resident,
                'detectSeconds':round(pause_at-fault_at,3), 'rootPauseToLockSeconds':round(locked_at-pause_at,3),
                'injectionToLockSeconds':round(locked_at-fault_at,3)}), flush=True)
            if stop_resident:
                # Keep both user-session providers suspended until the root's
                # exact implementation has produced lock and completed its
                # short-lived runner. A parent's fallback cannot pass this cell.
                def route_completed():
                    log = root_log()
                    added = '\n'.join(line for line in log.splitlines() if line not in before_lines)
                    (c['evidence'] / 'root-only-relock.log').write_text(added)
                    os.chmod(c['evidence'] / 'root-only-relock.log', 0o600)
                    return ('dispatched through user_bootstrap_runner' in added and
                            'runner ended (status=0 ' in added and
                            'Console relock readback (locked=1 ' in added)
                poll(route_completed, 'root-only dispatch, runner exit and independent readback log', timeout=30)
        finally:
            if suspended:
                os.kill(suspended, signal.SIGCONT); suspended = None
            if resident_stopped:
                os.kill(c['pid'], signal.SIGCONT)
        ended()
        c['not_before'] = observed_pause['pausedUptime'] + observed_pause['recoveryDelaySeconds'] - .5
        def settled_recovery():
            observed = fresh_status()
            value = state(observed)
            return observed if value['phase'] in {'recovering', 'ready'} else None
        observed = poll(settled_recovery, 'fresh pending or completed recovery')
        current = observed['lockedUse']
        if current['phase'] == 'recovering':
            refusal = raw('snapshot', target=str(c['fixture'].pid), provider='macos-native')
            observed = poll(settled_recovery, 'recovery state after desktop probe')
            current = observed['lockedUse']
            if current['phase'] == 'recovering':
                # Grant restoration can temporarily publish browser scopes
                # before the local recovery fence is consulted. Both layers
                # must refuse desktop dispatch under the retained consent.
                assert not refusal['accepted'] and refusal['errorCode'] in {
                    'locked_use_recovery_pending', 'desktop_locked_browser_only',
                    'access_temporarily_unavailable'}, 'Desktop dispatch must remain fenced'
                c['desktop_recovery_guard_verified'] = True
                print('DESKTOP_RECOVERY_GUARD ' + json.dumps({'refusalCode':refusal['errorCode'],
                    'coveredSession':observed['unlock'].get('coveredSession'),
                    'lockedUsePaused':observed['unlock'].get('lockedUsePaused')}), flush=True)
        if current['phase'] == 'ready':
            root = observed['unlock']
            assert root.get('installation') == 'healthy' and root.get('callerEligibility') == 'allowed'
            assert not root.get('lockedUsePaused', True) and root.get('coveredSession') == 0
            assert raw_time() >= c['not_before'], 'Root recovered before minimum fault cooldown'
        before = c['effects']['clicks']
        call('browser.eval', tabId=c['browser_tab'], expression="fetch('/click', {method:'POST'}); true")
        poll(lambda: c['effects']['clicks'] == before + 1, 'browser effect across protected recovery')
        check('protected failure preserves browser control and fences pending desktop recovery')
        return observed_pause['recoveryDelaySeconds']

    def stalled_root():
        start()
        def freshly_live():
            age = state().get('helperLastPositiveAgeMs')
            return isinstance(age, (int, float)) and age <= 1000
        poll(freshly_live, 'fresh positive helper liveness before root fault injection')
        job = subprocess.check_output(['sudo', '-n', '/bin/launchctl', 'print',
                                       'system/org.machine-control.unlock']).decode()
        matches = re.findall(r'^\s*pid = (\d+)\s*$', job, re.MULTILINE)
        assert len(matches) == 1, 'Root fault injection requires one exact managed service PID'
        pid = int(matches[0])
        probe = c['root'] / 'guardian-startup-watch'
        executable = subprocess.check_output([str(probe), '--pidpath', str(pid)]).decode().strip()
        expected = Path(c['resident']).parents[1] / 'Resources/unlock/mc-unlock-broker'
        assert Path(executable).resolve() == expected.resolve(), 'Root service identity mismatch; no signal sent'
        latest = subprocess.check_output(['sudo', '-n', '/bin/launchctl', 'print',
                                          'system/org.machine-control.unlock']).decode()
        assert re.findall(r'^\s*pid = (\d+)\s*$', latest, re.MULTILINE) == [str(pid)], 'Root generation changed; no signal sent'
        stopped_at = time.monotonic()
        subprocess.run(['sudo', '-n', '/bin/kill', '-STOP', str(pid)], check=True, capture_output=True)
        try:
            before = c['effects']['clicks']
            call('browser.eval', tabId=c['browser_tab'], expression="fetch('/click', {method:'POST'}); true")
            poll(lambda: c['effects']['clicks'] == before + 1, 'browser effect while root is stalled')
            poll(c['locked'], 'resident/guardian relock with the root watchdog stalled', timeout=45)
            assert time.monotonic() - stopped_at >= 25, 'A different early ending cannot qualify helper-silence recovery'
        finally:
            # Resume the exact helper even on inconclusive injection, restoring
            # its independent watchdog before any failure cleanup can proceed.
            resumed_at = raw_time()
            subprocess.run(['sudo', '-n', '/bin/kill', '-CONT', str(pid)], check=True, capture_output=True)
        ended()
        assert state()['lastEndedReason'] == 'helper_unavailable', 'A different ending cannot qualify helper liveness'
        def recovering():
            current = state()
            return current if current['phase'] == 'recovering' and current['recoveryDelaySeconds'] == 30 else None
        poll(recovering, 'root catches up to the independently locked helper-silence ending')
        marker = poll(pause_marker, 'root fault timestamp after helper resume', timeout=10)
        assert marker['recoveryDelaySeconds'] == 30 and marker['pausedUptime'] >= resumed_at - 1
        c['not_before'] = marker['pausedUptime'] + marker['recoveryDelaySeconds'] - .5
        check('a hung root cannot silently remove the independent watchdog for an admitted task')

    def startup_timeout():
        nonlocal owner, suspended
        def injection_ready():
            assert c['locked'](), 'Console unlocked while waiting for startup injection'
            return state()['phase'] == 'ready'
        poll(injection_ready, 'fresh helper readiness before startup injection', timeout=20)
        watcher = c['root'] / 'guardian-startup-watch'
        subprocess.run(['xcrun', 'clang', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'CoreGraphics',
                        str(c['source_root'] / 'tests/macos/guardian-startup-watch.m'), '-o', str(watcher)],
                       capture_output=True, check=True, timeout=60)
        observer = subprocess.Popen([str(watcher), str(c['pid'])], stdout=subprocess.PIPE)
        for required in ['/var/db/machine-control-unlock', '/var/db/machine-control-unlock/receipt.plist']:
            assert subprocess.run(['sudo', '-n', '/bin/test', '-e', required], capture_output=True).returncode == 0, 'Independent root state probe unavailable'
        marker = '/var/db/machine-control-unlock/covered-session.plist'
        try:
            owner = subprocess.Popen([str(c['resident']), 'request', str(Path.home() /
                'Library/Application Support/MachineControl/control.sock'), json.dumps({
                'operation':'session.control', 'durationSeconds':120, 'claimId':c['claim']})],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert select.select([observer.stdout], [], [], 35)[0], 'Native guardian watcher timed out'
            line = observer.stdout.readline()
            assert line, 'Native guardian watcher missed startup; cell unqualified'
            observed = json.loads(line)
            assert observer.wait(timeout=5) == 0
            suspended = observed['pid']
            assert observed['ownedWindows'] == 0 and c['locked'](), 'Startup injection too late; cell unqualified'
            process_state = subprocess.check_output(['ps', '-o', 'state=', '-p', str(suspended)]).decode().strip()
            assert process_state.startswith('T'), 'Guardian did not stop before startup'
            def unarmed():
                assert c['locked'](), 'Console unlocked during unarmed startup timeout'
                result = subprocess.run(['sudo', '-n', '/bin/test', '!', '-e', marker], capture_output=True, timeout=5)
                assert result.returncode == 0, 'Root armed during startup injection; cell unqualified'
            deadline = time.monotonic() + 14
            while time.monotonic() < deadline:
                unarmed(); time.sleep(.1)
            # The parent has abandoned and closed startup. A late child must
            # exit without arming. Parent validation or the startup socket
            # fence can enforce this; the socketpair test isolates the latter.
            os.kill(suspended, signal.SIGCONT)
            delayed = suspended; suspended = None
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                unarmed()
                result = subprocess.run(['ps', '-o', 'state=', '-p', str(delayed)], capture_output=True)
                if result.returncode or result.stdout.strip().startswith(b'Z'):
                    break
                time.sleep(.1)
            else:
                os.kill(delayed, signal.SIGKILL)
                raise AssertionError('Delayed guardian did not exit after startup cancellation')
            ended()
            check('late guardian exits after parent startup timeout without arming or unlocking')
            assert state()['lastEndedReason'] == 'guardian_start_failed'
            assert not fresh_status()['unlock'].get('lockedUsePaused')
            before = c['effects']['clicks']
            call('browser.eval', tabId=c['browser_tab'], expression="fetch('/click', {method:'POST'}); true")
            poll(lambda: c['effects']['clicks'] == before + 1, 'locked browser effect after failed startup')
            check('failed pre-arm startup preserves standing browser authorization')
        finally:
            if observer.poll() is None:
                observer.terminate(); observer.wait(timeout=10)
            if suspended:
                # Never resume an inconclusive injection. Root/OS cleanup is
                # independently verified before the disposable clone is freed.
                os.kill(suspended, signal.SIGKILL); suspended = None

    try:
        startup_timeout()
        active = start(); effect()
        call('session.control.end', controlSessionId=active['controlSessionId']); ended()
        first = crash()
        check('first guardian failure advertises bounded automatic recovery', first == 30)
        second = crash()
        check('repeated guardian failure increases recovery cooldown', second == 60)
        active = start(); effect()
        call('session.control.end', controlSessionId=active['controlSessionId']); ended()
        check('a fresh covered task succeeds after autonomous recovery without rearming')
        check('root watchdog recovers a stalled guardian', crash(stall=True) == 30)
        active = start()
        call('session.control.end', controlSessionId=active['controlSessionId']); ended()
        check('root alone relocks with both resident and guardian stopped', crash(stall=True, stop_resident=True) == 30)
        active = start()
        call('session.control.end', controlSessionId=active['controlSessionId']); ended()
        assert c.get('desktop_recovery_guard_verified'), 'Campaign never observed actual desktop dispatch fencing'
        stalled_root()
        active = start()
        call('session.control.end', controlSessionId=active['controlSessionId']); ended()
        start()
        consent = Path.home() / 'Library/Application Support/MachineControl/operator-consent.json'
        digest = hashlib.sha256(consent.read_bytes()).digest()
        c['pid'] = c['restart']()
        poll(c['locked'], 'guardian relocks after resident death', timeout=45)
        if owner:
            owner.communicate(timeout=15); owner = None
        marker = poll(pause_marker, 'root fault timestamp after resident restart', timeout=10)
        assert marker['recoveryDelaySeconds'] == 30
        c['not_before'] = marker['pausedUptime'] + marker['recoveryDelaySeconds'] - .5
        restored = poll(lambda: call('grant.status').get('grant'), 'saved browser consent restoration', timeout=20)
        check('resident death restores independent browser scopes while protected recovery is pending',
              set(restored['scopes']) == {'browser', 'devtools'} and state()['recoveryCondition'] is not None)
        refusal = raw('snapshot', target=str(c['fixture'].pid), provider='macos-native')
        check('temporarily unavailable desktop scopes do not ask for new approval',
              not refusal['accepted'] and refusal['errorCode'] == 'access_temporarily_unavailable')
        poll(lambda: raw('browser.tabs').get('accepted'), 'extension reconnect after armed resident crash', timeout=30)
        before = c['effects']['clicks']
        call('browser.eval', tabId=c['browser_tab'], expression="fetch('/click', {method:'POST'}); true")
        poll(lambda: c['effects']['clicks'] == before + 1, 'restored locked-browser effect')
        def restored_desktop():
            assert c['locked'](), 'Console unlocked during restart recovery'
            ready = {'observe', 'control'}.issubset(call('grant.status')['grant']['scopes'])
            if ready:
                assert raw_time() >= c['not_before'], 'Desktop scopes restored before fault cooldown'
            return ready
        poll(restored_desktop, 'fresh desktop scope upgrade after root recovery', timeout=100)
        c['original_id'] = call('grant.status')['grant']['grantId']
        check('recovery upgrades authority with saved operator consent unchanged',
              hashlib.sha256(consent.read_bytes()).digest() == digest == c['consent_digest'])
        # Leave a fresh covered lease active so the observer can exercise the
        # real operator Stop. Stop must terminate it and independently relock.
        start()
        c['check_stop_lock'] = True
    finally:
        if suspended:
            os.kill(suspended, signal.SIGCONT)
        if not c.get('check_stop_lock') and owner and owner.poll() is None:
            try:
                current = state()
                if current['controlSessionId']:
                    call('session.control.end', controlSessionId=current['controlSessionId'])
            finally:
                owner.communicate(timeout=30)
        c['covered_owner'] = owner


def cleanup(c):
    owner = c.get('covered_owner')
    try:
        if owner:
            try:
                current = c.get('fresh_status', lambda: c['call']('status'))()['lockedUse']
                if current['controlSessionId']:
                    c['call']('session.control.end', controlSessionId=current['controlSessionId'])
                owner.communicate(timeout=30)
            finally:
                if owner.poll() is None:
                    owner.terminate(); owner.communicate(timeout=15)
    finally:
        fixture = c.get('fixture')
        if fixture:
            fixture.terminate(); fixture.wait(timeout=15)

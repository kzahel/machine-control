#!/usr/bin/env python3
"""Exercise signed installed updates with live access in a dedicated Mac VM.

Run on the controller under `machine-control --target macos run`. Supply two
authenticated candidate package directories: an older sender and the incoming
release. The sender keeps its production updater endpoint and signed-version
requirement. The guest serves an exact-shape fixture feed for that endpoint
through a temporary hosts entry and a temporary trusted fixture certificate.

The guest backs up and restores the installed app, policy, LaunchAgent,
operator files, app data, hosts and certificate trust. Removing certificate
trust raises the System Certificate Trust Settings prompt; the independent
appliance observer issues a one-use lease and this controller delivers the
canonical appliance credential through the resident's secret transport. This
runner restores the original power state. Never run it on a personal Mac.

Checks: Off before update stays Off; enabled Desktop (timed) and Browser
(until stopped, exact profile) leave Install and restart enabled with the
pause note; an active task requires Install anyway/Cancel; a tampered
download never stops access; a verified update records a one-shot plan, stops
access, relaunches automatically and replays the same surfaces with the
original wall-clock end, then deletes the plan. Generation, version, source,
permissions, installed CLI identity and stale references are verified.
Raw evidence stays in a new private directory outside the checkout.
"""
import argparse
import base64
import calendar
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import signal
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import uuid

HOST = 'machinecontrol.dev'
FEED_PREFIX = '/updates/tauri/darwin/aarch64/'
ARCHIVE_PREFIX = '/fixture-updates/'
PLAN = 'update-access-resume.json'
RESTORED_NOTE = 'Access was turned back on after the update.'
PAUSE_NOTE = 'Access pauses while Machine Control restarts, then turns back on.'
HOSTS_MARK = '# machine-control update fixture'


# --------------------------------------------------------------------------
# Guest half: runs inside the dedicated VirtualMac from a private stage.
# --------------------------------------------------------------------------

def guest(stage, claim):
    sys.path.insert(0, str(stage / 'source/tests/macos'))
    from surface_fixture import SurfaceFixture, launch_profile, poll, require_managed_observer
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).startswith(b'VirtualMac')
    home = Path.home()
    installed = home / 'Applications/Machine Control.app'
    resident = installed / 'Contents/MacOS/macui'
    support = home / 'Library/Application Support/MachineControl'
    endpoint = support / 'control.sock'
    policy = Path('/Library/Application Support/MachineControl/policy.json')
    agent = home / 'Library/LaunchAgents/org.machine-control.resident.plist'
    domain = 'gui/' + str(os.getuid())
    label = domain + '/org.machine-control.resident'
    plan_path = home / 'Library/Application Support/org.machine-control.app' / PLAN
    app_dirs = [home / 'Library/Application Support/org.machine-control.app',
                home / 'Library/Caches/org.machine-control.app',
                home / 'Library/WebKit/org.machine-control.app',
                home / 'Library/HTTPStorages/org.machine-control.app',
                home / 'Library/Saved Application State/org.machine-control.app.savedState']
    operator_files = ['operator-consent.json', 'presentation.json', 'desktop-caller-trust.json']
    hosts = Path('/etc/hosts')
    feed = json.loads((stage / 'feed/feed.json').read_text())
    sender_app = stage / 'sender/Machine Control.app'
    observer_socket = stage / 'observer/control.sock'
    backup = stage / 'backup'
    backup.mkdir(mode=0o700)
    results = stage / 'results'
    results.mkdir(mode=0o700)
    checks, evidence = [], {}

    def check(name, condition, detail=None):
        assert condition, name + ('' if detail is None else ': ' + json.dumps(detail, default=str))
        checks.append(name)
        print('PASS ' + name, flush=True)

    def command(*args, check=True, stdin=None):
        return subprocess.run([str(v) for v in args], check=check, capture_output=True,
                              timeout=120, stdin=stdin)

    def exchange(path, operation, timeout=10, **fields):
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(timeout)
            c.connect(str(path))
            c.sendall(json.dumps(dict(operation=operation, claimId=claim, **fields)).encode() + b'\n')
            line = c.makefile('rb').readline(32 * 1024 * 1024)
            if not line:
                raise ConnectionError('resident closed the request')
            return json.loads(line)

    def status(path=endpoint):
        try:
            value = exchange(path, 'status')
        except (OSError, ValueError):
            return None
        return value if value.get('accepted') else None

    def update_status():
        for _ in range(50):
            value = exchange(endpoint, 'update.status')
            if value.get('accepted') or value.get('errorCode') != 'native_provider_busy':
                break
            time.sleep(.2)
        assert value.get('accepted'), value.get('errorCode')
        return value['data']['update']

    def wait(fn, description, seconds=60):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = fn()
            if value:
                return value
            time.sleep(.2)
        raise AssertionError('Timed out: ' + description)

    def info(app=installed):
        return plistlib.loads((app / 'Contents/Info.plist').read_bytes())

    def manifest(app):
        result = {}
        for f in sorted(app.rglob('*')):
            mode = stat.S_IMODE(f.lstat().st_mode)
            result[str(f.relative_to(app))] = (
                ['link', mode, os.readlink(f)] if f.is_symlink() else
                ['file', mode, hashlib.sha256(f.read_bytes()).hexdigest()] if f.is_file() else
                ['directory', mode])
        return result

    def stop_candidate():
        for operation in ['grant.revoke', 'server.stop']:
            with contextlib.suppress(OSError, ValueError):
                exchange(endpoint, operation)
        command('/bin/launchctl', 'bootout', label, check=False)
        wait(lambda: status() is None, 'resident released the canonical endpoint')
        endpoint.unlink(missing_ok=True)

    def trust_entries():
        dump = command('/usr/bin/security', 'dump-trust-settings', '-d', check=False)
        keys = command('/usr/bin/security', 'find-certificate', '-a', '-Z', '/Library/Keychains/System.keychain')
        hashes = sorted(line.split(':', 1)[1].strip() for line in keys.stdout.decode().splitlines()
                        if line.startswith('SHA-1 hash:'))
        return {'adminTrust': (dump.stdout + dump.stderr).decode().strip(), 'systemKeychain': hashes}

    # ---- Baseline and backups ------------------------------------------------
    original = status()
    require_managed_observer(original['data'])
    original_manifest = manifest(installed)
    command('/usr/bin/ditto', installed, backup / 'Original.app')
    assert manifest(backup / 'Original.app') == original_manifest
    original_agent, agent_mode = agent.read_bytes(), stat.S_IMODE(agent.stat().st_mode)
    original_policy, policy_stat = policy.read_bytes(), policy.stat()
    (backup / 'policy.json').write_bytes(original_policy)
    support_entries = {p.name for p in support.iterdir()}
    saved = {}
    for name in operator_files:
        f = support / name
        saved[name] = (f.read_bytes(), stat.S_IMODE(f.stat().st_mode)) if f.exists() else None
    prefs = command('/usr/bin/defaults', 'export', 'org.machine-control.app', '-', check=False)
    (backup / 'preferences.plist').write_bytes(prefs.stdout)
    saved_dirs = {}
    for index, path in enumerate(app_dirs):
        saved_dirs[path] = path.exists()
        if path.exists():
            command('/usr/bin/ditto', path, backup / ('appdir-' + str(index)))
    original_hosts, hosts_stat = hosts.read_bytes(), hosts.stat()
    assert HOST.encode() not in original_hosts, 'hosts already names the update host'
    original_trust = trust_entries()
    fixture_sha1 = feed['caSHA1']
    assert fixture_sha1 not in original_trust['systemKeychain']

    observer = feed_server = browser = rig = None
    mutated = hosts_changed = trust_added = False
    feed_state = FeedState(stage)
    try:
        # ---- Independent observer, fixture feed, hosts and trust -------------
        observer_socket.parent.mkdir(mode=0o700)
        with (results / 'observer.log').open('wb') as log:
            observer = subprocess.Popen([str(backup / 'Original.app/Contents/MacOS/macui'),
                                         'serve', str(observer_socket)], stdout=log, stderr=log)
        require_managed_observer(wait(lambda: status(observer_socket), 'observer')['data'])

        # Unprivileged macOS processes cannot bind loopback port 443. Only
        # this bounded fixture server runs as root; it exits with this actor.
        feed_server = subprocess.Popen(['/usr/bin/sudo', '-n', '/usr/bin/python3', '-I', str(stage / 'tauri-update.py'),
            '--serve-feed', str(stage), '--owner-pid', str(os.getpid())], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=(results / 'feed-server.log').open('wb'))
        wait(lambda: (stage / 'feed/ready').exists() or feed_server.poll() is not None, 'fixture feed server', 20)
        assert feed_server.poll() is None, 'Fixture feed server did not start'
        command('/usr/bin/sudo', '-n', '/usr/bin/security', 'add-trusted-cert', '-d', '-r', 'trustRoot',
                '-k', '/Library/Keychains/System.keychain', stage / 'feed/ca.pem')
        trust_added = True
        hosts_file = stage / 'hosts'
        hosts_file.write_bytes(original_hosts.rstrip(b'\n') + b'\n' +
            ('127.0.0.1\t%s %s\n::1\t%s %s\n' % (HOST, HOSTS_MARK, HOST, HOSTS_MARK)).encode())
        hosts_changed = True
        command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m', '644', '-o', 'root', '-g', 'wheel', hosts_file, hosts)
        command('/usr/bin/sudo', '-n', '/usr/bin/dscacheutil', '-flushcache')
        command('/usr/bin/sudo', '-n', '/usr/bin/killall', '-HUP', 'mDNSResponder', check=False)
        lookup = command('/usr/bin/dscacheutil', '-q', 'host', '-a', 'name', HOST).stdout.decode()
        addresses = set(re.findall(r'^ip(?:v6)?_address: (\S+)$', lookup, re.M))
        check('fixture host resolves only to guest loopback', addresses and addresses <= {'127.0.0.1', '::1'}, sorted(addresses))
        verified = command('/usr/bin/security', 'verify-cert', '-c', stage / 'feed/leaf.pem',
                           '-p', 'ssl', '-s', HOST, check=False)
        check('system trust evaluates the fixture certificate for the update host', verified.returncode == 0)
        probe = command('/usr/bin/curl', '-sS', '--cacert', stage / 'feed/ca.pem',
                        'https://' + HOST + FEED_PREFIX + feed['senderVersion'])
        check('fixture feed answers the exact production route', json.loads(probe.stdout) == feed['response'])
        feed_state.clear()

        # ---- Install the sender under workstation policy ---------------------
        mutated = True
        stop_candidate()
        work = stage / 'workstation.json'
        work.write_text(json.dumps({'schema': 'machine-control-policy/v0', 'preset': 'workstation',
                                    'protectedOperations': False}))
        command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m', '644', work, policy)
        for name in operator_files:
            (support / name).unlink(missing_ok=True)
        presentation = support / 'presentation.json'
        presentation.write_text(json.dumps({'schema': 'machine-control-presentation/v1', 'profile': 'minimal'}))
        presentation.chmod(0o600)

        def install_sender():
            command('/bin/bash', stage / 'install-user.sh', '--app', sender_app)
            current = wait(status, 'installed sender')
            data = current['data']
            assert info()['CFBundleShortVersionString'] == feed['senderVersion']
            assert data['deployment']['policy']['grantMode'] == 'surface_modes'
            assert data['admission']['schema'] == 'machine-control-admission/v2'
            assert data['nativeSemanticState'] == 'ready', 'Signed sender needs normal Accessibility consent'
            assert all(v['mode'] == 'off' for v in data['admission']['surfaces'].values())
            plan_path.unlink(missing_ok=True)
            return current

        install_sender()
        rig = SurfaceFixture(stage / 'source', resident, endpoint, observer_socket, claim)

        def surfaces():
            return rig.status()['admission']['surfaces']

        def texts():
            rows = rig.tree()
            return [str(row.get(key, '')) for row in rows for key in ('label', 'value', 'title', 'description')]

        def has_text(fragment):
            return any(fragment in value for value in texts())

        def button(name):
            return rig.find(name)

        def press_after(anchor, name):
            # Press the confirmation's own button, not an unrelated same label.
            rows = rig.tree()
            start = next(i for i, row in enumerate(rows) if row.get('role') == 'AXButton' and row.get('label') == anchor)
            row = next(row for row in rows[start + 1:] if row.get('role') == 'AXButton' and row.get('label') == name)
            rig.observe('action', reference=row['reference'], action='press')

        def open_settings_page():
            rig.settings()
            rig.press('Settings')

        def discover():
            open_settings_page()
            rig.press('Check for updates')

            def ready():
                update = update_status()
                if update['phase'] == 'error':
                    raise AssertionError('Native update discovery failed: ' + str(update['error']))
                row = button('Install and restart')
                return (update, row) if (update['phase'] == 'available' and row and
                        update['availableVersion'] == feed['incomingVersion']) else None
            update, row = wait(ready, 'sender discovers the signed fixture update', 90)
            assert any(r['path'] == FEED_PREFIX + feed['senderVersion'] for r in feed_state.requests())
            # WebKit renders the settled state shortly after native discovery.
            end = time.monotonic() + 15
            while row.get('enabled') is not True and time.monotonic() < end:
                time.sleep(.3)
                row = button('Install and restart') or row
            return update, row

        def watch_install(old_pid):
            """Record plan presence and resident access until replacement."""
            record = {'plan': None, 'planMode': None, 'samples': [], 'stop': False}

            def run():
                tick = 0
                while not record['stop']:
                    tick += 1
                    if record['plan'] is None and plan_path.exists():
                        with contextlib.suppress(OSError, ValueError):
                            record['planMode'] = oct(stat.S_IMODE(plan_path.stat().st_mode))
                            record['plan'] = json.loads(plan_path.read_text())
                            record['planSeenAt'] = time.time()
                    if tick % 5:
                        time.sleep(.04)
                        continue  # Sample status gently; it shares the native budget.
                    try:
                        value = exchange(endpoint, 'status', timeout=2)
                        data = value.get('data') or {}
                        record['samples'].append({'t': time.time(), 'pid': data.get('processId'),
                            'modes': {k: v['mode'] for k, v in data.get('admission', {}).get('surfaces', {}).items()}})
                    except (OSError, ValueError):
                        record['samples'].append({'t': time.time(), 'pid': None})
                    time.sleep(.04)
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            record['thread'] = thread
            return record

        def relaunched(old_pid, old_generation):
            def ready():
                value = status()
                if not value or value['data'].get('processId') in (None, old_pid):
                    return None
                try:
                    current = info().get('CFBundleShortVersionString')
                except Exception:
                    return None  # The bundle is briefly absent during replacement.
                return value if current == feed['incomingVersion'] else None
            value = wait(ready, 'automatic relaunch of the incoming version', 180)
            new_info = info()
            check('automatic relaunch runs the exact incoming version and source',
                  new_info['CFBundleShortVersionString'] == feed['incomingVersion'] and
                  new_info.get('MCSourceRevision') == feed['revision'],
                  {k: new_info.get(k) for k in ['CFBundleShortVersionString', 'MCSourceRevision']})
            command('/usr/bin/codesign', '--verify', '--deep', '--strict', installed)
            def permissions():
                data = (status() or {}).get('data') or {}
                return data if data.get('captureState') == 'ready' else None
            data = wait(permissions, 'relaunched permissions ready', 60)
            check('replacement retains semantic and capture permission',
                  data['nativeSemanticState'] == 'ready' and data['captureState'] == 'ready')
            check('relaunch changes the resident generation', value['generation'] != old_generation)
            archive = [r for r in feed_state.requests() if r['path'] == ARCHIVE_PREFIX + feed['archiveName']]
            check('installed bytes came from the fixture feed', archive and archive[-1]['served'] == 'genuine')
            return value

        def journal(kind, since):
            # Closed-code client diagnostics and the native resident's audit.
            rows = []
            for path in sorted((home / 'Library/Logs/MachineControl' / kind).glob('*.jsonl')):
                with contextlib.suppress(OSError):
                    for line in path.read_text().splitlines():
                        with contextlib.suppress(ValueError):
                            row = json.loads(line)
                            at = row.get('atUnixMs', 0) / 1000 or calendar.timegm(time.strptime(row['at'], '%Y-%m-%dT%H:%M:%SZ'))
                            if at >= int(since):
                                rows.append(dict(row, _at=at))
            return sorted(rows, key=lambda row: (row['_at'], row.get('sequence', 0)))

        def codes(since, version=None):
            return [r['operation'] for r in journal('diagnostics', since)
                    if version is None or r.get('version') == version]

        def finish_watch(record):
            record['stop'] = True
            record['thread'].join(5)
            record.pop('thread')
            return record

        # ---- Cycle 1: access Off stays Off ------------------------------------
        before = status()
        update, install = discover()
        check('Off: Install and restart is enabled', install.get('enabled') is True)
        check('Off: no pause note while access is Off', not has_text(PAUSE_NOTE))
        # No task is live, so the one press must install without confirmation.
        pressed = time.time()
        rig.press('Install and restart')
        watch = watch_install(before['data']['processId'])
        after = relaunched(before['data']['processId'], before['generation'])
        record = finish_watch(watch)
        check('Off: one press installs without task confirmation', True)
        check('Off: no restoration plan is written', record['plan'] is None)
        off_codes = codes(pressed)
        check('Off: client installs without stopping or restoring access',
              'update.install.ok' in off_codes and not any(c.startswith('update.access.') for c in off_codes), off_codes)
        check('Off: plan file absent after relaunch', not plan_path.exists())
        time.sleep(20)
        current = rig.status()
        check('Off: every surface remains Off after relaunch',
              all(v['mode'] == 'off' for v in current['admission']['surfaces'].values()))
        check('Off: updated client reports no access restoration', update_status().get('accessResume') is None)
        open_settings_page()
        check('Off: Settings shows no restoration message', not has_text(RESTORED_NOTE))
        evidence['offCycle'] = {'from': feed['senderVersion'], 'to': info()['CFBundleShortVersionString'],
            'generationChanged': after['generation'] != before['generation'],
            'samples': len(record['samples'])}

        # ---- Cycle 2: Desktop timed + Browser until stopped ------------------
        rig.close()
        install_sender()
        cli = installed / 'Contents/Resources/mc-cli/commands/machine-control'
        sender_cli = json.loads(command(cli, 'agent', 'identity').stdout) if cli.exists() else None
        if sender_cli:
            check('installed CLI identifies the sender', sender_cli['version'] == feed['senderVersion'])
        rig = SurfaceFixture(stage / 'source', resident, endpoint, observer_socket, claim)
        browser = launch_profile(rig, stage, 'Update fixture')
        profile = rig.profiles[0]
        rig.settings()
        rig.options()
        rig.choose('Access lifetime', 1)
        rig.choose('Desktop before starting', 2)
        rig.switch('Desktop access')
        poll(lambda: surfaces()['desktop']['mode'] == 'ask', 'Desktop Ask enabled')
        desktop = surfaces()['desktop']
        check('Desktop is on, waits for approval and expires in 15 minutes',
              desktop['consentRemainingSeconds'] is not None and 840 <= desktop['consentRemainingSeconds'] <= 900, desktop)
        rig.choose('Access lifetime', 0)
        rig.choose('Browser before starting', 1)
        rig.select_profiles([profile])
        rig.switch('Browser access')
        poll(lambda: surfaces()['browser']['mode'] == 'automatic', 'Browser Automatic enabled')
        current = surfaces()
        check('Browser is on until stopped for exactly the fixture profile',
              current['browser']['consentRemainingSeconds'] is None and current['browser']['profileIds'] == [profile], current['browser'])
        check('Desktop keeps its timed consent after Browser is enabled',
              current['desktop']['mode'] == 'ask' and current['desktop']['consentRemainingSeconds'] is not None)

        # A live approved task makes Settings ask before ending it.
        owner = rig.owner('desktop')
        snap = rig.dispatch('snapshot', provider='macos-native', target=str(browser.pid), maxDepth=8, maxElements=80)
        assert snap.get('accepted'), snap.get('errorCode')
        old_reference = next(e['reference'] for e in snap['data']['elements'] if e.get('reference'))
        check('approved Desktop task is active before updating', owner.status()['state'] == 'active')
        sender_status = status()
        desktop_end = time.time() + sender_status['data']['admission']['surfaces']['desktop']['consentRemainingSeconds']

        update, install = discover()
        check('On: Install and restart is enabled', install.get('enabled') is True)
        check('On: Settings explains the pause and automatic restoration', has_text(PAUSE_NOTE))

        def confirm():
            rig.press('Install and restart')
            return poll(lambda: button('Install anyway'), 'task confirmation', 15)

        # Tampered bytes fail signature verification before access stops.
        feed_state.tamper(True)
        confirm()
        pressed = time.time()
        rig.press('Install anyway')
        watch = watch_install(sender_status['data']['processId'])
        failed = wait(lambda: (lambda u: u if u['phase'] == 'error' else None)(update_status()), 'tampered install failure', 90)
        time.sleep(2)
        record = finish_watch(watch)
        feed_state.tamper(False)
        current = rig.status()
        check('tampered download fails without stopping access',
              current['admission']['surfaces']['desktop']['mode'] == 'ask' and
              current['admission']['surfaces']['browser']['mode'] == 'automatic' and
              all(sample.get('modes', {}).get('desktop') in (None, 'ask') for sample in record['samples']),
              failed.get('error'))
        check('tampered download leaves the same resident and task',
              current['processId'] == sender_status['data']['processId'] and owner.status()['state'] == 'active')
        check('tampered download writes no restoration plan', record['plan'] is None and not plan_path.exists())
        check('tampered download keeps the timed end',
              abs(time.time() + current['admission']['surfaces']['desktop']['consentRemainingSeconds'] - desktop_end) <= 3)
        tampered_codes = codes(pressed)
        check('tampered download records failure without an access stop',
              'update.install.failed' in tampered_codes and 'update.access.stopped' not in tampered_codes, tampered_codes)
        evidence['tampered'] = {'error': failed.get('error'), 'diagnostics': tampered_codes}

        # Cancel keeps everything; Install anyway proceeds.
        confirm()
        press_after('Install anyway', 'Cancel')
        poll(lambda: not button('Install anyway'), 'confirmation dismissed', 10)
        time.sleep(2)
        current = status()
        check('Cancel leaves the sender, access and task untouched',
              current['data']['processId'] == sender_status['data']['processId'] and
              info()['CFBundleShortVersionString'] == feed['senderVersion'] and
              current['data']['admission']['surfaces']['desktop']['mode'] == 'ask' and
              owner.status()['state'] == 'active')
        before_install = rig.status()
        before = status()
        evidence['beforeInstall'] = {k: {f: v.get(f) for f in ['mode', 'consentRemainingSeconds', 'profileIds']}
                                     for k, v in before_install['admission']['surfaces'].items()}
        confirm()
        pressed = time.time()
        rig.press('Install anyway')
        watch = watch_install(before['data']['processId'])
        after = relaunched(before['data']['processId'], before['generation'])
        record = finish_watch(watch)
        (results / 'access-install-watch.json').write_text(json.dumps(record) + '\n')
        plan = record['plan']
        check('a one-shot restoration plan was recorded before replacement',
              plan is not None and plan['targetVersion'] == feed['incomingVersion'] and record['planMode'] == '0o600', plan)
        entries = {e['surface']: e for e in plan['surfaces']}
        check('plan keeps Desktop wall-clock end and Browser until-stopped exact profile',
              set(entries) == {'desktop', 'browser'} and entries['desktop']['mode'] == 'ask' and
              abs(entries['desktop']['expiresAt'] - desktop_end) <= 3 and entries['browser']['mode'] == 'automatic' and
              entries['browser']['expiresAt'] is None and entries['browser']['profileIds'] == [profile], plan)
        old_samples = [s for s in record['samples'] if s.get('pid') == before['data']['processId'] and s.get('modes')]
        # Replacement follows Stop by about a second, faster than gentle
        # status sampling. The native audit and closed client codes order it.
        check('no old-resident sample shows live access after the plan',
              all(all(v == 'off' for v in s['modes'].values()) for s in old_samples
                  if s['t'] >= (record.get('planSeenAt') or float('inf'))), old_samples[-3:])
        sender_codes = codes(pressed, feed['senderVersion'])
        check('sender client stopped access before installing',
              'update.access.stopped' in sender_codes and 'update.install.ok' in sender_codes and
              sender_codes.index('update.access.stopped') < sender_codes.index('update.install.ok'), sender_codes)
        audit = [r for r in journal('audit', pressed) if r.get('version') == feed['senderVersion']]
        names = [r['operation'] for r in audit]
        check('sender resident audited Stop and task end before quitting for replacement',
              'control.stopped' in names and 'access.operator_quit' in names and
              names.index('control.stopped') < names.index('access.operator_quit') and
              any(r['operation'] == 'control.ended' and r.get('errorCode') == 'stopped' for r in audit), names)
        evidence['senderJournal'] = {'diagnostics': sender_codes, 'audit': names}

        def restored():
            update = update_status()
            phase = (update.get('accessResume') or {}).get('phase')
            return update if phase in ('restored', 'failed') else None
        update = wait(restored, 'updated client restores access', 150)
        restored_at = time.time()
        incoming_codes = codes(pressed, feed['incomingVersion'])
        check('updated client records restoration', 'update.access.restored' in incoming_codes and
              'update.access.restore_failed' not in incoming_codes, incoming_codes)
        evidence['incomingDiagnostics'] = incoming_codes
        check('updated client reports restoration of both surfaces',
              update['accessResume']['phase'] == 'restored' and sorted(update['accessResume']['surfaces']) == ['browser', 'desktop'],
              update['accessResume'])
        check('plan file is consumed on launch', not plan_path.exists())
        current = rig.status()['admission']['surfaces']
        desktop_remaining = current['desktop']['consentRemainingSeconds']
        drift = None if desktop_remaining is None else time.time() + desktop_remaining - desktop_end
        check('Desktop returns in the same mode with its original wall-clock end',
              current['desktop']['mode'] == 'ask' and drift is not None and abs(drift) <= 5,
              {'remaining': desktop_remaining, 'drift': drift})
        check('Browser returns until stopped for the same exact profile',
              current['browser']['mode'] == 'automatic' and current['browser']['consentRemainingSeconds'] is None and
              current['browser']['profileIds'] == [profile], current['browser'])
        open_settings_page()
        check('Settings confirms access was turned back on', has_text(RESTORED_NOTE))
        if sender_cli:
            incoming_cli = json.loads(command(cli, 'agent', 'identity').stdout)
            check('installed CLI identity is replaced with the incoming release',
                  incoming_cli['version'] == feed['incomingVersion'] and incoming_cli['version'] != sender_cli['version'])
        rig.close_owners()
        owner = rig.owner('desktop')
        stale = rig.dispatch('action', reference=old_reference, action='press')
        check('updated runtime refuses the pre-update reference',
              not stale.get('accepted') and stale.get('errorCode') == 'stale_reference', stale.get('errorCode'))
        rig.close_owners()
        owner = rig.owner('browser')
        tabs = rig.dispatch('browser.tabs')
        check('restored Browser access serves the exact profile', tabs.get('accepted') is True, tabs.get('errorCode'))
        rig.close_owners()
        rig.stop()
        check('Stop turns restored access Off', all(v['mode'] == 'off' for v in rig.status()['admission']['surfaces'].values()))
        evidence['accessCycle'] = {
            'from': feed['senderVersion'], 'to': info()['CFBundleShortVersionString'],
            'generationChanged': after['generation'] != before['generation'],
            'before': evidence['beforeInstall'],
            'after': {k: {f: v.get(f) for f in ['mode', 'consentRemainingSeconds', 'profileIds']} for k, v in current.items()},
            'desktopEndDriftSeconds': round(drift, 2),
            'restoredSecondsAfterPlan': round(restored_at - (record.get('planSeenAt') or restored_at), 1),
            'plan': {'schema': plan['schema'], 'targetVersion': plan['targetVersion'], 'mode': record['planMode'],
                     'surfaces': [{k: e[k] for k in ['surface', 'mode']} | {'timed': e['expiresAt'] is not None,
                                  'profiles': len(e['profileIds'])} for e in plan['surfaces']]},
            'accessResume': update['accessResume']}
        (results / 'summary.json').write_text(json.dumps({'passed': True, 'checks': checks,
            'checkCount': len(checks), 'evidence': evidence,
            'feedRequests': [{k: r[k] for k in ['path', 'reason', 'served']} for r in feed_state.requests()]}, indent=2) + '\n')
    except BaseException:
        with contextlib.suppress(Exception):
            (results / 'failure-status.json').write_text(json.dumps({'status': (status() or {}).get('data', {}).get('admission'),
                'update': update_status(), 'checks': checks,
                'feedRequests': [{k: r[k] for k in ['path', 'reason', 'served']} for r in feed_state.requests()]}, default=str))
        with contextlib.suppress(Exception):
            (results / 'failure-tree.json').write_text(json.dumps(rig.tree()))
        raise
    finally:
        errors = []
        if rig is not None:
            with contextlib.suppress(Exception):
                rig.close()
        if browser is not None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(browser.pid, signal.SIGTERM)
            try:
                browser.wait(10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(browser.pid, signal.SIGKILL)
                browser.wait(5)
        if mutated:
            try:
                stop_candidate()
                command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m', format(stat.S_IMODE(policy_stat.st_mode), 'o'),
                        backup / 'policy.json', policy)
                command('/usr/bin/sudo', '-n', '/usr/sbin/chown', '%d:%d' % (policy_stat.st_uid, policy_stat.st_gid), policy)
                for name, value in saved.items():
                    f = support / name
                    if value is None:
                        f.unlink(missing_ok=True)
                    else:
                        f.write_bytes(value[0])
                        f.chmod(value[1])
                for extra in sorted({p.name for p in support.iterdir()} - support_entries - {'control.sock'}):
                    path = support / extra
                    command('/bin/rm', '-rf', path)
                for index, path in enumerate(app_dirs):
                    command('/bin/rm', '-rf', path)
                    if saved_dirs[path]:
                        command('/usr/bin/ditto', backup / ('appdir-' + str(index)), path)
                if prefs.returncode == 0:
                    command('/usr/bin/defaults', 'import', 'org.machine-control.app', backup / 'preferences.plist')
                else:
                    command('/usr/bin/defaults', 'delete', 'org.machine-control.app', check=False)
                command('/bin/bash', stage / 'install-user.sh', '--app', backup / 'Original.app')
                command('/bin/launchctl', 'bootout', label, check=False)
                agent.write_bytes(original_agent)
                agent.chmod(agent_mode)
                command('/bin/launchctl', 'bootstrap', domain, agent)
                require_managed_observer(wait(status, 'original resident returned')['data'])
                assert manifest(installed) == original_manifest, 'original app bytes differ'
                assert policy.read_bytes() == original_policy and policy.stat().st_uid == policy_stat.st_uid
                assert agent.read_bytes() == original_agent
                for name, value in saved.items():
                    f = support / name
                    assert ((f.read_bytes(), stat.S_IMODE(f.stat().st_mode)) == value if value is not None
                            else not f.exists()), 'operator file differs: ' + name
                assert not plan_path.exists()
                print('Original app, policy, LaunchAgent, operator and app state restored', flush=True)
            except BaseException as error:
                errors.append('application: ' + str(error))
        if hosts_changed:
            try:
                restore = stage / 'hosts.original'
                restore.write_bytes(original_hosts)
                command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m', format(stat.S_IMODE(hosts_stat.st_mode), 'o'),
                        '-o', str(hosts_stat.st_uid), '-g', str(hosts_stat.st_gid), restore, hosts)
                command('/usr/bin/sudo', '-n', '/usr/bin/dscacheutil', '-flushcache')
                command('/usr/bin/sudo', '-n', '/usr/bin/killall', '-HUP', 'mDNSResponder', check=False)
                assert hosts.read_bytes() == original_hosts
                print('Original hosts restored', flush=True)
            except BaseException as error:
                errors.append('hosts: ' + str(error))
        if trust_added:
            try:
                remove_trust(stage, observer_socket, exchange, feed)
                assert trust_entries() == original_trust, 'certificate trust differs from baseline'
                print('Temporary fixture certificate trust removed', flush=True)
            except BaseException as error:
                errors.append('trust: ' + str(error))
        if feed_server is not None:
            (stage / 'feed/stop').touch()
            try:
                feed_server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                errors.append('fixture feed server did not exit')
        with contextlib.suppress(OSError):
            (stage / 'feed/leaf.key').unlink()
        if observer is not None:
            with contextlib.suppress(OSError, ValueError):
                exchange(observer_socket, 'server.stop')
            try:
                observer.wait(timeout=15)
            except subprocess.TimeoutExpired:
                observer.terminate()
                observer.wait(timeout=10)
        (results / 'cleanup.json').write_text(json.dumps({'restored': not errors, 'errors': errors}) + '\n')
        if errors:
            raise RuntimeError('Restoration incomplete: ' + '; '.join(errors))


class FeedState:
    """Unprivileged view of the root fixture server's tamper flag and log."""
    def __init__(self, stage):
        self.flag, self.log, self.offset = stage / 'feed/tampered', stage / 'feed/requests.jsonl', 0

    def tamper(self, value):
        self.flag.touch() if value else self.flag.unlink(missing_ok=True)

    def all(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def requests(self):
        return self.all()[self.offset:]

    def clear(self):
        self.offset = len(self.all())


def serve_feed(stage, owner):
    """Serve the production update route and archive on guest loopback."""
    import ssl
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    feed = json.loads((stage / 'feed/feed.json').read_text())
    flag, log, lock = stage / 'feed/tampered', stage / 'feed/requests.jsonl', threading.Lock()
    archive = (stage / 'feed' / feed['archiveName']).read_bytes()
    tampered = bytearray(archive)
    tampered[len(tampered) // 2] ^= 0xFF
    tampered = bytes(tampered)
    body = json.dumps(feed['response']).encode()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *_):
            pass

        def do_GET(self):
            record = {'t': time.time(), 'path': self.path, 'reason': self.headers.get('X-Check-Reason'), 'served': None}
            try:
                self.respond(record)
            finally:
                with lock, log.open('a') as stream:
                    stream.write(json.dumps(record) + '\n')

        def respond(self, record):
            if self.path == FEED_PREFIX + feed['senderVersion']:
                record['served'] = 'metadata'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith(FEED_PREFIX):
                record['served'] = 'current'
                self.send_response(204)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
            elif self.path == ARCHIVE_PREFIX + feed['archiveName']:
                bad = flag.exists()
                payload = tampered if bad else archive
                record['served'] = 'tampered' if bad else 'genuine'
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                record['served'] = 'missing'
                self.send_response(404)
                self.send_header('Content-Length', '0')
                self.end_headers()

    class V6(ThreadingHTTPServer):
        address_family = socket.AF_INET6

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(stage / 'feed/leaf.pem'), str(stage / 'feed/leaf.key'))
    servers = []
    for cls, address in [(ThreadingHTTPServer, '127.0.0.1'), (V6, '::1')]:
        server = cls((address, 443), Handler)
        server.daemon_threads = True
        server.socket = context.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
    log.touch()
    os.chmod(log, 0o644)
    (stage / 'feed/ready').touch()
    try:
        # Exit with the unprivileged guest actor or its explicit stop file.
        while not (stage / 'feed/stop').exists():
            try:
                os.kill(owner, 0)
            except ProcessLookupError:
                break
            time.sleep(.5)
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        for name in ['ready', 'stop']:
            with contextlib.suppress(OSError):
                (stage / 'feed' / name).unlink()


def remove_trust(stage, observer_socket, exchange, feed):
    """Remove admin trust through the exact SecurityAgent prompt, then the cert."""
    log = (stage / 'results/trust-removal.log').open('wb')
    process = subprocess.Popen(['/usr/bin/sudo', '-n', '/usr/bin/security', 'remove-trusted-cert', '-d',
                                str(stage / 'feed/ca.pem')], stdin=subprocess.DEVNULL, stdout=log, stderr=log)
    lease = None
    deadline = time.monotonic() + 30
    while process.poll() is None and lease is None and time.monotonic() < deadline:
        reply = exchange(observer_socket, 'authorization.begin', expectedRequester='security',
                         contextId='update-fixture-trust-' + uuid.uuid4().hex, timeoutMs=60000)
        if reply.get('accepted'):
            lease = reply['data']['leaseId']
        else:
            time.sleep(.5)
    if lease is not None:
        # The controller submits the canonical credential once; never retried.
        print('MC_CREDENTIAL_LEASE ' + json.dumps({'leaseId': lease}), flush=True)
    try:
        code = process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(10)
        raise AssertionError('Trust removal did not complete')
    log.close()
    assert code == 0, 'remove-trusted-cert failed'
    subprocess.run(['/usr/bin/sudo', '-n', '/usr/bin/security', 'delete-certificate', '-Z', feed['caSHA1'],
                    '/Library/Keychains/System.keychain'], stdin=subprocess.DEVNULL,
                   check=True, capture_output=True, timeout=30)


# --------------------------------------------------------------------------
# Controller half.
# --------------------------------------------------------------------------

def certificates(directory):
    """Create a short-lived fixture CA and update-host leaf."""
    def openssl(*args):
        subprocess.run(['openssl', *args], check=True, capture_output=True, cwd=directory)
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '2',
            '-subj', '/CN=Machine Control update fixture CA', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    openssl('req', '-newkey', 'rsa:2048', '-nodes', '-keyout', 'leaf.key', '-out', 'leaf.csr',
            '-subj', '/CN=' + HOST)
    (directory / 'leaf.ext').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n'
                                        'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:' + HOST + '\n')
    openssl('x509', '-req', '-in', 'leaf.csr', '-CA', 'ca.pem', '-CAkey', 'ca.key', '-CAcreateserial',
            '-out', 'leaf.pem', '-days', '2', '-sha256', '-extfile', 'leaf.ext')
    der = subprocess.run(['openssl', 'x509', '-in', 'ca.pem', '-outform', 'DER'], check=True,
                         capture_output=True, cwd=directory).stdout
    (directory / 'ca.key').unlink()
    return hashlib.sha1(der).hexdigest().upper()


def controller(a):
    repo = Path(__file__).resolve().parents[2]
    if a.output.resolve().is_relative_to(repo):
        raise SystemExit('Raw VM evidence must be outside the public checkout')
    if not os.environ.get('MACHINE_CONTROL_CLAIM_ID') or not os.environ.get('MACHINE_CONTROL_SCOPE_FILE'):
        raise SystemExit('Run inside a common CLI claim scope')
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    mc = [str(repo / 'bin/machine-control')]
    claim = os.environ['MACHINE_CONTROL_CLAIM_ID']

    def call(*args, **kwargs):
        return subprocess.check_output(mc + list(args), timeout=240, **kwargs)

    manifests = {}
    for role, directory in [('sender', a.sender), ('incoming', a.incoming)]:
        manifest = json.loads((directory / 'build.json').read_text())
        subprocess.run([sys.executable, str(repo / 'desktop/scripts/verify-package.py'), str(directory),
                        '--revision', manifest['sourceRevision'], '--team-id', a.team_id, '--test-tampering'], check=True)
        manifests[role] = manifest
    sender, incoming = manifests['sender'], manifests['incoming']
    version = lambda v: tuple(map(int, v.split('.')))
    assert version(sender['version']) < version(incoming['version']), 'Sender must be older than the incoming release'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    archive_name = 'MachineControl_%s_arm64.app.tar.gz' % incoming['version']
    incoming_archive = a.incoming / archive_name
    signature = (a.incoming / (archive_name + '.sig')).read_text().strip()
    trusted = [line for line in base64.b64decode(signature).decode().splitlines() if line.startswith('trusted comment: ')]
    assert len(trusted) == 1 and 'version:' + incoming['version'] in trusted[0].split('\t')
    spec = importlib.util.spec_from_file_location('release_changelog', repo / 'release/changelog.py')
    changelog = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(changelog)
    response = {'version': incoming['version'], 'notes': changelog.notes(incoming['version'], repo / 'desktop/CHANGELOG.md').strip(),
                'pub_date': time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime()),
                'url': 'https://' + HOST + ARCHIVE_PREFIX + archive_name, 'signature': signature, 'channel': 'stable'}
    (a.output / 'identity.json').write_text(json.dumps({
        'sender': {k: sender[k] for k in ['version', 'sourceRevision', 'workflowRun', 'workflowAttempt']},
        'incoming': {k: incoming[k] for k in ['version', 'sourceRevision', 'workflowRun', 'workflowAttempt']},
        'harnessRevision': head, 'harnessClean': not subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo),
        'incomingArchiveSHA256': next(v['sha256'] for v in incoming['artifacts'] if v['name'] == archive_name)}, indent=2) + '\n')

    doctor = subprocess.run(mc + ['target', 'doctor'], capture_output=True, timeout=90)
    initial = json.loads(doctor.stdout)['states']['power']
    remote = '/tmp/mc-update-' + uuid.uuid4().hex[:16]
    staged = False
    summary = None
    with tempfile.TemporaryDirectory(prefix='mc-update-stage-') as temporary:
        root = Path(temporary)
        sender_archive = a.sender / ('MachineControl_%s_arm64.app.tar.gz' % sender['version'])
        with tarfile.open(sender_archive) as archive:
            archive.extractall(root / 'sender', filter='data')
        sender_app = root / 'sender/Machine Control.app'
        assert plistlib.loads((sender_app / 'Contents/Info.plist').read_bytes())['CFBundleShortVersionString'] == sender['version']
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(sender_app)], check=True)
        tls = root / 'tls'
        tls.mkdir(mode=0o700)
        ca_sha1 = certificates(tls)
        feed = {'senderVersion': sender['version'], 'incomingVersion': incoming['version'],
                'revision': incoming['sourceRevision'], 'archiveName': archive_name, 'caSHA1': ca_sha1,
                'response': response}
        staging = root / 'inputs.tar'
        with tarfile.open(staging, 'w') as tar:
            tar.add(sender_app, arcname='sender/Machine Control.app')
            tar.add(incoming_archive, arcname='feed/' + archive_name)
            for name in ['ca.pem', 'leaf.pem', 'leaf.key']:
                tar.add(tls / name, arcname='feed/' + name)
            (root / 'feed.json').write_text(json.dumps(feed))
            tar.add(root / 'feed.json', arcname='feed/feed.json')
            tar.add(Path(__file__).resolve(), arcname='tauri-update.py')
            tar.add(repo / 'platforms/macos/resident/scripts/install-user.sh', arcname='install-user.sh')
            for name in ['tests/macos/surface_fixture.py', 'tests/macos/surface-policy-live.py', 'platforms/chromeos/cdp.py']:
                tar.add(repo / name, arcname='source/' + name)
        try:
            call('target', 'up')
            assert json.loads(call('target', 'doctor'))['ready'], 'Guest doctor is not ready'
            call('testbed', '--', 'exec', '/bin/mkdir', '-m', '700', remote)
            staged = True
            with staging.open('rb') as stream:
                call('testbed', '--', 'exec', '-i', '/usr/bin/tar', '-xf', '-', '-C', remote, stdin=stream)
            attempted = False
            proc = subprocess.Popen(mc + ['os', '--', '/usr/bin/python3', remote + '/tauri-update.py',
                                          '--guest-stage', remote, '--claim', claim],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                with (a.output / 'guest.log').open('wb') as log:
                    for line in proc.stdout:
                        if line.startswith(b'MC_CREDENTIAL_LEASE '):
                            assert not attempted, 'Repeated credential request'
                            lease = json.loads(line[len(b'MC_CREDENTIAL_LEASE '):])
                            assert set(lease) == {'leaseId'} and re.fullmatch(r'[0-9A-Za-z:._-]{8,200}', lease['leaseId'])
                            fd = os.open(a.admin_secret_file, os.O_RDONLY | os.O_NOFOLLOW)
                            with os.fdopen(fd, 'rb') as secret:
                                st = os.fstat(secret.fileno())
                                assert stat.S_ISREG(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o600
                                assert st.st_uid == os.getuid() and st.st_nlink == 1 and 0 < st.st_size <= 4096
                                attempted = True
                                reply = json.loads(call('testbed', '--', 'exec', '-i',
                                    remote + '/backup/Original.app/Contents/MacOS/macui', 'credential',
                                    remote + '/observer/control.sock', lease['leaseId'], stdin=secret))
                            assert reply.get('accepted') and reply.get('effect') == 'confirmed', 'Credential effect uncertain; no retry'
                            line = b'Trust-settings authorization delivered through the one-shot transport\n'
                        log.write(line)
                        log.flush()
                        sys.stdout.buffer.write(line)
                        sys.stdout.flush()
                assert proc.wait(timeout=30) == 0, 'Guest update campaign failed'
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=60)
            summary = json.loads(call('os', '--', '/bin/cat', remote + '/results/summary.json'))
            (a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        except BaseException:
            subprocess.run(mc + ['usage', 'note', '--kind', 'friction', '--goal', 'Packaged update access restoration'],
                           input=b'Update acceptance failed; inspect controller-private evidence and cleanup status.\n',
                           stdout=subprocess.DEVNULL, timeout=30, check=False)
            raise
        finally:
            try:
                if staged:
                    with (a.output / 'guest-results.tar').open('wb') as stream:
                        subprocess.run(mc + ['os', '--', '/usr/bin/tar', '-cf', '-', '-C', remote, 'results'],
                                       stdout=stream, check=False, timeout=90)
                    cleanup = json.loads(call('os', '--', '/bin/cat', remote + '/results/cleanup.json'))
                    (a.output / 'cleanup.json').write_text(json.dumps(cleanup) + '\n')
                    if not cleanup['restored']:
                        raise RuntimeError('Guest restoration incomplete; private backups retained at ' + remote)
                    call('os', '--', '/bin/rm', '-rf', remote)
            finally:
                if initial == 'suspended':
                    call('target', 'suspend')
                elif initial == 'off':
                    call('target', 'shutdown')
    print('Update acceptance passed %d checks; original guest state and power restored' % summary['checkCount'], flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--guest-stage', type=Path, help=argparse.SUPPRESS)
    p.add_argument('--serve-feed', type=Path, help=argparse.SUPPRESS)
    p.add_argument('--owner-pid', type=int, help=argparse.SUPPRESS)
    p.add_argument('--claim', help=argparse.SUPPRESS)
    p.add_argument('--sender', type=Path, help='Authenticated older candidate package directory')
    p.add_argument('--incoming', type=Path, help='Authenticated incoming candidate package directory')
    p.add_argument('--team-id', help='Expected publisher team')
    p.add_argument('--admin-secret-file', type=Path, help='Canonical owner-only appliance credential')
    p.add_argument('--output', type=Path, help='New private evidence directory outside the checkout')
    a = p.parse_args()
    if a.serve_feed:
        serve_feed(a.serve_feed, a.owner_pid)
        return
    if a.guest_stage:
        guest(a.guest_stage, a.claim)
        return
    if not (a.sender and a.incoming and a.team_id and a.admin_secret_file and a.output):
        p.error('--sender, --incoming, --team-id, --admin-secret-file and --output are required')
    controller(a)


if __name__ == '__main__':
    main()

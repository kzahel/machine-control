#!/usr/bin/env python3
"""Development-package cold-boot preference check in a disposable VirtualMac.

Run under the common CLI's isolated, discard-on-release workspace. The guest
deliberately leaves the candidate installed for disposal: this is not an
in-place appliance upgrade or a release receipt. No outer UI is used.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tarfile
import time
import uuid


def wait(fn, label, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.3)
    raise AssertionError(label)


def guest(stage, claim, verify):
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).startswith(b'VirtualMac')
    home = Path.home()
    installed = home / 'Applications/Machine Control.app'
    endpoint = home / 'Library/Application Support/MachineControl/control.sock'
    policy = Path('/Library/Application Support/MachineControl/policy.json')
    # Durable staging can exceed sockaddr_un's path limit. Only this private
    # socket directory is ephemeral and recreated on each side of the reboot.
    observer_socket = Path('/tmp/mc-rb-'+stage.name[-16:]) / 'control.sock'
    observer_socket.parent.mkdir(mode=0o700,exist_ok=True)
    service_label = 'gui/' + str(os.getuid()) + '/org.machine-control.resident'

    def command(*args, check=True):
        return subprocess.run([str(v) for v in args], check=check, capture_output=True, timeout=90)

    def exchange(path, operation, **fields):
        try:
            with socket.socket(socket.AF_UNIX) as channel:
                channel.settimeout(15); channel.connect(str(path))
                channel.sendall(json.dumps(dict(operation=operation, claimId=claim, **fields)).encode() + b'\n')
                result = json.loads(channel.makefile('rb').readline(32 * 1024 * 1024))
                if operation == 'status' and result.get('errorCode') in {'control_generation_changed','locked_use_interrupted'}:
                    return None
                assert result.get('accepted'), result.get('errorCode')
                return result.get('data', {})
        except (OSError, ValueError):
            return None

    def status(path=endpoint):
        return exchange(path, 'status')

    def select_policy(preset):
        value = stage / (preset + '.json')
        value.write_text(json.dumps({'schema':'machine-control-policy/v0', 'preset':preset}))
        command('/usr/bin/sudo','-n','/usr/bin/install','-m','644',value,policy)

    boot = subprocess.check_output(['sysctl','-n','kern.boottime']).decode().strip()
    if not verify:
        assert wait(status, 'Original resident unavailable')['deployment']['policy']['grantMode'] == 'standing'
        command('/usr/bin/ditto', installed, stage / 'Original.app')
    else:
        saved = json.loads((stage / 'preboot.json').read_text())
        assert boot != saved['boot'], 'No actual guest reboot observed'
        current = wait(status, 'Candidate did not return after reboot')
        assert current['deployment']['policy']['grantMode'] == 'approval'
        assert exchange(endpoint, 'grant.status')['grant'] is None, 'Pre-boot approval survived reboot'

    # The standing appliance observer is independent of the candidate. On the
    # post-boot pass the candidate has already loaded workstation policy; only
    # the observer loads the temporary appliance policy. Restore it immediately.
    observer = None
    try:
        if verify:
            select_policy('appliance')
        observer_socket.unlink(missing_ok=True)
        with (stage / ('observer-post.log' if verify else 'observer-pre.log')).open('wb') as log:
            observer = subprocess.Popen([str(stage / 'Original.app/Contents/MacOS/macui'),
                'serve', str(observer_socket)], stdout=log, stderr=log)
        assert wait(lambda:status(observer_socket), 'Independent observer unavailable')['deployment']['policy']['grantMode'] == 'standing'
    finally:
        select_policy('workstation')
    try:
        if not verify:
            exchange(endpoint, 'server.stop')
            command('/bin/launchctl','bootout',service_label,check=False)
            wait(lambda:status() is None, 'Original endpoint still running')
            endpoint.unlink(missing_ok=True)
            for name in ['operator-consent.json', 'presentation.json']:
                (endpoint.parent / name).unlink(missing_ok=True)
            command('/bin/bash', stage / 'install-user.sh', '--app', stage / 'candidate/Machine Control.app')
        current = wait(status, 'Candidate unavailable')
        assert current['deployment']['policy']['grantMode'] == 'approval'
        pid = current['processId']
        command(installed / 'Contents/MacOS/macui', 'serve', endpoint, '--settings')

        def find(label, role):
            tree = exchange(observer_socket, 'snapshot', target=str(pid), query=label,
                            projection='full', maxDepth=40, maxElements=2000, provider='macos-native')
            rows = [e for e in tree['elements'] if e.get('label') == label and e.get('role') == role]
            return rows[0] if len(rows) == 1 else None

        def press(label, role='AXButton'):
            row = wait(lambda:find(label,role), 'Missing operator control: ' + label)
            return exchange(observer_socket,'action',reference=row['reference'],action='press',provider='macos-native')

        def browser_preference(check_only):
            press('Settings')
            row = wait(lambda:find('Allow approved browser access while locked','AXCheckBox'),
                       'Missing browser preference')
            checked = str(row.get('value')).lower() in {'true','1'}
            if check_only:
                assert checked, 'Browser preference reset across restart'
            elif not checked:
                exchange(observer_socket,'action',reference=row['reference'],action='press',provider='macos-native')
            assert wait(lambda:(status() or {}).get('browserWhileLocked',{}).get('enabled'),
                        'Browser preference did not become enabled')
            press('Access')

        press('Access')
        labels = ['View desktop','Control apps and input','Browser tabs','Browser scripts and DevTools']
        for label in labels:
            row = wait(lambda:find(label,'AXCheckBox'), 'Missing remembered scope')
            checked = str(row.get('value')).lower() in {'true','1'}
            if verify:
                assert checked, 'Scope choice reset after reboot: ' + label
            elif not checked:
                exchange(observer_socket,'action',reference=row['reference'],action='press',provider='macos-native')
        if not verify:
            exchange(observer_socket,'application.activate',target=str(pid),provider='macos-native')
            press('Access duration','AXPopUpButton')
            for key in ['u','enter']:
                exchange(observer_socket,'input.key',target=str(pid),key=key,provider='macos-native')
            browser_preference(False)
            press('Enable access')
            grant = wait(lambda:(exchange(endpoint,'grant.status') or {}).get('grant'), 'Indefinite approval unavailable')
            assert grant['lifetime'] == 'until_stopped' and set(grant['scopes']) == {'observe','control','browser','devtools'}
            press('Stop access')
            wait(lambda:exchange(endpoint,'grant.status')['grant'] is None,'Stop did not clear approval')
            old_pid = pid
            exchange(observer_socket,'application.terminate',target=str(pid),provider='macos-native')
            wait(lambda:command('/bin/kill','-0',str(old_pid),check=False).returncode != 0,'Clean exit unavailable')
            command('/bin/launchctl','kickstart',service_label)
            def restarted():
                value = status()
                return value if value and value.get('processId') not in {None,old_pid} else None
            current = wait(restarted,'Clean restart unavailable')
            pid = current['processId']
            assert exchange(endpoint,'grant.status')['grant'] is None
            command(installed/'Contents/MacOS/macui','serve',endpoint,'--settings')
            press('Access')
            for label in labels:
                assert str(wait(lambda:find(label,'AXCheckBox'),'Scope choice after Stop/relaunch').get('value')).lower() in {'true','1'}
            assert 'Until' in str(wait(lambda:find('Access duration','AXPopUpButton'),'Duration after Stop/relaunch').get('value'))
            browser_preference(True)
            print('Visible choices survive unlocked Stop and clean relaunch with approval Off',flush=True)
            press('Enable access')
            grant = wait(lambda:(exchange(endpoint,'grant.status') or {}).get('grant'),'Preboot approval unavailable')
            assert grant['lifetime'] == 'until_stopped' and set(grant['scopes']) == {'observe','control','browser','devtools'}
            (stage / 'preboot.json').write_text(json.dumps({'boot':boot,'stopCleanRelaunch':True}))
            (stage / 'preboot.json').chmod(0o600)
            print('Actual native indefinite approval and all four scopes saved before reboot',flush=True)
        else:
            row = wait(lambda:find('Access duration','AXPopUpButton'), 'Duration unavailable after reboot')
            assert 'Until' in str(row.get('value')), row.get('value')
            browser_preference(True)
            assert exchange(endpoint,'grant.status')['grant'] is None
            report = {'actualReboot':True,'rememberedScopes':4,'rememberedDuration':0,
                      'authorizationRestored':False,'policy':'workstation','stopCleanRelaunch':saved['stopCleanRelaunch'],
                      'browserWhileLockedRemembered':True}
            (stage / 'reboot-choices.json').write_text(json.dumps(report))
            print(json.dumps(report),flush=True)
    finally:
        select_policy('workstation')
        if observer:
            exchange(observer_socket,'server.stop')
            try:
                observer.wait(timeout=10)
            except subprocess.TimeoutExpired:
                observer.terminate(); observer.wait(timeout=10)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--guest-stage', type=Path)
    p.add_argument('--verify', action='store_true')
    p.add_argument('--claim')
    p.add_argument('--app', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--admin-secret-file', type=Path)
    a = p.parse_args()
    if a.guest_stage:
        guest(a.guest_stage, a.claim, a.verify)
        return
    if not a.app or not a.output or not a.admin_secret_file or not os.environ.get('MACHINE_CONTROL_WORKSPACE_HANDLE'):
        p.error('--app/--output/--admin-secret-file and an isolated common claim scope are required')
    repo = Path(__file__).resolve().parents[2]
    assert not a.output.resolve().is_relative_to(repo)
    scope = json.loads(Path(os.environ['MACHINE_CONTROL_SCOPE_FILE']).read_text())
    mc = [str(repo / 'bin/machine-control')]
    env = {k:v for k,v in os.environ.items() if k not in {'MACHINE_CONTROL_SCOPE_FILE','MACHINE_CONTROL_WORKSPACE_HANDLE'}}
    inventory = json.loads(subprocess.check_output(mc+['--registry',scope['registry'],'--target',scope['target'],'workspace','inventory'],env=env,timeout=45))
    row = next(w for w in inventory['data']['workspaces'] if w['handle'] == scope['workspace'])
    assert row['intent'] == 'isolated' and row['retention'] == 'discardOnRelease'
    a.output.mkdir(mode=0o700,parents=True,exist_ok=False)
    remote = None
    def call(*args, check=True, **kwargs):
        return subprocess.run(mc+list(args),check=check,timeout=120,**kwargs)
    try:
        call('target','up')
        guest_home = call('testbed','--','exec','/usr/bin/printenv','HOME',capture_output=True).stdout.decode().strip()
        assert guest_home.startswith('/') and '\n' not in guest_home and guest_home != '/'
        remote = guest_home+'/Library/Application Support/MachineControl/reboot-acceptance-'+uuid.uuid4().hex
        call('testbed','--','exec','mkdir','-m','700',remote)
        archive = a.output / 'inputs.tar'
        with tarfile.open(archive,'w') as tar:
            tar.add(a.app,arcname='candidate/Machine Control.app')
            tar.add(__file__,arcname='reboot-choices.py')
            tar.add(repo/'tests/macos/verify-appliance-credential.swift',arcname='verify-credential.swift')
            tar.add(repo/'platforms/macos/resident/scripts/install-user.sh',arcname='install-user.sh')
        with archive.open('rb') as stream:
            call('testbed','--','exec','-i','tar','-xf','-','-C',remote,stdin=stream)
        tool = remote+'/verify-credential'
        call('testbed','--','exec','xcrun','swiftc',remote+'/verify-credential.swift','-o',tool)
        probe = json.loads(call('testbed','--','exec',tool,'--preflight',capture_output=True).stdout)
        assert probe == {'schema':'machine-control-appliance-credential-check/v0','code':'ready','verified':False}
        fd = os.open(a.admin_secret_file,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as secret:
            info = os.fstat(secret.fileno())
            assert stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600
            assert info.st_uid == os.getuid() and info.st_nlink == 1 and 0 < info.st_size <= 4096
            verified = json.loads(call('testbed','--','exec','-i',tool,'--verify',stdin=secret,capture_output=True).stdout)
        assert verified.get('verified') is True, 'Canonical appliance credential verification failed; no retry'
        (a.output/'credential-check.json').write_text(json.dumps(verified))
        args = ['testbed','--','exec','/usr/bin/python3',remote+'/reboot-choices.py','--guest-stage',remote,'--claim',scope['claim']]
        call(*args)
        before = json.loads(call('testbed','--','exec','cat',remote+'/preboot.json',capture_output=True).stdout)['boot']
        # Submit one guest-local one-shot job before losing the transport.
        # Submission is paired in the journal; changed kernel boot time below
        # is the independent effect oracle. Never replay an uncertain submit.
        job = 'org.machine-control.acceptance-reboot.' + uuid.uuid4().hex
        call('testbed','--','exec','/bin/launchctl','submit','-l',job,'--','/bin/sh','-c',
             'sleep 3; exec /usr/bin/sudo -n /sbin/shutdown -r now')
        def returned():
            result = call('testbed','--','exec','/usr/sbin/sysctl','-n','kern.boottime',check=False,capture_output=True)
            return result.returncode == 0 and result.stdout.decode().strip() != before
        wait(returned,'Guest did not return after reboot',seconds=180)
        call(*args,'--verify')
        with (a.output/'reboot-choices.json').open('wb') as stream:
            call('testbed','--','exec','cat',remote+'/reboot-choices.json',stdout=stream)
    finally:
        # This verified discard-on-release workspace is controller-owned.
        # Bound its lifecycle explicitly; guest sudo timestamp availability is
        # not the credential handoff or the workspace-disposal authority.
        call('testbed','--','stop',check=False)


if __name__ == '__main__':
    main()

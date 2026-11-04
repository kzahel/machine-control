#!/usr/bin/env python3
"""Covered v2 composition inside an exact claimed candidate VirtualMac.

The controller owns root-policy preflight/restore, stored one-shot secret
transport, app installation, final normal reboot/shutdown and claim cleanup.
This actor owns the native fixture and uses real operator UI, not a test inlet.
It can leave the console locked; the controller must complete cleanup.
"""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import socket
import subprocess
import time
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observer-socket',required=True,type=Path)
    parser.add_argument('--source-root',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    parser.add_argument('--claim',required=True)
    args=parser.parse_args()
    assert subprocess.check_output(['sysctl','-n','hw.model']).decode().startswith('VirtualMac')
    spec=importlib.util.spec_from_file_location('surface_actor',args.source_root/'tests/macos/surface-policy-live.py')
    actor=importlib.util.module_from_spec(spec);spec.loader.exec_module(actor)
    poll=actor.poll
    endpoint=Path.home()/'Library/Application Support/MachineControl/control.sock'
    app=Path.home()/'Applications/Machine Control.app'
    resident=app/'Contents/MacOS/macui'
    root=args.report.parent
    checks=[]
    fixture=None
    observer_owner=None

    def check(label,condition=True):
        assert condition,label
        checks.append(label);print('PASS: '+label,flush=True)

    def exchange(path,operation,**fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(30);channel.connect(str(path))
            channel.sendall(json.dumps(dict(operation=operation,claimId=args.claim,**fields)).encode()+b'\n')
            return json.loads(channel.makefile('rb').readline(16*1024*1024))

    def status():
        # A read that straddles relock may lose its native observation epoch.
        # Repeat discovery only; effect requests are never retried.
        def observed():
            result=exchange(endpoint,'status')
            if result.get('errorCode')=='control_generation_changed':return None
            assert result.get('accepted'),result.get('errorCode')
            return result['data']
        return poll(observed,'stable native status',5)

    def observe(operation,**fields):
        nonlocal observer_owner
        if observer_owner is None:
            result=exchange(args.observer_socket,operation,provider='macos-native',**fields)
            if result.get('errorCode')!='control_session_required':
                assert result.get('accepted'),result.get('errorCode');return result.get('data',{})
            assert result.get('delivery')=='refused' and result.get('uncertainty')=='none'
            observer_owner=actor.Owner(args.observer_socket,args.claim,['desktop'],duration=900)
        if observer_owner.status()['state']!='active':observer_owner.wait()
        result=observer_owner.call(operation,provider='macos-native',**fields)
        assert result.get('accepted'),result.get('errorCode');return result.get('data',{})

    pid=status()['processId']
    def tree(query='',target=None):
        return observe('snapshot',target=str(target or pid),query=query,projection='full',maxDepth=40,maxElements=2000)['elements']

    def find(label,role='AXButton'):
        rows=[row for row in tree(label) if label in [row.get('label'),row.get('title'),row.get('description')] and row.get('role')==role]
        rows.sort(key=lambda row:row.get('depth',1000))
        return rows[0] if rows and (len(rows)==1 or rows[0].get('depth')!=rows[1].get('depth')) else None

    def press(label,role='AXButton'):
        row=poll(lambda:find(label,role),'operator '+label)
        observe('action',reference=row['reference'],action='press')

    def choose(label,index):
        observe('application.activate',target=str(pid));press(label,'AXPopUpButton')
        for key in {0:['home','enter'],1:['home','down','enter'],2:['end','enter']}[index]:
            observe('input.key',key=key)
        time.sleep(.3)

    def locked():
        rows=plistlib.loads(subprocess.check_output(['ioreg','-a','-l','-d','1']))
        value=(rows[0] if isinstance(rows,list) else rows).get('IOConsoleLocked')
        assert isinstance(value,bool),'Independent lock observation unavailable'
        return value

    def oracle():
        value=json.loads(state.read_text());assert value['pid']==fixture.pid;return value

    def accepted(value):
        assert value.get('accepted'),value.get('errorCode');return value.get('data',{})

    try:
        initial=status()
        assert initial['desktopState']=='unlocked' and initial['unlock']['installation']=='missing'
        assert all(value['mode']=='off' for value in initial['admission']['surfaces'].values())
        subprocess.run([str(resident),'serve',str(endpoint),'--settings'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
        press('Permissions');press('Set up Machine Control helper')
        approval_attempted=False
        def prepared():
            nonlocal approval_attempted
            current=status()['lockedUse']
            if current['setupState']=='approval' and current['helperApproval']=='requires_approval' and not approval_attempted:
                approval_attempted=True
                def switch():
                    rows=[row for row in tree('', 'com.apple.systempreferences') if row.get('role') in {'AXCheckBox','AXSwitch'}
                          and row.get('label')=='Machine Control' and str(row.get('value','')).lower() in {'0','false'}]
                    return rows[0] if len(rows)==1 else None
                row=poll(switch,'exact native helper approval switch')
                observe('action',reference=row['reference'],action='press')
                lease=poll(lambda:exchange(args.observer_socket,'authorization.begin',expectedRequester='Login Items',
                    contextId='surface-helper-'+uuid.uuid4().hex,timeoutMs=120000).get('data',{}).get('leaseId'),
                    'strict native credential lease',15)
                print('MC_CREDENTIAL_LEASE '+json.dumps({'leaseId':lease}),flush=True)
            if current['permissionReady']:
                return current
            if current['setupState']=='idle' and current['setupError']:
                raise AssertionError('Helper preparation refused: '+current['setupError'])
            return None
        ready=poll(prepared,'native helper and capture preparation',180)
        check('real Permissions prepares the production protected helper',ready['helperHealthy'])
        check('helper preparation does not arm ordinary control',all(value['mode']=='off' for value in status()['admission']['surfaces'].values()))
        press('Access');press('Allow prepared tasks behind an opaque cover','AXCheckBox')
        poll(lambda:status()['lockedUse']['enabled'],'operator enables covered tasks')
        choose('Desktop access mode',2)
        poll(lambda:status()['admission']['surfaces']['desktop']['mode']=='automatic','Desktop Automatic consent')
        check('protected preference and ordinary Desktop consent are separate',status()['admission']['surfaces']['browser']['mode']=='off')

        binary=root/'native-fixture'
        subprocess.run(['xcrun','swiftc',str(args.source_root/'platforms/macos/guests/macos/fixture/MachineControlFixture.swift'),'-o',str(binary)],check=True,capture_output=True,timeout=100)
        state=root/'fixture-state/state.json'
        fixture=subprocess.Popen([str(binary)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
            env={**os.environ,'MC_FIXTURE_LEFT_EDGE':'1','MC_FIXTURE_DIRECTORY':str(state.parent)})
        poll(lambda:state.exists() and json.loads(state.read_text()).get('pid')==fixture.pid,'owned native fixture')
        observe('window.close',target=str(pid))
        lock_binary=root/'native-lock'
        subprocess.run(['xcrun','clang','-fobjc-arc','-framework','Foundation','-framework','IOKit',
            str(args.source_root/'tests/macos/session-lock.m'),'-o',str(lock_binary)],check=True,capture_output=True,timeout=60)
        subprocess.run([str(lock_binary),'--lock'],check=True,capture_output=True,timeout=15)
        poll(locked,'independent initial native lock')
        sessions=[]
        for number in [1,2]:
            before=oracle()['count']
            with actor.Owner(endpoint,args.claim,['desktop']) as owner:
                active=owner.wait();sessions.append(active['sessionId'])
                # Submit exactly once immediately after acceptance. The native
                # adapter must hold it through guard preparation, not send a
                # transient busy/refusal back for an agent to retry.
                snapshot=accepted(owner.call('snapshot',provider='macos-native',target=str(fixture.pid),maxDepth=8,maxElements=500))
                check('covered task '+str(number)+' holds its first observation until native readiness')
                poll(lambda:status()['lockedUse']['phase']=='active','covered activation',60)
                check('covered task '+str(number)+' unlocks the same console behind a guard',not locked() and status()['lockedUse']['coveredDisplays']>0)
                cover_tool=root/'cover-observation'
                if not cover_tool.exists():
                    subprocess.run(['xcrun','swiftc',str(args.source_root/'tests/macos/cover-observation.swift'),'-o',str(cover_tool)],check=True,capture_output=True,timeout=90)
                actual_display=observe('capture',scope='display')
                image=Path(actual_display['artifactPath'])
                private_image=root/('unfiltered-cover-'+str(number)+'.png')
                private_image.write_bytes(image.read_bytes());private_image.chmod(0o600);image.unlink()
                inspected=subprocess.run([str(cover_tool),str(private_image)],capture_output=True,text=True,timeout=30)
                visual=json.loads(inspected.stdout)
                check('covered task '+str(number)+' independently conceals the real display',inspected.returncode==0 and visual['sampledConcealment'])
                button=next(row for row in snapshot['elements'] if row.get('identifier')=='fixture.increment' or row.get('label')=='Increment')
                accepted(owner.call('action',provider='macos-native',reference=button['reference'],action='press'))
                poll(lambda:oracle()['count']==before+1,'independent protected fixture effect',5)
                check('covered task '+str(number)+' has exactly one native fixture effect',oracle()['count']==before+1)
                captured=accepted(owner.call('capture',provider='macos-native',target=str(fixture.pid)))
                artifact=Path(captured['artifactPath'])
                saved=root/('underlying-fixture-'+str(number)+'.png')
                saved.write_bytes(artifact.read_bytes());saved.chmod(0o600);artifact.unlink()
                check('covered task '+str(number)+' captures its owned underlying fixture')
                if number==2:
                    # The actual registered native Stop shortcut, delivered by
                    # the independent operator observer, remains usable covered.
                    observe('input.key',key='ctrl-alt-cmd-.')
                    poll(lambda:owner.status()['state']=='ended','native hotkey ends owner')
            poll(locked,'independent relock',45)
            poll(lambda:status()['lockedUse']['controlSessionId'] is None,'native helper cleanup')
            check('covered task '+str(number)+' independently relocks and releases its guard',status()['lockedUse']['coveredDisplays']==0)
            if number==1:
                check('ordinary consent survives normal protected completion',status()['admission']['surfaces']['desktop']['mode']=='automatic')
        check('successive protected tasks have distinct shared owner sessions',len(set(sessions))==2)
        check('native Stop turns both surfaces Off',all(value['mode']=='off' for value in status()['admission']['surfaces'].values()))
        args.report.write_text(json.dumps({'passed':True,'checks':checks,'checkCount':len(checks),
            'protectedFixtureEffects':oracle()['count'],'physicalHidQualification':False,'onlineDisplays':status()['lockedUse']['onlineDisplays']})+'\n')
    except BaseException:
        with contextlib.suppress(Exception):
            args.report.with_name('covered-failure-state.json').write_text(json.dumps(status())+'\n')
            args.report.with_name('covered-failure-tree.json').write_text(json.dumps(tree(''))+'\n')
        raise
    finally:
        if observer_owner is not None:observer_owner.close()
        if fixture:
            fixture.terminate()
            try:fixture.wait(timeout=10)
            except subprocess.TimeoutExpired:fixture.kill();fixture.wait(timeout=5)
            state.unlink(missing_ok=True)


if __name__=='__main__':
    main()

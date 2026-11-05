"""Actual Settings, protected Stop and cold boot for the v2 release contract."""
import contextlib
import json
import os
from pathlib import Path
import signal
import subprocess
from surface_fixture import SurfaceFixture,launch_profile,poll


def run(stage,claim,observer_socket,verify,boot,saved,protected_stop=False):
    resident=Path.home()/'Applications/Machine Control.app/Contents/MacOS/macui'
    endpoint=Path.home()/'Library/Application Support/MachineControl/control.sock'
    rig=SurfaceFixture(stage/'source',resident,endpoint,observer_socket,claim)
    browser=None
    try:
        if protected_stop:
            assert not verify
            report=stage/'protected-stop.json'
            subprocess.run(['/usr/bin/python3',str(stage/'source/tests/macos/surface-covered-live.py'),'--source-root',str(stage/'source'),'--observer-socket',str(observer_socket),'--claim',claim,'--report',str(report)],check=True)
            value=json.loads(report.read_text());assert value['passed'] and value['checkCount']>=18
            assert all(v['mode']=='off' for v in rig.status()['admission']['surfaces'].values())
            print('Actual native Stop ended an active protected owner and independently relocked',flush=True)
            return
        rig.settings()
        if not verify:
            browser=launch_profile(rig,stage)
            rig.arm('ask',('desktop',));rig.arm('automatic',('browser',))
            assert rig.status()['admission']['surfaces']['desktop']['mode']=='ask'
            assert rig.status()['admission']['surfaces']['browser']['profileIds']==rig.profiles
            rig.press('Settings')
            row=poll(lambda:rig.find('Allow approved browser access while locked','AXCheckBox'),'locked Browser setting')
            if str(row.get('value','')).lower() not in {'1','true'}:rig.observe('action',reference=row['reference'],action='press')
            rig.press('Access');rig.stop()
            old=rig.status()['processId']
            rig.observe('application.terminate',target=str(old))
            poll(lambda:subprocess.run(['/bin/kill','-0',str(old)],capture_output=True).returncode!=0,'clean candidate exit')
            subprocess.run(['/bin/launchctl','kickstart','gui/'+str(os.getuid())+'/org.machine-control.resident'],check=True,capture_output=True)
            def restarted():
                try:value=rig.status()
                except (OSError,ValueError):return None
                return value if value['processId']!=old else None
            poll(restarted,'clean candidate relaunch');rig.settings()
            visible_choices(rig)
            assert all(v['mode']=='off' for v in rig.status()['admission']['surfaces'].values())
            # Explicitly re-enable real consent before boot, distinguishing
            # saved choices from authority that must not survive the reboot.
            rig.press('Enable Ask first for desktop')
            poll(lambda:rig.status()['admission']['surfaces']['desktop']['mode']=='ask','preboot Desktop consent')
            rig.press('Enable Automatic for browser')
            poll(lambda:rig.status()['admission']['surfaces']['desktop']['mode']=='ask' and rig.status()['admission']['surfaces']['browser']['mode']=='automatic','preboot surface consent')
            evidence=dict(boot=boot,stopCleanRelaunch=True,profileIds=rig.profiles,desktopChoice='ask',browserChoice='automatic')
            assert json.loads((stage/'protected-stop.json').read_text())['passed']
            (stage/'preboot.json').write_text(json.dumps(evidence));(stage/'preboot.json').chmod(0o600)
            print('Real surface consent saved before boot; form choices remain distinct',flush=True)
        else:
            visible_choices(rig)
            assert all(v['mode']=='off' for v in rig.status()['admission']['surfaces'].values())
            profiles=rig.status()['browser']['profiles']
            for identifier in saved['profileIds']:
                current=next((p for p in profiles if p['profileId']==identifier and p['enabled']),None)
                label='Allow profile '+current['name'] if current else 'Unavailable profile · '+identifier[-8:]
                row=poll(lambda:rig.find(label,'AXCheckBox'),'remembered exact profile choice')
                assert str(row.get('value','')).lower() in {'1','true'}
            result=dict(actualReboot=True,rememberedSurfaces=2,rememberedDuration=0,authorizationRestored=False,policy='workstation',stopCleanRelaunch=saved['stopCleanRelaunch'],browserWhileLockedRemembered=True,protectedStopNative=True)
            (stage/'reboot-choices.json').write_text(json.dumps(result));print(json.dumps(result),flush=True)
    finally:
        rig.close()
        if browser is not None:
            with contextlib.suppress(ProcessLookupError):os.killpg(browser.pid,signal.SIGTERM)
            try:browser.wait(10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):os.killpg(browser.pid,signal.SIGKILL)
                browser.wait(5)


def visible_choices(rig):
    rig.settings()
    for label in ['Enable Ask first for desktop','Enable Automatic for browser']:
        assert poll(lambda:rig.find(label),'remembered '+label)
    duration=poll(lambda:rig.find('Access lifetime','AXPopUpButton'),'remembered access lifetime')
    assert 'Until' in str(duration.get('value')),duration.get('value')
    rig.press('Settings')
    row=poll(lambda:rig.find('Allow approved browser access while locked','AXCheckBox'),'remembered locked Browser preference')
    assert str(row.get('value','')).lower() in {'1','true'}
    rig.press('Access')

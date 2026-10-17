#!/usr/bin/env python3
"""Provision and independently verify the fixture on one explicit test phone.

Requires the existing debug YA Android host and its staged Alpine payload,
stopped before testing. Temporary accessibility enablement is restored in
finally; other services and debugging listeners are preserved.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
APP = 'dev.machinecontrol.android.spike'
HOST = 'com.yepanywhere.host.experimental'
COMPONENT = APP + '/.ResidentService'


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--serial', required=True)
    p.add_argument('--apk', type=Path, default=HERE/'app/build/outputs/apk/debug/app-debug.apk')
    p.add_argument('--replace-spike', action='store_true', help='Explicitly replace this fixture APK only')
    args = p.parse_args()
    adb = ['adb','-s',args.serial]
    run_id = uuid.uuid4().hex
    workspace = 'mc-bridge-' + run_id
    remote = 'files/state/' + workspace
    evidence = HERE/'.local'/run_id
    evidence.mkdir(parents=True, mode=0o700)

    def run(*words, data=None):
        return subprocess.run([*adb,*words],input=data,capture_output=True,check=True,timeout=120).stdout
    def shell(*words): return run('shell',shlex.join(words)).decode().strip()
    def read(package,path): return run('exec-out','run-as',package,'cat',path)
    def write(package,path,data):
        run('shell','-T','run-as',package,'tee',path,data=data)
        shell('run-as',package,'chmod','600',path)
    def setting(key): return shell('settings','--user','0','get','secure',key)
    def put(key,value): shell('settings','--user','0','put','secure',key,value)
    def tap_label(label):
        # Used only before arming. UiAutomator may temporarily suppress other
        # accessibility services, so never dump while the bridge is admitted.
        xml_path = '/data/local/tmp/mc-fixture-' + run_id + '.xml'
        try:
            shell('uiautomator','dump',xml_path)
            xml = run('exec-out','cat',xml_path)
        finally:
            shell('rm','-f',xml_path)
        node = next(n for n in ET.fromstring(xml).iter('node') if n.get('text','').casefold() == label.casefold())
        x1,y1,x2,y2 = map(int,re.findall(r'\d+',node.attrib['bounds']))
        time.sleep(.5)
        shell('input','tap',str((x1+x2)//2),str((y1+y2)//2))

    doctor = subprocess.check_output([str(ROOT/'platforms/android/bin/android-device'),
        '--serial',args.serial,'doctor','--json'])
    assert json.loads(doctor)['ready'], 'Explicit target must be ready and unlocked'
    packages = shell('pm','list','packages','--user','0',APP)
    assert 'package:'+APP not in packages or args.replace_spike, 'Use --replace-spike to replace this fixture only'
    assert 'Stopped' in read(HOST,'files/host-status.txt').decode(), 'Stop the experimental host before instrumentation'
    assert not subprocess.run([*adb,'shell','run-as',HOST,'test','-e',remote],capture_output=True).returncode == 0
    old_services = setting('enabled_accessibility_services')
    old_enabled = setting('accessibility_enabled')
    (evidence/'recovery.json').write_text(json.dumps({'serial':args.serial,'services':old_services,
        'enabled':old_enabled,'workspace':remote}))
    (evidence/'recovery.json').chmod(0o600)
    installed = staged = enabled = False
    try:
        subprocess.run([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,
            'install',str(args.apk.resolve())],check=True,capture_output=True)
        installed = True
        services = [] if old_services in ('null','') else old_services.split(':')
        put('enabled_accessibility_services',':'.join([*services,COMPONENT]))
        enabled = True
        put('accessibility_enabled','1')
        subprocess.run([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,
            'launch',APP],check=True,capture_output=True)
        tap_label('Arm bridge (15 minutes)')
        grant = None
        for _ in range(30):
            try:
                grant = read(APP,'files/bridge.json')
                json.loads(grant)
                break
            except (subprocess.CalledProcessError,ValueError): time.sleep(.2)
        assert grant is not None, 'Fixture grant was not armed'
        # Stage unchanged MC core and the spike scripts under the existing host
        # app. No native runtime or provider credentials are copied/changed.
        shell('run-as',HOST,'mkdir',remote)
        staged = True
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as tar:
            for source in sorted((ROOT/'client').glob('*.py')):
                tar.add(source,arcname='client/'+source.name)
            for name in ('session.py','phone_probe.py'):
                tar.add(HERE/name,arcname=name)
        run('shell','-T','run-as',HOST,'tar','-xf','-','-C',remote,data=archive.getvalue())
        write(HOST,remote+'/bridge.json',grant)
        nonce = 'MC_ANDROID_' + uuid.uuid4().hex
        write(HOST,remote+'/challenge.txt',nonce.encode())
        result = run('shell','am','instrument','-w','-e','workspace',workspace,
            APP+'/.PhonePythonProbe')
        (evidence/'instrumentation.log').write_bytes(result)
        for name in ('phone-probe.log','phone-witness.json','python-snippets.json','capture.png'):
            try: (evidence/name).write_bytes(read(HOST,remote+'/'+name))
            except subprocess.CalledProcessError: pass
        assert b'PHONE_PYTHON_PASS' in result, 'Phone probe failed; inspect private evidence'
        witness = json.loads((evidence/'phone-witness.json').read_text())
        assert read(APP,'files/fixture-result.txt').decode() == nonce, 'Independent fixture result mismatch'
        witness['independentFixtureFileVerified'] = True
        # Revocation is witnessed by disabling just our service below. The
        # native grant file must disappear; no unrelated service is removed.
        print(json.dumps(witness,indent=2))
        (evidence/'summary.json').write_text(json.dumps(witness,indent=2)+'\n')
    finally:
        if enabled:
            now = setting('enabled_accessibility_services')
            remaining = [s for s in now.split(':') if s and s not in (COMPONENT,APP+'/'+APP+'.ResidentService','null')]
            if remaining == ([] if old_services in ('null','') else old_services.split(':')):
                if old_services == 'null': shell('settings','--user','0','delete','secure','enabled_accessibility_services')
                else: put('enabled_accessibility_services',old_services)
            else:
                put('enabled_accessibility_services',':'.join(remaining))
            if not remaining:
                if old_enabled == 'null': shell('settings','--user','0','delete','secure','accessibility_enabled')
                else: put('accessibility_enabled',old_enabled)
        if installed:
            shell('am','force-stop',APP)
            # Leave only the debug fixture installed for review, fully revoked.
        if staged:
            shell('run-as',HOST,'rm','-rf',remote)
        print('Private evidence: '+str(evidence))


if __name__ == '__main__':
    main()

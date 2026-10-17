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
import urllib.request
import urllib.error
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
    p.add_argument('--aar-checkout', type=Path, help='Opt in to real Codex/Claude turns using temporary existing-account grants')
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
    def read(package,path): return run('shell','-T','run-as',package,'cat',path)
    def write(package,path,data):
        run('shell','-T','run-as',package,'tee',path,data=data)
        shell('run-as',package,'chmod','600',path)
    def setting(key): return shell('settings','--user','0','get','secure',key)
    def put(key,value): shell('settings','--user','0','put','secure',key,value)
    def fixture_buttons():
        # Used only before arming. UiAutomator may temporarily suppress other
        # accessibility services, so never dump while the bridge is admitted.
        xml_path = '/data/local/tmp/mc-fixture-' + run_id + '.xml'
        try:
            shell('uiautomator','dump',xml_path)
            xml = run('exec-out','cat',xml_path)
        finally:
            shell('rm','-f',xml_path)
        buttons = {}
        for node in ET.fromstring(xml).iter('node'):
            x1,y1,x2,y2 = map(int,re.findall(r'\d+',node.attrib['bounds']))
            buttons[node.get('text','').casefold()] = (str((x1+x2)//2),str((y1+y2)//2))
        return buttons

    doctor = subprocess.check_output([str(ROOT/'platforms/android/bin/android-device'),
        '--serial',args.serial,'doctor','--json'])
    assert json.loads(doctor)['ready'], 'Explicit target must be ready and unlocked'
    packages = shell('pm','list','packages','--user','0',APP)
    assert 'package:'+APP not in packages or args.replace_spike, 'Use --replace-spike to replace this fixture only'
    assert 'Stopped' in read(HOST,'files/host-status.txt').decode(), 'Stop the experimental host before instrumentation'
    assert subprocess.run([*adb,'shell','run-as',HOST,'test','-e',remote],capture_output=True).returncode == 1
    old_services = setting('enabled_accessibility_services')
    old_enabled = setting('accessibility_enabled')
    (evidence/'recovery.json').write_text(json.dumps({'serial':args.serial,'services':old_services,
        'enabled':old_enabled,'workspace':remote}))
    (evidence/'recovery.json').chmod(0o600)
    installed = staged = enabled = False
    gateway = None
    reverse_owned = False
    reverse_port = None
    def aar(*words, body=None):
        return subprocess.check_output(['node',str(args.aar_checkout.resolve()/'src/cli.ts'),*words],
            input=body,text=True,cwd=args.aar_checkout,stderr=subprocess.PIPE)
    try:
        if args.aar_checkout:
            overview = json.loads(aar('owner-request','overview',body='{}'))
            assert overview['origin'] == 'http://127.0.0.1:8417'
            accounts = {provider:next(a['id'] for a in overview['accounts'] if a['provider']==provider and a['enabled'])
                for provider in ('claude','codex')}
            name = 'android-native-spike-'+run_id
            created = aar('client','add',name,'--claude',accounts['claude'],'--codex',accounts['codex'])
            token = re.findall(r'\baar_[A-Za-z0-9_-]+\b',created)[0]
            gateway = {'client':name,'token':token}
            lease = evidence/'aar-recovery.json';lease.write_text(json.dumps(gateway));lease.chmod(0o600)
            mappings = run('reverse','--list').decode()
            reverse_port = next(port for port in range(18418,18518) if 'tcp:'+str(port) not in mappings)
            run('reverse','tcp:'+str(reverse_port),'tcp:8417');reverse_owned = True
        subprocess.run([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,
            'install',str(args.apk.resolve())],check=True,capture_output=True)
        installed = True
        services = [] if old_services in ('null','') else old_services.split(':')
        put('enabled_accessibility_services',':'.join([*services,COMPONENT]))
        enabled = True
        put('accessibility_enabled','1')
        subprocess.run([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,
            'launch',APP],check=True,capture_output=True)
        buttons = fixture_buttons()
        time.sleep(.5)
        shell('input','tap',*buttons['arm bridge (15 minutes)'])
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
            for name in ('session.py','phone_probe.py','provider_probe.py'):
                tar.add(HERE/name,arcname=name)
        run('shell','-T','run-as',HOST,'tar','-xf','-','-C',remote,data=archive.getvalue())
        write(HOST,remote+'/bridge.json',grant)
        nonce = 'MC_ANDROID_' + uuid.uuid4().hex
        write(HOST,remote+'/challenge.txt',nonce.encode())
        if gateway:
            write(HOST,remote+'/inference.json',json.dumps({'endpoint':'http://127.0.0.1:'+str(reverse_port),
                'token':gateway['token']}).encode())
        instrument = subprocess.Popen([*adb,'shell','am','instrument','-w','-e','workspace',workspace,
            APP+'/.PhonePythonProbe'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + (360 if gateway else 90)
            verified = set()
            replaced = False
            while instrument.poll() is None and time.monotonic() < deadline:
                for provider in ('codex','claude') if gateway else ():
                    if provider not in verified and subprocess.run([*adb,'shell','run-as',HOST,'test','-e',remote+'/'+provider+'-await-oracle'],capture_output=True).returncode == 0:
                        expected = read(HOST,remote+'/'+provider+'-expected.txt')
                        assert read(APP,'files/fixture-result.txt') == expected, 'Provider effect oracle mismatch'
                        write(HOST,remote+'/'+provider+'-oracle-verified',b'verified')
                        verified.add(provider)
                if not replaced and subprocess.run([*adb,'shell','run-as',HOST,'test','-e',remote+'/await-replace'],capture_output=True).returncode == 0:
                    shell('input','tap',*buttons['replace input'])
                    write(HOST,remote+'/replaced-by-controller',b'replaced')
                    replaced = True
                if subprocess.run([*adb,'shell','run-as',HOST,'test','-e',remote+'/await-revoke'],capture_output=True).returncode == 0:
                    shell('input','tap',*buttons['stop bridge'])
                    write(HOST,remote+'/revoked-by-controller',b'revoked')
                    break
                time.sleep(.2)
            result,_ = instrument.communicate(timeout=20)
        except BaseException:
            instrument.kill();instrument.communicate()
            raise
        (evidence/'instrumentation.log').write_bytes(result)
        for name in ('phone-probe.log','phone-witness.json','python-snippets.json','capture.png','provider-witness.json',
                     'codex/events.json','codex/stderr.log','claude/events.json','claude/stderr.log'):
            destination = evidence/name;destination.parent.mkdir(exist_ok=True)
            try: destination.write_bytes(read(HOST,remote+'/'+name))
            except subprocess.CalledProcessError: pass
        assert b'PHONE_PYTHON_PASS' in result, 'Phone probe failed; inspect private evidence'
        witness = json.loads((evidence/'phone-witness.json').read_text())
        assert read(APP,'files/fixture-result.txt').decode() == nonce, 'Independent fixture result mismatch'
        witness['independentFixtureFileVerified'] = True
        assert subprocess.run([*adb,'shell','run-as',APP,'test','-e','files/bridge.json'],capture_output=True).returncode == 1
        witness['nativeGrantFileRemoved'] = True
        if gateway:
            witness['realProviders'] = json.loads((evidence/'provider-witness.json').read_text())
        print(json.dumps(witness,indent=2))
        (evidence/'summary.json').write_text(json.dumps(witness,indent=2)+'\n')
    finally:
        def revoke_gateway():
            aar('client','revoke',gateway['client'])
            for provider in ('claude','codex'):
                request = urllib.request.Request('http://127.0.0.1:8417/'+provider+'/'+('v1/models' if provider=='claude' else 'models'),
                    headers={'Authorization':'Bearer '+gateway['token']})
                try:
                    urllib.request.urlopen(request,timeout=5).close()
                    raise RuntimeError('Revoked gateway grant accepted')
                except urllib.error.HTTPError as error:
                    assert error.code == 401
            (evidence/'aar-recovery.json').unlink()
        def restore_accessibility():
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
        steps = []
        if gateway: steps.append(('gateway revocation',revoke_gateway))
        if reverse_owned: steps.append(('inference tunnel',lambda:run('reverse','--remove','tcp:'+str(reverse_port))))
        if enabled: steps.append(('accessibility restoration',restore_accessibility))
        if installed: steps.append(('fixture stop',lambda:shell('am','force-stop',APP)))
        if staged:
            steps.extend([('probe host stop',lambda:shell('am','force-stop',HOST)),
                          ('private workspace removal',lambda:shell('run-as',HOST,'rm','-rf',remote))])
        failed = []
        for label,cleanup in steps:
            try: cleanup()
            except Exception: failed.append(label)
        print('Private evidence: '+str(evidence))
        if failed:
            raise RuntimeError('Cleanup needs recovery: '+', '.join(failed)+'; retain private recovery records') from None


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Exercise real photo/SAF consent and independent phone-local data readers.

Uses only unique owned media/folders, never a personal photograph. Requires the
stopped debug YA host with its existing Python/Alpine payload. No accessibility
settings, broad storage permissions, provider credentials or ADB tunnels change.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import struct
import subprocess
import tarfile
import time
import uuid
import xml.etree.ElementTree as ET
import zlib

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
APP = 'dev.machinecontrol.android.spike'
HOST = 'com.yepanywhere.host.experimental'


def test_png():
    def chunk(kind, body):
        return struct.pack('!I',len(body))+kind+body+struct.pack('!I',zlib.crc32(kind+body))
    pixels = b''.join(b'\0'+bytes((240,40,80) if y<64 else (30,200,120))*128 for y in range(128))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('!2I5B',128,128,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--replace-spike',action='store_true')
    parser.add_argument('--apk',type=Path,default=HERE/'app/build/outputs/apk/debug/app-debug.apk')
    args = parser.parse_args()
    adb = ['adb','-s',args.serial]
    run_id = uuid.uuid4().hex
    folder = 'MCData-'+run_id
    photo_name = 'mc-photo-'+run_id+'.png'
    photo_path = '/sdcard/Pictures/'+folder+'/'+photo_name
    tree_path = '/sdcard/Download/'+folder
    initial = 'content://com.android.externalstorage.documents/document/primary%3ADownload%2F'+folder
    workspace = 'mc-bridge-'+run_id
    remote = 'files/state/'+workspace
    evidence = HERE/'.local'/('data-'+run_id)
    evidence.mkdir(parents=True,mode=0o700)
    def run(*words,data=None):
        return subprocess.run([*adb,*words],input=data,capture_output=True,check=True,timeout=120).stdout
    def shell(*words): return run('shell',shlex.join(words)).decode().strip()
    def read(package,path): return run('shell','-T','run-as',package,'cat',path)
    def write(package,path,data):
        run('shell','-T','run-as',package,'tee',path,data=data)
        shell('run-as',package,'chmod','600',path)
    def exists(package,path):
        return subprocess.run([*adb,'shell',shlex.join(['run-as',package,'test','-e',path])],capture_output=True).returncode==0
    def nodes():
        path = '/data/local/tmp/mc-data-'+run_id+'.xml'
        try:
            shell('uiautomator','dump',path)
            xml = run('exec-out','cat',path)
            (evidence/'latest-ui.xml').write_bytes(xml)
            (evidence/('ui-'+str(time.monotonic_ns())+'.xml')).write_bytes(xml)
            return list(ET.fromstring(xml).iter('node'))
        finally: shell('rm','-f',path)
    def tap(label):
        items = nodes()
        matches = [n for n in items if n.get('text','').casefold()==label.casefold() or n.get('content-desc','').casefold()==label.casefold()]
        assert matches, 'Missing UI control '+label+'; inspect latest-ui.xml'
        node = matches[-1]
        x1,y1,x2,y2 = map(int,re.findall(r'\d+',node.get('bounds')))
        shell('input','tap',str((x1+x2)//2),str((y1+y2)//2))
        time.sleep(.5)
    def activity(): shell('am','start','-f','0x10008000','-n',APP+'/.DataActivity','--es','initialTree',initial)
    def arm():
        tap('Arm data bridge')
        deadline = time.monotonic()+10
        while not exists(APP,'files/data-bridge.json'):
            assert time.monotonic()<deadline
            time.sleep(.1)
        return read(APP,'files/data-bridge.json')
    doctor = json.loads(subprocess.check_output([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,'doctor','--json']))
    assert doctor['ready'] and doctor['states']['interaction']=='unlocked'
    assert args.replace_spike or 'package:'+APP not in shell('pm','list','packages',APP)
    assert not exists(APP,'shared_prefs/data-selections-v1.xml'), 'Preserve existing user selections; use a clean dedicated fixture install'
    assert 'Stopped' in read(HOST,'files/host-status.txt').decode()
    before = {key:shell('settings','--user','0','get','secure',key) for key in ('enabled_accessibility_services','accessibility_enabled')}
    recovery = {'serial':args.serial,'photoPath':photo_path,'treePath':tree_path,'workspace':remote,'initialTree':initial}
    (evidence/'recovery.json').write_text(json.dumps(recovery)); (evidence/'recovery.json').chmod(0o600)
    installed = staged = fixtures = False
    instrument = None
    try:
        subprocess.run([str(ROOT/'platforms/android/bin/android-device'),'--serial',args.serial,'install',str(args.apk.resolve())],check=True,capture_output=True)
        installed = True
        photo = test_png(); document = ('MC selected document '+run_id+'\n').encode()
        (evidence/photo_name).write_bytes(photo); (evidence/'proof.txt').write_bytes(document)
        shell('mkdir','-p','/sdcard/Pictures/'+folder,tree_path)
        fixtures = True
        run('push',str(evidence/photo_name),photo_path); run('push',str(evidence/'proof.txt'),tree_path+'/proof.txt')
        shell('am','broadcast','-a','android.intent.action.MEDIA_SCANNER_SCAN_FILE','-d','file://'+photo_path)
        deadline = time.monotonic()+15
        while 'Row:' not in shell('content','query','--uri','content://media/external/images/media','--projection','_id:_display_name','--where',"_display_name='"+photo_name+"'"):
            assert time.monotonic()<deadline, 'Owned photo was not indexed'
            time.sleep(.3)
        activity(); tap('Select photo')
        # Use only the unique owned album, never the first personal thumbnail.
        tap('Collections')
        if any(n.get('text','')=='From this device' for n in nodes()): tap('From this device')
        tap(folder)
        items = nodes()
        images = [n for n in items if n.get('resource-id','').endswith('/icon_thumbnail') or
            n.get('content-desc','').startswith('Photo taken on ')]
        assert len(images)==1, 'Owned album must contain exactly one test photo'
        x1,y1,x2,y2 = map(int,re.findall(r'\d+',images[0].get('bounds')))
        shell('input','tap',str((x1+x2)//2),str((y1+y2)//2)); time.sleep(.5)
        # Some picker versions return immediately; others have an Add button.
        labels = {n.get('text','').casefold() for n in nodes()}
        if 'add' in labels: tap('Add')
        elif 'done' in labels: tap('Done')
        tap('Select read-only folder')
        assert any(n.get('text')==folder for n in nodes()), 'System picker did not open the owned folder'
        tap('Use this folder'); tap('Allow')
        assert 'Selected photo available: true' in ' '.join(n.get('text','') for n in nodes())
        grant = arm()
        shell('run-as',HOST,'mkdir',remote); staged = True
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive,mode='w') as tar:
            for source in sorted((ROOT/'client').glob('*.py')): tar.add(source,arcname='client/'+source.name)
            for name in ('session.py','data_client.py'): tar.add(HERE/name,arcname=name)
            tar.add(HERE/'data_probe.py',arcname='phone_probe.py')
        run('shell','-T','run-as',HOST,'tar','-xf','-','-C',remote,data=archive.getvalue())
        write(HOST,remote+'/expected.json',json.dumps({'photoHash':hashlib.sha256(photo).hexdigest(),'docHash':hashlib.sha256(document).hexdigest()}).encode())
        results = []
        for phase in ('initial','restart'):
            if phase=='restart':
                old = json.loads(grant)
                shell('am','force-stop',APP); activity()
                grant = arm()
                assert json.loads(grant)['generation'] != old['generation'] and json.loads(grant)['token'] != old['token']
            write(HOST,remote+'/bridge.json',grant)
            write(HOST,remote+'/phase',phase.encode())
            shell('input','keyevent','KEYCODE_HOME')
            instrument = subprocess.Popen([*adb,'shell','am','instrument','-w','-e','workspace',workspace,APP+'/.PhonePythonProbe'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            deadline=time.monotonic()+180
            done=set()
            while instrument.poll() is None and time.monotonic()<deadline:
                for action,button in (('revoke-tree','Revoke folder access'),('revoke-photo','Revoke photo access'),('stop','Stop data bridge')):
                    if action not in done and exists(HOST,remote+'/await-'+action):
                        activity(); tap(button); shell('input','keyevent','KEYCODE_HOME')
                        write(HOST,remote+'/done-'+action,b'done'); done.add(action)
                time.sleep(.15)
            output,_=instrument.communicate(timeout=10); instrument=None
            (evidence/('instrumentation-'+phase+'.log')).write_bytes(output)
            (evidence/('phone-'+phase+'.log')).write_bytes(read(HOST,remote+'/phone-probe.log'))
            assert b'PHONE_PYTHON_PASS' in output, 'Probe failed; inspect private phone log'
            witness=json.loads(read(HOST,remote+'/data-witness-'+phase+'.json'))
            assert read(HOST,remote+'/export-'+phase+'.png')==photo
            assert read(HOST,remote+'/export-'+phase+'.txt')==document
            witness['independentExportsVerified']=True
            for name in ('data-witness-'+phase+'.json','data-snippets-'+phase+'.json','thumbnail-'+phase+'.png'):
                (evidence/name).write_bytes(read(HOST,remote+'/'+name))
            results.append(witness)
        assert not exists(APP,'files/data-bridge.json'), 'Stopped bridge receipt still exists'
        after={key:shell('settings','--user','0','get','secure',key) for key in before}
        assert after==before, 'Accessibility settings changed'
        summary={'phases':results,'persistedGrantAfterAppRestart':True,'newRuntimeAuthorityAfterRestart':True,'accessibilityUnchanged':True,'bridgeReceiptRemoved':True}
        (evidence/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,indent=2))
    finally:
        if instrument:
            instrument.kill(); instrument.communicate()
        failures=[]
        def cleanup(label,fn):
            try: fn()
            except Exception: failures.append(label)
        if installed:
            def forget():
                # Picker may still be open on failure; explicit activity returns
                # to the owned operator surface before releasing owned grants.
                shell('am','force-stop',APP); activity(); tap('Forget selections')
                shell('am','force-stop',APP)
                shell('run-as',APP,'rm','-f','files/data-bridge.json','shared_prefs/data-selections-v1.xml')
            cleanup('owned grant cleanup',forget)
        if staged:
            cleanup('probe host stop',lambda:shell('am','force-stop',HOST))
            cleanup('workspace removal',lambda:shell('run-as',HOST,'rm','-rf',remote,'cache/'+workspace))
        if fixtures:
            cleanup('owned media row',lambda:shell('content','delete','--uri','content://media/external/images/media','--where',"_display_name='"+photo_name+"'"))
            cleanup('owned fixtures',lambda:shell('rm','-rf',tree_path,'/sdcard/Pictures/'+folder))
        print('Private evidence: '+str(evidence))
        if failures: raise RuntimeError('Cleanup needs recovery: '+', '.join(failures))
        (evidence/'recovery.json').unlink()


if __name__=='__main__': main()

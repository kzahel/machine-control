#!/usr/bin/env python3
"""Real Linux companion/GTK handoff with an isolated native effect oracle.

The claimed controller owns helper setup, source identity and power cleanup.
No simulated policy, operator hook or approval bypass is added to the product.
"""
import argparse
import contextlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--portal-source',help='Exact native screen name on a multi-screen target')
    args=parser.parse_args();signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(SystemExit(143)))
    args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
    sys.path.insert(0,str(args.runtime))
    import linuxui
    from gi.repository import GLib
    linuxui.Atspi.init()
    spec=importlib.util.spec_from_file_location('surface_owner',args.source_root/'tests/macos/surface-policy-live.py')
    actor=importlib.util.module_from_spec(spec);spec.loader.exec_module(actor)
    checks=[];owned=[];owners=[];child=None;failure=None;fixture_unit=None
    log=(args.output/'native.log').open('w')
    def report(complete=False):
        (args.output/'summary.json').write_text(json.dumps(dict(complete=complete,passed=complete and failure is None,
            failure=failure,checks=checks),indent=2))
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)));report()
        if not value:raise AssertionError(name)
    def poll(fn,label,timeout=15):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            context=GLib.MainContext.default()
            for _ in range(64):
                if not context.pending():break
                context.iteration(False)
            try:
                value=fn()
                if value:return value
            except (OSError,linuxui.UIError):pass
            time.sleep(.1)
        raise AssertionError('Timed out: '+label)
    def operator(method,**fields):
        child.stdin.write(json.dumps(dict(method=method,**fields))+'\n');child.stdin.flush()
        assert select.select([child.stdout],[],[],10)[0],'Private operator deadline'
        reply=json.loads(child.stdout.readline());assert reply['ok'],reply
        return reply
    def state():return operator('state')['state']
    def plain(operation,**fields):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(30);peer.connect(str(endpoint));peer.sendall(json.dumps(dict(operation=operation,**fields)).encode()+b'\n')
            with peer.makefile('rb') as stream:return json.loads(stream.readline(16*1024*1024))
    def fixture_operator(operation,**fields):
        # Independently select the owned foreground fixture as the human-side
        # operator after portal consent. Never route ordinary effects here.
        path=Path(os.environ['XDG_RUNTIME_DIR'])/'linuxvm-testbed/control.sock'
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(20);peer.connect(str(path));peer.sendall(json.dumps(dict(operation=operation,**fields)).encode()+b'\n')
            peer.shutdown(socket.SHUT_WR)
            with peer.makefile('rb') as stream:return json.load(stream)
    def nodes(name):
        app=linuxui.choose_application(linuxui.desktop(),name);app.clear_cache()
        return list(linuxui.walk(app,25,2000))
    def press(label):
        import linux_notice_ui
        control=poll(lambda:linux_notice_ui.find(linuxui,label),label)
        check('native notice '+label,linux_notice_ui.press(linuxui,control,fixture_operator))
    def foreground():
        active=[]
        for application in linuxui.application_roots(linuxui.desktop()):
            application.clear_cache()
            for _,window in linuxui.children(application):
                window.clear_cache()
                if 'active' in linuxui.state_names(window):
                    active.append(dict(name=linuxui.safe(application.get_name,''),pid=linuxui.safe(application.get_process_id,0)))
        return active
    def owner():
        value=actor.Owner(endpoint,'fixture',['desktop']);owners.append(value);return value
    def waiting(value,wanted):return poll(lambda:(v if (v:=value.status())['state']==wanted else None),wanted)
    def configure(mode):operator('surface.configure',surface='desktop',mode=mode,lifetime='until_stopped',duration=0)
    def effect(value):
        result=value.call('snapshot',target='machine-control-fixture',maxDepth=16)
        print(json.dumps(result),file=log,flush=True)
        check('controlled native snapshot',result['accepted'])
        elements=result['data']['elements'];button=next(row for row in elements if row['label']=='Semantic Increment')
        before=json.loads(oracle.read_text())['semanticPresses']
        result=value.call('action',reference=button['reference'])
        check('ordinary AT-SPI delivery',result['accepted'] and result['actualRoute']=='guest.user/linux.atspi')
        poll(lambda:json.loads(oracle.read_text())['semanticPresses']==before+1,'independent fixture effect')
        check('independent native effect',True)
        return button['reference']
    try:
        # Isolate all product preferences, while leaving the canonical capture
        # cache available to the public artifact-fetch adapter.
        env=dict(os.environ)
        for name,suffix in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state')]:
            env[name]=str(args.output/suffix)
        child=subprocess.Popen(['/usr/bin/python3',str(args.runtime/'desktop.py')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True,env=env)
        operator('hello',processId=os.getpid(),executable='/usr/bin/true')
        poll(lambda:state()['safetyAvailable'] and state()['permissions']['accessibility'],'native readiness')
        endpoint=Path(state()['socket'])
        check('both surfaces initially Off',all(s['mode']=='off' for s in state()['accessPolicy']['surfaces'].values()))
        check('plain effects require a live task',plain('snapshot')['errorCode']=='control_session_required')
        check('legacy grant request removed',plain('grant.request')['errorCode']=='legacy_grant_request_unsupported')
        oracle=args.output/'fixture.json'
        runner=args.output/'fixture.py'
        runner.write_text("import importlib.util,pathlib\ns=importlib.util.spec_from_file_location('fixture',"+repr(str(args.source_root/'platforms/linux/guests/ubuntu/fixtures/control_fixture.py'))+")\nm=importlib.util.module_from_spec(s);s.loader.exec_module(m)\nm.STATE_PATH=pathlib.Path("+repr(str(oracle))+")\nm.main()\n")
        fixture_unit='mc-surface-fixture-'+str(os.getpid())+'.service'
        subprocess.run(['/usr/bin/systemd-run','--user','--quiet','--collect','--unit',fixture_unit,
            '/usr/bin/python3',str(runner)],stdout=log,stderr=log,check=True)
        poll(lambda:oracle.exists(),'owned fixture')
        operator('control_notice',noticeSeconds=10);configure('ask')
        poll(lambda:state()['activityObserver']['healthy'],'actual read-only observer')
        first=owner();waiting(first,'waiting_for_approval')
        check('native warning does not take keyboard focus',any(row['pid']==json.loads(oracle.read_text())['pid'] for row in foreground()))
        press('Allow this task');waiting(first,'announcing')
        press('Start now');first.wait()
        check('Ask first yields a live owner',first.view['state']=='active')
        reference=effect(first);original=first.view['sessionId']
        press('Open task controls');poll(lambda:any('active' in info['states'] for _,info in nodes('machine-control-safety') if info['role']=='frame'),'explicit full native controls')
        check('full native controls open only on user action',True)
        press('Hide task controls')
        operator('pause_surface',surface='browser',duration=30)
        check('Browser pause preserves Desktop owner',first.status()['sessionId']==original)
        press('Pause 30 seconds');waiting(first,'paused')
        check('deferral retains surface consent',state()['accessPolicy']['surfaces']['desktop']['mode']=='ask')
        press('Resume desktop');waiting(first,'announcing');press('Start now');first.wait()
        check('Resume creates a fresh session',first.view['sessionId']!=original)
        stale=first.call('action',reference=reference)
        check('old native reference refused',not stale['accepted'])
        effect(first);first.close();owners.remove(first)
        check('owner close preserves consent',state()['accessPolicy']['surfaces']['desktop']['mode']=='ask')
        denied=owner();waiting(denied,'waiting_for_approval');press('Deny this task');waiting(denied,'ended')
        check('native task denial is terminal',denied.view['terminalReason']=='denied_by_person')
        denied.close();owners.remove(denied)
        configure('automatic');automatic=owner();waiting(automatic,'announcing')
        check('Automatic announces without approval',True)
        automatic.wait();check('warning reaches offer automatically',automatic.view['state']=='active')
        effect(automatic)
        # Portal consent is independently acted on through native accessibility.
        consent_command=['/usr/bin/python3',str(args.source_root/'tests/desktop/linux-consent.py'),
            '--runtime',str(args.runtime)]
        if args.portal_source:consent_command+=['--source',args.portal_source]
        consent=subprocess.Popen(consent_command,stdout=log,stderr=log);owned.append(consent)
        operator('permission');consent.wait(40);check('real compositor consent',consent.returncode==0)
        poll(lambda:state()['portal']['state']=='ready','portal ready')
        # The pending chooser yields the old session. A new warning is required.
        automatic.wait()
        snapshot=automatic.call('snapshot',target='machine-control-fixture',maxDepth=16)
        entry=next(row for row in snapshot['data']['elements'] if row['label']=='Fixture Text')
        check('ordinary native focus',automatic.call('focus',reference=entry['reference'])['accepted'])
        fixture_pid=json.loads(oracle.read_text())['pid']
        for _ in range(3):
            if any(row['pid']==fixture_pid for row in foreground()):break
            selected=fixture_operator('input.key',key='alt+tab')
            assert selected['accepted'],'Independent fixture selection refused'
            time.sleep(.4)
        poll(lambda:any(row['pid']==fixture_pid for row in foreground()),'independent foreground fixture')
        check('independent operator selects the owned foreground fixture',True)
        active=foreground()
        (args.output/'foreground.private.json').write_text(json.dumps(active))
        typed=automatic.call('input.key',target='machine-control-fixture',key='a')
        (args.output/'input-result.private.json').write_text(json.dumps(typed))
        check('ordinary portal input delivery',typed['accepted'] and typed['actualRoute']=='user/linux.portal-notify')
        poll(lambda:json.loads(oracle.read_text())['text']=='a','independent portal key effect')
        check('independent portal key effect',True)
        capture=automatic.call('capture')
        check('ordinary portal capture',capture['accepted'] and capture['actualRoute']=='user/linux.portal-pipewire')
        artifact=capture['data']['artifact'];check('capture artifact is bounded',artifact['byteLength']>100)
        image=Path(artifact['guestPath']);content=image.read_bytes()
        check('capture artifact hash',hashlib.sha256(content).hexdigest()==artifact['sha256'])
        (args.output/'capture.png').write_bytes(content);image.unlink()
        press('Stop all access');waiting(automatic,'ended')
        check('native Stop turns both surfaces Off',all(s['mode']=='off' for s in state()['accessPolicy']['surfaces'].values()))
        automatic.close();owners.remove(automatic)
        operator('quit');child.wait(10);check('owned policy and native UI exit',child.returncode==0)
    except BaseException as error:
        failure=type(error).__name__+': '+str(error);raise
    finally:
        for value in owners:
            with contextlib.suppress(Exception):value.close()
        if child and child.poll() is None:
            with contextlib.suppress(Exception):operator('quit');child.wait(10)
            if child.poll() is None:child.kill();child.wait(5)
        if fixture_unit:
            subprocess.run(['/usr/bin/systemctl','--user','stop',fixture_unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for process in owned:
            if process.poll() is None:process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired):process.wait(5)
            if process.poll() is None:process.kill();process.wait(5)
        log.close();report(True)


if __name__=='__main__':main()

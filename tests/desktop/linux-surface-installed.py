#!/usr/bin/env python3
"""Packaged Linux Settings and shipped Python SDK, through native UI only."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('app','runtime','client','output','fixture'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--revision',required=True)
    parser.add_argument('--remote-handoff',action='store_true',help='Coordinate an outside SDK actor through private fixture markers')
    args=parser.parse_args();args.output.mkdir(parents=True,mode=0o700,exist_ok=True)
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(SystemExit(143)))
    sys.dont_write_bytecode=True;os.environ['PYTHONDONTWRITEBYTECODE']='1'
    sys.path.insert(0,str(args.runtime))
    import linuxui
    from gi.repository import GLib
    linuxui.Atspi.init()
    sys.dont_write_bytecode=True;sys.path.insert(0,str(args.client/'client'))
    from control_session import ControlSession
    checks=[];failure=None;app=None;sdk=None;claim=None;unit=None
    log=(args.output/'installed.log').open('w')
    endpoint=Path(os.environ['XDG_RUNTIME_DIR'])/'machine-control-desktop/desktop.sock'
    cli=[str(args.client/'python/bin/python3'),'-I','-B',str(args.client/'platforms/linux/host/linuxhost.py')]
    def report(complete=False):
        (args.output/'summary.json').write_text(json.dumps(dict(complete=complete,passed=complete and failure is None,
            failure=failure,checks=checks),indent=2))
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)));report()
        if not value:raise AssertionError(name)
    def poll(fn,label,timeout=25):
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
            time.sleep(.15)
        raise AssertionError('Timed out: '+label)
    def plain(operation,**fields):
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(20);peer.connect(str(endpoint));peer.sendall(json.dumps(dict(operation=operation,**fields)).encode()+b'\n')
            with peer.makefile('rb') as stream:return json.loads(stream.readline(16*1024*1024))
    def policy():return plain('status')['data']['admission']
    def owned_pid(pid):
        for _ in range(32):
            if pid==app.pid:return True
            if pid<=1:return False
            try:pid=int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[1])
            except (OSError,ValueError,IndexError):return False
        return False
    def nodes(safety=False):
        roots=linuxui.application_roots(linuxui.desktop())
        selected=[r for r in roots if linuxui.safe(r.get_name,'')=='machine-control-safety'] if safety else [r for r in roots if linuxui.safe(r.get_name,'')!='machine-control-safety' and owned_pid(linuxui.safe(r.get_process_id,0)) and any(linuxui.safe(w.get_role_name,'')=='frame' for _,w in linuxui.children(r))]
        if len(selected)!=1:return []
        selected[0].clear_cache();return list(linuxui.walk(selected[0],30,3000))
    def widget(label,role='push button',safety=False):
        found=[n for n,i in nodes(safety) if i['name']==label and i['role']==role]
        return found[0] if len(found)==1 else None
    def press(label,safety=False):
        if safety:
            import linux_notice_ui
            control=poll(lambda:linux_notice_ui.locate(linuxui,label,observer),'native notice '+label)
            check('native UI '+label,linux_notice_ui.press(linuxui,control,observer));return
        node=poll(lambda:widget(label),'native UI '+label)
        check('native UI '+label,node.do_action(0))
    def observer(operation,**fields):
        # This explicitly separate appliance provider acts as the human-side
        # fixture operator. It is never an ordinary-app dispatch fallback.
        path=Path(os.environ['XDG_RUNTIME_DIR'])/'linuxvm-testbed/control.sock'
        with socket.socket(socket.AF_UNIX) as peer:
            peer.settimeout(20);peer.connect(str(path));peer.sendall(json.dumps(dict(operation=operation,**fields)).encode()+b'\n')
            peer.shutdown(socket.SHUT_WR)
            with peer.makefile('rb') as stream:value=json.load(stream)
            assert value['accepted'],'Independent native operator refused'
            return value
    def active_app():
        for root in linuxui.application_roots(linuxui.desktop()):
            if not owned_pid(linuxui.safe(root.get_process_id,0)):continue
            root.clear_cache()
            for _,window in linuxui.children(root):
                window.clear_cache()
                if 'active' in linuxui.state_names(window):return True
        return False
    def activate_app():
        for _ in range(4):
            if active_app():return
            observer('input.key',key='alt+tab');time.sleep(.4)
        assert active_app(),'Independent operator could not select the owned app'
    def choose(label,index,surface,mode):
        combo=poll(lambda:widget(label,'combo box'),label)
        selected=False
        if 'Selection' in linuxui.interfaces(combo):
            with contextlib.suppress(Exception):selected=combo.select_child(index)
        if not selected:
            activate_app()
            assert combo.grab_focus(),'Native combo focus'
            observer('input.key',key='home')
            for _ in range(index):observer('input.key',key='down')
            observer('input.key',key='enter')
        poll(lambda:policy()['surfaces'][surface]['mode']==mode,label+' applied')
        check('Settings applies '+surface+' '+mode,True)
    try:
        env=dict(os.environ)
        for name,suffix in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state')]:env[name]=str(args.output/suffix)
        app=subprocess.Popen([str(args.app)],env=env,stdout=log,stderr=log,start_new_session=True)
        poll(lambda:plain('status')['data'].get('ready'),'packaged companion')
        check('exact packaged runtime source',plain('status')['data']['sourceRevision']==args.revision)
        receipt=json.loads((args.runtime/'desktop-runtime.json').read_text())
        def policy_child():
            found=[]
            for process in Path('/proc').iterdir():
                if not process.name.isdecimal() or not owned_pid(int(process.name)):continue
                with contextlib.suppress(OSError,ValueError):
                    command=(process/'cmdline').read_bytes().split(b'\0')
                    if command and command[0].endswith(b'/shared-policy/node'):
                        found.append(Path(os.fsdecode(command[0])).parent)
            return found[0] if len(found)==1 else None
        child_root=poll(policy_child,'owned packaged policy child')
        check('actual child uses installed usr share policy',child_root.parts[-4:]==('usr','share','machine-control','shared-policy'))
        check('actual running policy matches complete pinned receipt',all(
            hashlib.sha256((child_root/entry['path']).read_bytes()).hexdigest()==entry['sha256'] for entry in receipt['policyFiles']))

        check('packaged app starts both surfaces Off',all(s['mode']=='off' for s in policy()['surfaces'].values()))
        poll(lambda:widget('Desktop access mode','combo box'),'shared Settings modes')
        check('real Settings exposes independent modes',widget('Browser access mode','combo box') is not None)
        activate_app()
        picture=observer('capture',target='active_window')['data']['artifact']
        image=Path(picture['guestPath']);content=image.read_bytes()
        check('independent Settings capture hash',hashlib.sha256(content).hexdigest()==picture['sha256'])
        (args.output/'settings.png').write_bytes(content);image.unlink()
        choose('Desktop access mode',1,'desktop','ask')
        oracle=args.output/'effect.json';unit='mc-surface-installed-'+str(os.getpid())+'.service'
        subprocess.run(['/usr/bin/systemd-run','--user','--quiet','--collect','--unit',unit,
            '/usr/bin/python3',str(args.fixture),'--state',str(oracle)],check=True,stdout=log,stderr=log)
        poll(oracle.exists,'independent owned fixture')
        # A real local claim and the exact bundled interpreter/client adapter.
        acquired=subprocess.run([*cli,'claim-acquire','--json','--duration-seconds','900',
            '--reason','Qualify packaged Settings and the shipped SDK','--claimant-authority','machine-control-native-acceptance',
            '--claimant-id','fixture-'+uuid.uuid4().hex],capture_output=True,text=True,check=True)
        claim=json.loads(acquired.stdout)['data']['claim']['claimId']
        target=dict(platform='linux',command=cli,claimPolicy='required',_claimId=claim,
            environment={'MACHINE_CONTROL_CLAIM_ID':claim})
        sdk=ControlSession(target,reason='Verify packaged unified Desktop',surfaces=['desktop'],wait=180,duration=180)
        poll(lambda:sdk.status()['state']=='waiting_for_approval','Ask first task')
        press('Allow this task',True);poll(lambda:sdk.status()['state']=='announcing','native task warning')
        press('Start now',True);sdk.wait();check('shipped SDK negotiates and activates',sdk.view['state']=='active')
        capabilities=sdk.call({'operation':'capabilities'})
        check('controlled capabilities match the shared contract',capabilities['accepted'] and capabilities['data']['privilege']=='ordinary_user')
        snapshot=sdk.call({'operation':'snapshot','target':'machine-control-surface-fixture','maxDepth':16})
        check('packaged controlled native snapshot',snapshot['accepted'])
        button=next(row for row in snapshot['data']['elements'] if row['label']=='Increment fixture')
        delivered=sdk.call({'operation':'action','reference':button['reference']})
        check('packaged native effect delivery',delivered['accepted'])
        poll(lambda:json.loads(oracle.read_text())['count']==1,'independent packaged native effect')
        check('independent packaged native effect',True)
        press('Pause desktop 30s');poll(lambda:sdk.status()['state']=='paused','surface pause')
        check('independent Browser remains Off',policy()['surfaces']['browser']['mode']=='off')
        press('Resume desktop');poll(lambda:sdk.status()['state']=='announcing','fresh resumed warning');press('Start now',True);sdk.wait()
        check('Settings Resume restores a fresh live session',sdk.view['state']=='active')
        press('Stop all access');poll(lambda:sdk.status()['state']=='ended','native Stop')
        check('Settings Stop turns both surfaces Off',all(s['mode']=='off' for s in policy()['surfaces'].values()))
        sdk.close();sdk=None
        choose('Desktop access mode',2,'desktop','automatic')
        sdk=ControlSession(target,reason='Verify packaged Automatic warning',surfaces=['desktop'],wait=120,duration=60)
        poll(lambda:sdk.status()['state']=='announcing','automatic notice');sdk.wait()
        check('packaged Automatic warns then starts',sdk.view['state']=='active')
        if args.remote_handoff:
            sdk.close();sdk=None
            (args.output/'remote-ready.json').write_text(json.dumps({'ready':True}))
            poll(lambda:(args.output/'remote-finished').exists(),'outside SDK actor',180)
            poll(lambda:json.loads(oracle.read_text())['count']==2,'independent outside SDK effect')
            check('outside SDK effect reaches the same packaged provider',True)
            poll(lambda:policy()['active']==0,'outside owner EOF cleanup')
            check('outside owner closes without disabling consent',policy()['surfaces']['desktop']['mode']=='automatic')
        press('Stop all access')
        if sdk:sdk.close();sdk=None
        # The real permissions UI includes the separate native observer setup.
        press('Permissions')
        check('native read-only observer setup is visible',poll(lambda:widget('Set up activity observer'),'activity observer setup') is not None)
        # End the exact owned app; its native children follow inherited lifetime.
        os.killpg(app.pid,signal.SIGTERM);app.wait(15)
        poll(lambda:not endpoint.exists(),'owned companion endpoint cleanup')
        check('packaged app revokes on exit',True)
    except BaseException as error:
        failure=type(error).__name__+': '+str(error)
        with contextlib.suppress(Exception):
            (args.output/'ui.private.json').write_text(json.dumps([i for _,i in nodes()]))
        raise
    finally:
        if sdk:
            with contextlib.suppress(Exception):sdk.close()
        if claim:
            released=subprocess.run([*cli,'claim-release','--json','--claim-id',claim],capture_output=True,text=True)
            if released.returncode and failure is None:failure='Local acceptance claim release failed'
        if unit:subprocess.run(['/usr/bin/systemctl','--user','stop',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if app and app.poll() is None:
            os.killpg(app.pid,signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):app.wait(10)
            if app.poll() is None:os.killpg(app.pid,signal.SIGKILL);app.wait(5)
        log.close();report(True)


if __name__=='__main__':main()

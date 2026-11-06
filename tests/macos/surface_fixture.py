"""Native operator and shipped-SDK composition for dedicated Mac fixtures.

This is test infrastructure, never an operator endpoint or policy authority.
All arming goes through actual Settings; all effects use retained SDK owners.
"""
import concurrent.futures
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def poll(function, label, timeout=45):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=function()
        if value:return value
        time.sleep(.15)
    raise AssertionError('Timed out: '+label)


def require_managed_observer(value):
    """Require the explicitly installed appliance administration plane."""
    policy=value['deployment']['policy']
    assert policy['preset'] in {'appliance','unattended'}
    assert policy['grantMode']=='standing' or (
        policy['grantMode']=='surface_modes' and policy.get('protectedAdministration') is True)
    assert value['nativeSemanticState']=='ready'


def generation_bound_status(observe):
    """Reobserve only a read-only status fenced by a generation transition."""
    def fresh():
        result=observe()
        if result.get('accepted'):return result
        assert result.get('errorCode')=='control_generation_changed',result.get('errorCode')
        return None
    return poll(fresh,'fresh generation-bound fixture status',timeout=10)


class SurfaceFixture:
    def __init__(self, source, resident, endpoint, observer, claim,*,source_sdk=False):
        self.source,self.resident,self.endpoint,self.observer,self.claim=Path(source),Path(resident),Path(endpoint),Path(observer),claim
        self.owners={};self.observer_owner=None;self.profiles=[]
        spec=importlib.util.spec_from_file_location('surface_actor',self.source/'tests/macos/surface-policy-live.py')
        self.actor=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.actor)
        sys.dont_write_bytecode=True
        runtime=self.resident.parents[1]/'Resources/mc-cli'
        sdk_root=self.source/'client' if source_sdk else runtime/'client'
        sys.path.insert(0,str(sdk_root))
        from control_session import ControlSession
        assert Path(sys.modules[ControlSession.__module__].__file__).resolve().is_relative_to(sdk_root.resolve()),'SDK module origin does not match the selected test mode'
        self.sdk=ControlSession
        self.target=dict(platform='macos',command=[str(runtime/'python/bin/python3'),'-I','-B',str(runtime/'platforms/macos/host/machost.py')],_claimId=claim)

    def exchange(self,path,operation,**fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(35);channel.connect(str(path))
            channel.sendall(json.dumps(dict(operation=operation,claimId=self.claim,**fields)).encode()+b'\n')
            line=channel.makefile('rb').readline(32*1024*1024)
            if not line:raise ConnectionError('Native fixture transport closed; no replay')
            return json.loads(line)

    def status(self):
        return generation_bound_status(lambda:self.exchange(self.endpoint,'status'))['data']

    def observer_response(self,operation,**fields):
        if operation in {'status','capabilities','authorization.begin'}:
            return self.exchange(self.observer,operation,provider='macos-native',**fields)
        if self.observer_owner is None:
            result=self.exchange(self.observer,operation,provider='macos-native',**fields)
            if result.get('errorCode')!='control_session_required':
                return result
            assert result.get('delivery')=='refused' and result.get('uncertainty')=='none'
            class RenewingObserver(self.actor.Owner):
                def keepalive(owner):
                    while not owner.stopped.wait(1.5):
                        try:
                            view=owner.rpc(operation='control.heartbeat')
                            if view.get('state')=='active' and view.get('renewal')=='owner_connection/v1' and view.get('activeRemainingSeconds',900)<=300:
                                renewed=owner.rpc(operation='control.renew',durationSeconds=900)
                                assert renewed['sessionId']==view['sessionId'] and renewed['resourceGenerations']==view['resourceGenerations']
                        except Exception as error:
                            owner.failure=type(error).__name__;return
            self.observer_owner=RenewingObserver(self.observer,self.claim,['desktop'],duration=900)
            self.observer_owner.wait()
        result=self.observer_owner.call(operation,provider='macos-native',**fields)
        return result

    def observe(self,operation,**fields):
        result=self.observer_response(operation,**fields)
        assert result.get('accepted'),result.get('errorCode')
        return result.get('data',{})

    def tree(self,query='',target=None):
        return self.observe('snapshot',target=str(target or self.status()['processId']),query=query,projection='full',maxDepth=40,maxElements=2000)['elements']

    def find(self,label,role='AXButton',partial=False):
        rows=[row for row in self.tree(label) if row.get('role')==role and any((label in str(row.get(key,'')) if partial else label==row.get(key)) for key in ['label','title','description'])]
        rows.sort(key=lambda row:row.get('depth',1000))
        return rows[0] if rows and (len(rows)==1 or rows[0].get('depth')!=rows[1].get('depth')) else None

    def press(self,label,role='AXButton',partial=False):
        row=poll(lambda:self.find(label,role,partial),'operator '+label)
        self.observe('action',reference=row['reference'],action='press')

    def settings(self):
        subprocess.run([str(self.resident),'serve',str(self.endpoint),'--settings'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20)
        self.press('Access')

    def choose(self,label,index):
        self.observe('application.activate',target=str(self.status()['processId']))
        self.press(label,'AXPopUpButton')
        for key in (['end','enter'] if index==2 else ['home']+['down']*index+['enter']):
            self.observe('input.key',key=key)
        time.sleep(.3)

    def options(self):
        if not self.find('Access lifetime','AXPopUpButton'):
            row=poll(lambda:self.find('More options','AXDisclosureTriangle') or self.find('More options'),'access options disclosure')
            self.observe('action',reference=row['reference'],action='press')
            poll(lambda:self.find('Access lifetime','AXPopUpButton'),'expanded access options')

    def switch(self,label):
        row=poll(lambda:next((value for role in ['AXSwitch','AXCheckBox','AXButton']
            if (value:=self.find(label,role))),None),'operator switch '+label)
        self.observe('action',reference=row['reference'],action='press')

    def apply(self,timeout=2):
        deadline=time.monotonic()+timeout
        row=self.find('Apply changes')
        while row is None and time.monotonic()<deadline:
            time.sleep(.1);row=self.find('Apply changes')
        if row:
            assert not self.find('Access changed elsewhere. Discard edits to reload.','AXStaticText'),'Access draft conflicts with a concurrent operator change'
            self.observe('action',reference=row['reference'],action='press')
            poll(lambda:not self.find('Apply changes'),'applied access choices')

    def select_profiles(self,ids):
        ids=set(ids)
        profiles=self.status()['browser']['profiles']
        labels={'Allow profile '+p['name'] for p in profiles if p['profileId'] in ids}
        assert len(labels)==len(ids), 'Fixture profiles must have unique native labels'
        for label in sorted(labels):poll(lambda:self.find(label,'AXCheckBox'),'visible '+label)
        for _ in range(70):
            rows=[r for r in self.tree() if r.get('role')=='AXCheckBox' and str(r.get('label','')).startswith(('Allow profile ','Unavailable profile'))]
            change=next((r for r in rows if (str(r.get('value','')).lower() in {'1','true'}) != (r.get('label') in labels)),None)
            if change is None:break
            self.observe('action',reference=change['reference'],action='press');time.sleep(.1)
        else:raise AssertionError('Profile selection did not settle')
        self.profiles=sorted(ids)

    def arm(self,mode='automatic',surfaces=('desktop','browser')):
        self.close_owners();self.settings();self.options()
        if 'browser' in surfaces:self.select_profiles(self.profiles)
        self.choose('Access lifetime',0)
        for surface in surfaces:
            self.choose(surface.title()+' before starting',2 if mode=='ask' else 1)
            current=self.status()['admission']['surfaces'][surface]
            if current['mode']=='off':
                self.switch(surface.title()+' access')
                poll(lambda:self.status()['admission']['surfaces'][surface]['mode']==mode,surface+' enabled')
        self.apply()
        for surface in surfaces:
            poll(lambda:self.status()['admission']['surfaces'][surface]['mode']==mode,surface+' '+mode)
        assert all(self.status()['admission']['surfaces'][name]['consentRemainingSeconds'] is None for name in surfaces)

    def owner(self,surface,duration=900,renew=None):
        surfaces=['desktop','browser'] if surface=='both' else [surface]
        assert not self.owners,'Close the previous human-input owner before opening a new phase'
        owner=self.sdk(self.target,reason='Qualify exact packaged '+surface+' behavior',surfaces=surfaces,profile_ids=self.profiles if 'browser' in surfaces else [],duration=duration,wait=180,renew=renew)
        self.bind_owner(owner,surfaces)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            waiting=pool.submit(owner.wait)
            deadline=time.monotonic()+120
            diagnosed=False
            try:
                while not waiting.done():
                    assert time.monotonic()<deadline,'Native surface approval did not complete'
                    state=owner.status()['state']
                    row=self.find('Allow now') if state=='waiting_for_approval' else None
                    if row:self.observe('action',reference=row['reference'],action='press')
                    elif state=='waiting_for_approval' and not diagnosed and time.monotonic()>deadline-110:
                        diagnosed=True
                        print('SURFACE_APPROVAL_DIAGNOSTIC '+json.dumps({
                            'buttons':[r.get('label') for r in self.tree() if r.get('role')=='AXButton'],
                            'requests':[{k:r.get(k) for k in ['state','surfaces']} for r in self.status()['admission']['requests']]}),flush=True)
                    time.sleep(.2)
                waiting.result()
            except BaseException:
                owner.close()
                raise
        return owner

    def dispatch(self,operation,**fields):
        surface='browser' if operation.startswith('browser.') else 'desktop'
        owner=self.owners.get(surface)
        assert owner is not None,'Fixture has no retained '+surface+' owner'
        return owner.call(dict(operation=operation,**fields))

    def stop(self,require_active=True):
        self.settings()
        started=time.monotonic()
        active=any(v['mode']!='off' for v in self.status()['admission']['surfaces'].values())
        assert active or not require_active,'Stop responsiveness requires enabled access before the operator press'
        if not active:
            self.close_owners();return None
        self.switch('Agent access')
        poll(lambda:all(v['mode']=='off' for v in self.status()['admission']['surfaces'].values()),'native Stop')
        acknowledged=time.monotonic()-started
        self.close_owners()
        return acknowledged

    def close_owners(self):
        for owner in set(self.owners.values()):
            with contextlib.suppress(Exception):owner.close()
        self.owners.clear()

    def bind_owner(self,owner,surfaces):
        for surface in surfaces:self.owners[surface]=owner

    def close(self):
        self.close_owners()
        self.close_observer()

    def close_observer(self):
        if self.observer_owner is not None:self.observer_owner.close();self.observer_owner=None


class SDKOwnerProcess:
    """Process-shaped fixture handle over one real shipped SDK connection.

    The asynchronous first read triggers native protected preparation. Polling
    observes actual SDK/native endings; it never creates or retries an owner.
    """
    def __init__(self,rig,duration,target,status):
        self.rig=rig;self.status=status;self.control_id=None;self.returncode=None;self.first_reply=None;self.browser_reply=None
        rig.close_owners()
        surfaces=['desktop','browser'] if rig.profiles else ['desktop']
        self.session=rig.sdk(rig.target,reason='Qualify finite protected owner',surfaces=surfaces,profile_ids=rig.profiles,duration=duration,wait=180,renew=False)
        rig.bind_owner(self.session,surfaces)
        self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
        def begin():
            self.session.wait()
            reply=self.session.call(dict(operation='snapshot',provider='macos-native',target=str(target),maxDepth=8,maxElements=500))
            self.first_reply=reply
            if not reply.get('accepted'):
                print('COVERED_FIRST_READ_REFUSAL '+json.dumps({k:reply.get(k) for k in ['errorCode','delivery','effect','uncertainty','retrySafety','actualRoute']}),flush=True)
            assert reply.get('accepted'),reply.get('errorCode')
            if 'browser' in surfaces:
                self.browser_reply=self.session.call(dict(operation='browser.tabs'))
                if not self.browser_reply.get('accepted'):
                    print('COVERED_BROWSER_PREFLIGHT_REFUSAL '+json.dumps({k:self.browser_reply.get(k) for k in ['errorCode','delivery','effect','uncertainty','retrySafety','actualRoute']}),flush=True)
                assert self.browser_reply.get('accepted'),self.browser_reply.get('errorCode')
                assert self.browser_reply.get('data',{}).get('tabs'),'Hybrid owner needs an established exact-profile Browser route before faults'
            return reply
        self.future=self.pool.submit(begin)

    @property
    def activation_reads_finished(self):
        return self.future.done()

    def poll(self):
        if self.returncode is not None:return self.returncode
        if not self.future.done():return None
        if self.future.exception() is not None:self.returncode=1;return 1
        current=self.status()['lockedUse']
        if current['phase']=='active' and current['controlSessionId'] is not None:
            if self.control_id is None:self.control_id=current['controlSessionId']
            assert current['controlSessionId']==self.control_id,'Protected owner changed without a new task'
        elif self.control_id is not None:
            assert current.get('lastEndedReason'),'Native owner disappeared without an ending reason'
            self.returncode=0
        return self.returncode

    def communicate(self,timeout=15):
        poll(lambda:self.poll() is not None,'finite SDK owner ending',timeout)
        current=self.status()['lockedUse']
        result=dict(accepted=self.returncode==0,data=dict(reason=current.get('lastEndedReason')))
        if self.returncode and self.future.done():
            error=self.future.exception()
            refused=next((r for r in [self.first_reply,self.browser_reply] if r is not None and not r.get('accepted')),None)
            result['errorCode']=(refused or {}).get('errorCode') or getattr(error,'code',type(error).__name__)
            if refused is not None:result['firstRead']={k:refused.get(k) for k in ['delivery','effect','uncertainty','retrySafety','actualRoute']}
        self.terminate()
        return json.dumps(result).encode(),b''

    def terminate(self):
        self.session.close()
        for surface,owner in list(self.rig.owners.items()):
            if owner is self.session:self.rig.owners.pop(surface)
        self.pool.shutdown(wait=False,cancel_futures=True)


def launch_profile(rig,root,name='Reboot fixture'):
    """Enable one isolated real CfT installation through its own panel."""
    import plistlib
    import shutil
    from urllib.request import urlopen
    spec=importlib.util.spec_from_file_location('fixture_cdp',rig.source/'platforms/chromeos/cdp.py')
    cdp=importlib.util.module_from_spec(spec);spec.loader.exec_module(cdp)
    app=Path.home()/'mc-cft/chrome-mac-arm64/Google Chrome for Testing.app'
    info=plistlib.loads((app/'Contents/Info.plist').read_bytes())
    assert info['CFBundleIdentifier']=='com.google.chrome.for.testing'
    profile=root/'reboot-profile';hosts=profile/'NativeMessagingHosts';hosts.mkdir(parents=True)
    extension=root/'reboot-extension';shutil.copytree(rig.resident.parents[1]/'Resources/chrome-extension',extension)
    extension_id='ncbfifkjllmnkkjmomjohinigfgdocjc'
    (hosts/'org.machine_control.browser.json').write_text(json.dumps(dict(name='org.machine_control.browser',description='Owned release fixture',path=str(rig.resident),type='stdio',allowed_origins=['chrome-extension://'+extension_id+'/'])))
    child=subprocess.Popen([str(app/'Contents/MacOS'/info['CFBundleExecutable']),'--user-data-dir='+str(profile),'--remote-debugging-port=0','--no-first-run','--no-default-browser-check','--use-mock-keychain','--no-proxy-server','--disable-extensions-except='+str(extension),'--load-extension='+str(extension),'about:blank'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
    try:
        portfile=profile/'DevToolsActivePort';poll(portfile.exists,'isolated profile readiness')
        port,path=portfile.read_text().splitlines()[:2];connection=cdp.CDP('ws://127.0.0.1:'+port+path)
        try:
            for url in ['chrome://extensions/','chrome-extension://'+extension_id+'/panel.html']:
                pageid=connection.call('Target.createTarget',url=url)['targetId']
                try:
                    def page_info():
                        with urlopen('http://127.0.0.1:'+port+'/json/list',timeout=5) as response:return next((r for r in json.load(response) if r['id']==pageid),None)
                    page=cdp.CDP(poll(page_info,'native setup page')['webSocketDebuggerUrl'])
                    try:
                        if url.startswith('chrome://'):expression='new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))'
                        else:
                            time.sleep(1)
                            expression="document.getElementById('profile-name').value="+json.dumps(name)+";document.getElementById('profile-enabled').checked=true;document.getElementById('profile-enabled').dispatchEvent(new Event('change'));true"
                        page.call('Runtime.evaluate',expression=expression,awaitPromise=True)
                    finally:page.close()
                finally:connection.call('Target.closeTarget',targetId=pageid)
        finally:connection.close()
        profiles=poll(lambda:[p for p in rig.status()['browser']['profiles'] if p['name']==name and p['connected'] and p['enabled']],'enabled named fixture profile')
        assert len(profiles)==1;rig.profiles=[profiles[0]['profileId']]
        return child
    except BaseException:
        child.terminate()
        try:child.wait(10)
        except subprocess.TimeoutExpired:child.kill();child.wait(5)
        raise

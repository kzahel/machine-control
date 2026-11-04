#!/usr/bin/env python3
"""Two real test-browser profiles and shared owner-bound CDP on Linux."""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import urlopen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','source-root','output','chrome'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--locked',action='store_true',help='Dedicated appliance only; caller owns final locked shutdown')
    args=parser.parse_args();args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(SystemExit(143)))
    def load(name,path):
        spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    actor=load('surface_owner',args.source_root/'tests/macos/surface-policy-live.py')
    cdp=load('fixture_cdp',args.source_root/'platforms/chromeos/cdp.py')
    checks=[];children=[];owners=[];failure=None;child=None;web=None;clipboard=None;clipboard_changed=False
    log=(args.output/'browser.log').open('w');effects={'Work':0,'Personal':0}
    def report(complete=False):
        (args.output/'summary.json').write_text(json.dumps(dict(complete=complete,passed=complete and failure is None,
            failure=failure,checks=checks,effects=effects),indent=2))
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)));report()
        if not value:raise AssertionError(name)
    def poll(fn,label,timeout=30):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                value=fn()
                if value:return value
            except (OSError,ConnectionError):pass
            time.sleep(.15)
        raise AssertionError('Timed out: '+label)
    def operator(method,**fields):
        child.stdin.write(json.dumps(dict(method=method,**fields))+'\n');child.stdin.flush()
        assert select.select([child.stdout],[],[],10)[0],'Private operator deadline'
        reply=json.loads(child.stdout.readline());assert reply['ok'],reply
        return reply
    def state():return operator('state')['state']
    def owner(profiles,operations=None):
        value=actor.Owner(endpoint,'fixture',['browser'],profiles=profiles,operations=operations,duration=180)
        owners.append(value);value.wait();return value
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def do_GET(self):
            name=self.path.strip('/').split('?',1)[0]
            if name not in effects:self.send_error(404);return
            body=("<!doctype html><title>"+name+" fixture</title><button onclick=\"fetch('/"+name+"',{method:'POST'})\">Increment</button>").encode()
            self.send_response(200);self.send_header('Content-Type','text/html');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_POST(self):
            name=self.path.strip('/')
            if name not in effects:self.send_error(404);return
            effects[name]+=1;self.send_response(204);self.end_headers()
    try:
        env=dict(os.environ)
        for name,suffix in [('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data'),('XDG_STATE_HOME','state')]:env[name]=str(args.output/suffix)
        child=subprocess.Popen(['/usr/bin/python3',str(args.runtime/'desktop.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=log,text=True,env=env)
        operator('hello',processId=os.getpid(),executable='/usr/bin/true')
        poll(lambda:state()['safetyAvailable'] and state()['permissions']['accessibility'],'native readiness')
        endpoint=Path(state()['socket'])
        previous=subprocess.run(['/usr/bin/wl-paste','--no-newline','--type','text/plain'],capture_output=True,timeout=3)
        clipboard=previous.stdout if previous.returncode==0 else None
        assert clipboard is None or len(clipboard)<=2*1024*1024,'Clipboard exceeds restoration bound'
        operator('browser.setup',bundled=True);clipboard_changed=True
        extension=Path(env['XDG_DATA_HOME'])/'machine-control/extension';extension_id='ncbfifkjllmnkkjmomjohinigfgdocjc'
        web=ThreadingHTTPServer(('127.0.0.1',0),Fixture);threading.Thread(target=web.serve_forever,daemon=True).start()
        for name in effects:
            profile=args.output/name;url=f'http://127.0.0.1:{web.server_port}/{name}'
            hosts=profile/'NativeMessagingHosts';hosts.mkdir(parents=True)
            # Chromium resolves user-level native hosts from its user-data root.
            # Both roots are separately owned test profiles, never the primary
            # installed browser's identity or configuration.
            manifest=hosts/'org.machine_control.browser.json'
            shutil.copyfile(Path(env['XDG_CONFIG_HOME'])/'chromium/NativeMessagingHosts'/manifest.name,manifest)
            manifest.chmod(0o600)
            chrome=subprocess.Popen([str(args.chrome),'--user-data-dir='+str(profile),'--remote-debugging-port=0',
                '--no-first-run','--no-default-browser-check','--no-proxy-server','--no-sandbox',
                '--disable-gpu','--ozone-platform=wayland','--password-store=basic',
                '--disable-extensions-except='+str(extension),'--load-extension='+str(extension),url],
                env=env,stdout=log,stderr=log,start_new_session=True);children.append(chrome)
            port_file=profile/'DevToolsActivePort';poll(port_file.exists,'owned browser')
            port,path=port_file.read_text().splitlines()[:2];connection=cdp.CDP('ws://127.0.0.1:'+port+path)
            try:
                for page_url in ['chrome://extensions/','chrome-extension://'+extension_id+'/panel.html']:
                    target=connection.call('Target.createTarget',url=page_url)['targetId']
                    def info():
                        with urlopen('http://127.0.0.1:'+port+'/json/list',timeout=5) as response:
                            return next((row for row in json.load(response) if row['id']==target),None)
                    page=cdp.CDP(poll(info,'extension preferences')['webSocketDebuggerUrl'])
                    try:
                        ready=("typeof chrome!=='undefined' && !!chrome.developerPrivate" if page_url.startswith('chrome://')
                            else "!!document.getElementById('profile-name') && !document.getElementById('profile-card').hidden")
                        poll(lambda:page.call('Runtime.evaluate',expression=ready).get('result',{}).get('value'),
                            'loaded extension preferences')
                        expression=('new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))'
                            if page_url.startswith('chrome://') else "document.getElementById('profile-name').value="+json.dumps(name)+";document.getElementById('profile-enabled').checked=true;document.getElementById('profile-enabled').dispatchEvent(new Event('change'));true")
                        response=page.call('Runtime.evaluate',expression=expression,awaitPromise=True)
                        if 'exceptionDetails' in response:print(json.dumps(response),file=log,flush=True)
                        assert 'exceptionDetails' not in response,'Extension preference setup failed'
                    finally:page.close();connection.call('Target.closeTarget',targetId=target)
            finally:connection.close()
        profiles=poll(lambda:(rows if len(rows:=state()['browser']['profiles'])==2 and all(p['enabled'] and p['connected'] for p in rows) else None),'two enabled profiles')
        ids={p['name']:p['profileId'] for p in profiles}
        check('two independently named real profiles stay connected',set(ids)=={'Work','Personal'})
        operator('surface.configure',surface='browser',mode='automatic',lifetime='until_stopped',duration=0,browserProfileIds=[ids['Work']])
        check('Browser mode does not arm Desktop',state()['accessPolicy']['surfaces']['desktop']['mode']=='off')
        read=owner([ids['Work']],['browser.tabs','browser.snapshot'])
        tabs=read.call('browser.tabs',browserProfileId=ids['Work']);check('exact profile tabs',tabs['accepted'])
        def fixture_tab():
            reply=read.call('browser.tabs',browserProfileId=ids['Work'])
            (args.output/'tabs.private.json').write_text(json.dumps(reply))
            return next((row for row in reply.get('data',{}).get('tabs',[]) if row.get('url','').endswith('/Work')),None)
        tab=poll(fixture_tab,'loaded Work fixture')['tabId']
        read.close();owners.remove(read)
        work=owner([ids['Work']])
        snap=work.call('browser.snapshot',browserProfileId=ids['Work'],tabId=tab);check('controlled profile AX snapshot',snap['accepted'])
        button=next(row for row in snap['data']['elements'] if row['name']=='Increment' and row['role']=='button')
        click=work.call('browser.click',browserProfileId=ids['Work'],reference=button['reference'])
        check('selected profile click delivered',click['accepted']);poll(lambda:effects['Work']==1,'HTTP effect')
        check('independent Work effect and zero Personal effects',effects=={'Work':1,'Personal':0})
        wrong=work.call('browser.tabs',browserProfileId=ids['Personal']);check('unapproved profile refused',not wrong['accepted'])
        endpoint_reply=work.call('browser.endpoint',browserProfileId=ids['Work']);check('owner-bound streamed CDP endpoint',endpoint_reply['accepted'])
        stream=cdp.CDP(endpoint_reply['data']['browserEndpoint'])
        try:
            result=stream.call('Browser.getVersion');check('real streamed CDP command',bool(result.get('product')))
            operator('stop');check('Stop leaves both profiles connected',all(p['connected'] for p in state()['browser']['profiles']))
            try:stream.call('Browser.getVersion');revoked=False
            except (OSError,ConnectionError,RuntimeError,ValueError):revoked=True
            check('Stop revokes retained CDP stream',revoked)
        finally:stream.close()
        check('Stop turns both surfaces Off',all(s['mode']=='off' for s in state()['accessPolicy']['surfaces'].values()))
        work.close();owners.remove(work)
        operator('surface.configure',surface='desktop',mode='automatic',lifetime='until_stopped',duration=0)
        operator('surface.configure',surface='browser',mode='ask',lifetime='until_stopped',duration=0,browserProfileIds=[ids['Work']])
        desktop=actor.Owner(endpoint,'fixture',['desktop']);owners.append(desktop);desktop.wait()
        pending=actor.Owner(endpoint,'fixture',['browser'],profiles=[ids['Work']],operations=['browser.tabs']);owners.append(pending)
        poll(lambda:pending.status()['state']=='waiting_for_approval','independent Browser approval')
        session=desktop.view['sessionId']
        refused=desktop.call('snapshot',target='gnome-shell',maxDepth=4)
        check('ordinary Shell semantics cannot answer native approval',not refused['accepted'] and refused['errorCode']=='operator_protected')
        refused=desktop.call('input.key',key='enter')
        check('ordinary physical input cannot answer native approval',not refused['accepted'] and refused['errorCode']=='approval_prompt_visible')
        check('native approval interlock preserves independent Desktop owner',desktop.status()['state']=='active' and desktop.view['sessionId']==session and pending.status()['state']=='waiting_for_approval')
        pending.close();owners.remove(pending);desktop.close();owners.remove(desktop);operator('stop')
        if args.locked:
            from gi.repository import Gio,GLib
            bus=Gio.bus_get_sync(Gio.BusType.SESSION,None);system=Gio.bus_get_sync(Gio.BusType.SYSTEM,None)
            def dbus(connection,destination,path,interface,method,parameters=None):
                return connection.call_sync(destination,path,interface,method,parameters,None,Gio.DBusCallFlags.NONE,1000,None).unpack()
            user=dbus(system,'org.freedesktop.login1','/org/freedesktop/login1','org.freedesktop.login1.Manager','GetUser',GLib.Variant('(u)',(os.getuid(),)))[0]
            session=dbus(system,'org.freedesktop.login1',user,'org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.freedesktop.login1.User','Display')))[0][1]
            def locked():
                return dbus(system,'org.freedesktop.login1',session,'org.freedesktop.DBus.Properties','Get',GLib.Variant('(ss)',('org.freedesktop.login1.Session','LockedHint')))[0] is True
            operator('browser_while_locked',enabled=True)
            for surface in ('desktop','browser'):
                operator('surface.configure',surface=surface,mode='automatic',lifetime='until_stopped',duration=0,
                    browserProfileIds=[ids['Work']] if surface=='browser' else [])
            try:dbus(bus,'org.gnome.ScreenSaver','/org/gnome/ScreenSaver','org.gnome.ScreenSaver','Lock')
            except GLib.Error:pass  # Only the independent locked state is evidence.
            poll(locked,'independent GNOME lock')
            poll(lambda:state()['accessPolicy']['surfaces']['browser']['ready'] and
                not state()['accessPolicy']['surfaces']['desktop']['ready'],'independent locked surface floors')
            check('known lock retains consent with Desktop unavailable',all(s['mode']=='automatic' for s in state()['accessPolicy']['surfaces'].values()))
            desktop=actor.Owner(endpoint,'fixture',['desktop']);owners.append(desktop)
            check('locked Desktop request stays queued',desktop.status()['state']=='paused')
            desktop.close();owners.remove(desktop)
            retained=owner([ids['Work']],['browser.tabs','browser.snapshot','browser.click'])
            snap=retained.call('browser.snapshot',browserProfileId=ids['Work'],tabId=tab)
            check('locked selected-profile snapshot',snap['accepted'])
            reference=next(row['reference'] for row in snap['data']['elements'] if row['name']=='Increment')
            delivered=retained.call('browser.click',browserProfileId=ids['Work'],reference=reference)
            check('locked Browser delivery',delivered['accepted'])
            poll(lambda:effects['Work']==2,'independent locked page effect')
            check('independent Browser effect keeps GNOME locked',locked() and effects=={'Work':2,'Personal':0})
            operator('pause_surface',surface='browser',duration=30)
            poll(lambda:retained.status()['state']=='paused','locked Browser pause')
            operator('resume_surface',surface='browser');retained.wait()
            check('locked Resume yields fresh Browser authority',retained.view['state']=='active' and locked())
            operator('browser_while_locked',enabled=False)
            poll(lambda:retained.status()['state']=='paused','locked opt-in withdrawal')
            check('withdrawing locked opt-in leaves OS locked',locked())
            retained.close();owners.remove(retained);operator('stop')
            check('locked Stop ends both surface permissions',all(s['mode']=='off' for s in state()['accessPolicy']['surfaces'].values()) and locked())
        operator('quit');child.wait(10);check('shared child exits cleanly',child.returncode==0)
    except BaseException as error:
        failure=type(error).__name__+': '+str(error)
        with contextlib.suppress(Exception):print(json.dumps(state()),file=log,flush=True)
        raise
    finally:
        for value in owners:
            with contextlib.suppress(Exception):value.close()
        if child and child.poll() is None:
            with contextlib.suppress(Exception):operator('quit');child.wait(10)
            if child.poll() is None:child.kill();child.wait(5)
        for process in children:
            if process.poll() is None:os.killpg(process.pid,signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):process.wait(5)
            if process.poll() is None:os.killpg(process.pid,signal.SIGKILL);process.wait(5)
        if web:web.shutdown()
        if clipboard_changed:
            subprocess.run(['/usr/bin/wl-copy','--clear'] if clipboard is None else ['/usr/bin/wl-copy'],
                input=clipboard,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
        log.close();report(True)


if __name__=='__main__':main()

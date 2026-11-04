#!/usr/bin/env python3
"""Guest-only v2 acceptance using real Settings, native input and extension.

The claimed controller owns installation, independent observer, original-state
restoration and power cleanup. This actor owns only its fixture/browser children.
No operator endpoint or approval hook is added to the product. Raw evidence is
private; printed checks contain no target identity, endpoints or bearer tokens.
"""
import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


def poll(function, label, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = function()
        if value:
            return value
        time.sleep(.15)
    raise AssertionError('Timed out: ' + label)


class Owner:
    def __init__(self, endpoint, claim, surfaces, *, profiles=(), operations=None):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(20)
        self.socket.connect(str(endpoint))
        self.file = self.socket.makefile('rb')
        self.lock = threading.RLock()
        self.sequence = 0
        self.stopped = threading.Event()
        self.failure = None
        request = dict(operation='control.open', schema='machine-control-admission/v2',
                       claimId=claim, surfaces=surfaces, profileIds=list(profiles),
                       waitSeconds=180, durationSeconds=180, reason='Verify unified surface handoff')
        if operations is not None:
            request['operations'] = operations
        self.view = self.rpc(**request)
        self.thread = threading.Thread(target=self.keepalive, daemon=True)
        self.thread.start()

    def rpc(self, **request):
        with self.lock:
            self.sequence += 1
            request.update(requestId=uuid.uuid4().hex, requestSequence=self.sequence)
            self.socket.sendall(json.dumps(request).encode() + b'\n')
            reply = json.loads(self.file.readline(16 * 1024 * 1024))
            assert reply.get('requestId') == request['requestId']
            assert reply.get('accepted'), reply.get('errorCode')
            return reply.get('data', {})

    def keepalive(self):
        while not self.stopped.wait(1.5):
            try:
                self.rpc(operation='control.heartbeat')
            except Exception as error:
                self.failure = type(error).__name__
                return

    def status(self):
        self.view = self.rpc(operation='control.status')
        return self.view

    def wait(self):
        def offered():
            value = self.status()
            assert value['state'] != 'ended', value.get('terminalReason')
            return value if value['state'] == 'offered' else None
        value = poll(offered, 'owner offer', 90)
        self.view = self.rpc(operation='control.accept', offerGeneration=value['offerGeneration'])
        return self.view

    def call(self, operation, **fields):
        return self.rpc(operation='control.dispatch', sessionId=self.view['sessionId'],
                        resourceGenerations=self.view['resourceGenerations'],
                        request=dict(operation=operation, **fields))

    def close(self):
        self.stopped.set()
        if hasattr(self, 'thread'):
            self.thread.join(3)
        with contextlib.suppress(Exception):
            self.rpc(operation='control.cancel')
        self.file.close()
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observer-socket', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--claim', required=True)
    args = parser.parse_args()
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).decode().startswith('VirtualMac')
    endpoint = Path.home() / 'Library/Application Support/MachineControl/control.sock'
    resident = Path.home() / 'Applications/Machine Control.app/Contents/MacOS/macui'
    checks = []
    children = []
    counters = {'Work': 0, 'Personal': 0}

    def check(label, condition=True):
        assert condition, label
        checks.append(label)
        print('PASS: ' + label, flush=True)

    def exchange(path, operation, **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(30)
            channel.connect(str(path))
            channel.sendall(json.dumps(dict(operation=operation, claimId=args.claim, **fields)).encode() + b'\n')
            return json.loads(channel.makefile('rb').readline(16 * 1024 * 1024))

    def status():
        result = exchange(endpoint, 'status')
        assert result.get('accepted'), result.get('errorCode')
        return result['data']

    def observe(operation, **fields):
        result = exchange(args.observer_socket, operation, provider='macos-native', **fields)
        assert result.get('accepted'), result.get('errorCode')
        return result.get('data', {})

    pid = status()['processId']

    def tree(query=''):
        return observe('snapshot', target=str(pid), query=query, projection='full', maxDepth=40, maxElements=2000)['elements']

    def find(label, role=None, partial=False):
        found = [element for element in tree(label) if
                 (label in element.get('label', '') if partial else element.get('label') == label)
                 and (role is None or element.get('role') == role)]
        # The native notice and Settings may expose the same task action.
        # Prefer the unique shallow native panel over the WebView copy.
        found.sort(key=lambda element:element.get('depth',1000))
        return found[0] if found and (len(found)==1 or found[0].get('depth')!=found[1].get('depth')) else None

    def press(label, role='AXButton', partial=False):
        element = poll(lambda: find(label, role, partial), 'operator ' + label)
        observe('action', reference=element['reference'], action='press')

    def choose(label, index):
        observe('application.activate', target=str(pid))
        press(label, 'AXPopUpButton')
        for key in ['up'] * 5 + ['down'] * index + ['enter']:
            observe('input.key', key=key)
        time.sleep(.3)

    def surface(name):
        return status()['admission']['surfaces'][name]

    def settings():
        subprocess.run([str(resident), 'serve', str(endpoint), '--settings'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        press('Access')

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            name = self.path.removeprefix('/')
            body = ('<!doctype html><title>Surface fixture ' + name + '</title>'
                    '<button onclick="fetch(location.pathname,{method:\'POST\'})">Increment fixture</button>').encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            name = self.path.removeprefix('/')
            if name in counters:
                counters[name] += 1
            self.send_response(204)
            self.end_headers()

    web = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=web.serve_forever, daemon=True).start()
    workspace = tempfile.TemporaryDirectory(prefix='mc-surface-fixtures-')
    try:
        initial = status()
        check('packaged v2 engine is live and both surfaces start Off',
              initial['admission']['schema'] == 'machine-control-admission/v2' and
              all(value['mode'] == 'off' for value in initial['admission']['surfaces'].values()))
        check('native physical-input observation is independently healthy', initial['physicalActivity']['healthy'])
        settings()
        choose('Desktop access mode', 1)
        poll(lambda: surface('desktop')['mode'] == 'ask', 'Desktop Ask first')
        check('Settings configures Desktop Ask first independently', surface('browser')['mode'] == 'off')
        with Owner(endpoint,args.claim,['desktop'],operations=['windows']) as owner:
            check('one live task waits for approval', owner.status()['state'] == 'waiting_for_approval')
            press('Allow this task')
            poll(lambda: owner.status()['state'] == 'announcing', 'native warning after approval')
            press('Pause 30 seconds')
            check('task deferral pauses the same request', owner.status()['state'] == 'paused')
            press('Resume desktop')
            poll(lambda: owner.status()['state'] == 'announcing', 'fresh warning after Resume')
            press('Start now')
            owner.wait()
            result = owner.call('windows')
            check('approved task performs a real native observation once', result.get('accepted') is True)
            press('Pause browser 30s') if surface('browser')['mode'] != 'off' else None
            press('Pause desktop until Resume')
            check('native pause fences active Desktop without turning it Off',
                  owner.status()['state'] == 'paused' and surface('desktop')['mode'] == 'ask')
            press('Resume desktop')
            poll(lambda: owner.status()['state'] == 'announcing', 'resumed warning')
            owner.wait()
            check('resumed task receives a fresh owner session', owner.view['state'] == 'active')
        press('Stop all access')
        poll(lambda: surface('desktop')['mode'] == 'off', 'Stop Off')
        check('Stop ends authority; Resume cannot rearm it', surface('browser')['mode'] == 'off')

        root = Path(workspace.name)
        spec = importlib.util.spec_from_file_location('cdp',args.source_root/'platforms/chromeos/cdp.py')
        cdp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cdp)
        browser_app = Path.home()/'mc-cft/chrome-mac-arm64/Google Chrome for Testing.app'
        binary = browser_app/'Contents/MacOS/Google Chrome for Testing'
        assert binary.is_file(), 'Separately identified test browser missing'
        extension = resident.parents[1]/'Resources/chrome-extension'
        assert (extension/'manifest.json').is_file()
        extension_id = 'ncbfifkjllmnkkjmomjohinigfgdocjc'
        for name in ['Work','Personal']:
            profile = root/name
            hosts = profile/'NativeMessagingHosts'
            hosts.mkdir(parents=True)
            (hosts/'org.machine_control.browser.json').write_text(json.dumps(dict(
                name='org.machine_control.browser',description='Owned surface fixture',path=str(resident),type='stdio',
                allowed_origins=['chrome-extension://' + extension_id + '/'])))
            url = 'http://127.0.0.1:' + str(web.server_port) + '/' + name
            child = subprocess.Popen([str(binary),'--user-data-dir='+str(profile),'--remote-debugging-port=0',
                '--no-first-run','--no-default-browser-check','--use-mock-keychain','--no-proxy-server',
                '--disable-extensions-except='+str(extension),'--load-extension='+str(extension),url],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            children.append(child)
            port_file = profile/'DevToolsActivePort'
            poll(port_file.exists,'owned test browser')
            port,path = port_file.read_text().splitlines()[:2]
            connection = cdp.CDP('ws://127.0.0.1:'+port+path)
            try:
                for page_url in ['chrome://extensions/','chrome-extension://'+extension_id+'/panel.html']:
                    target = connection.call('Target.createTarget',url=page_url)['targetId']
                    try:
                        def page_info():
                            with urlopen('http://127.0.0.1:'+port+'/json/list',timeout=5) as response:
                                return next((row for row in json.load(response) if row['id']==target),None)
                        page = cdp.CDP(poll(page_info,'fixture setup page')['webSocketDebuggerUrl'])
                        try:
                            if page_url.startswith('chrome://'):
                                expression = 'new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))'
                            else:
                                time.sleep(1)
                                expression = "document.getElementById('profile-name').value="+json.dumps(name)+";document.getElementById('profile-enabled').checked=true;document.getElementById('profile-enabled').dispatchEvent(new Event('change'));true"
                            page.call('Runtime.evaluate',expression=expression,awaitPromise=True)
                        finally:
                            page.close()
                    finally:
                        connection.call('Target.closeTarget',targetId=target)
            finally:
                connection.close()
        profiles = poll(lambda: status()['browser']['profiles'] if len(status()['browser']['profiles']) == 2 and
                        all(p['enabled'] and p['connected'] for p in status()['browser']['profiles']) else None,'two named enabled profiles')
        ids = {profile['name']:profile['profileId'] for profile in profiles}
        check('two real Chrome profiles remain connected together', set(ids)=={'Work','Personal'})
        settings()
        # Browser fixtures get fresh installation IDs on each run. Remembered
        # form choices are not authority; remove stale/current selections in
        # the real UI before choosing this run's exact Work profile.
        while True:
            selected = [row for row in tree('') if row.get('role')=='AXCheckBox'
                        and row.get('label','').startswith(('Allow profile ','Unavailable profile'))
                        and str(row.get('value','')).lower() in {'1','true'}]
            if not selected:
                break
            observe('action',reference=selected[0]['reference'],action='press')
        press('Work', 'AXCheckBox', partial=True)
        choose('Browser access mode',2)
        poll(lambda: surface('browser')['mode']=='automatic','Browser Automatic')
        check('Browser approval names only Work and leaves Desktop Off',
              surface('browser')['profileIds']==[ids['Work']] and surface('desktop')['mode']=='off')
        with Owner(endpoint,args.claim,['browser'],profiles=[ids['Work']],operations=['browser.tabs','browser.snapshot','browser.click']) as owner:
            owner.wait()
            tabs = owner.call('browser.tabs',browserProfileId=ids['Work'])
            assert tabs.get('accepted'),tabs.get('errorCode')
            tab = next(tab['tabId'] for tab in tabs['data']['tabs'] if tab['url'].endswith('/Work'))
            snapshot = owner.call('browser.snapshot',browserProfileId=ids['Work'],tabId=tab)
            assert snapshot.get('accepted'),snapshot.get('errorCode')
            ref = next(element['reference'] for element in snapshot['data']['elements'] if element.get('name')=='Increment fixture')
            result = owner.call('browser.click',browserProfileId=ids['Work'],reference=ref)
            assert result.get('accepted'),result.get('errorCode')
            poll(lambda:counters['Work']==1,'independent fixture HTTP effect')
            check('selected profile has one independent effect; Personal has none',counters=={'Work':1,'Personal':0})
            settings()
            choose('Desktop access mode',1)
            check('changing Desktop mode preserves active Browser ownership',owner.status()['state']=='active')
            press('Pause desktop 30s')
            check('Desktop pause leaves Browser usable',owner.call('browser.tabs',browserProfileId=ids['Work']).get('accepted') is True)
            press('Pause browser until Resume')
            check('Browser pause fences its owner while retaining consent',owner.status()['state']=='paused' and surface('browser')['mode']=='automatic')
            press('Stop all access')
            check('Stop ends the live Browser owner',owner.status()['state']=='ended')
        check('all profile connections survive Off without reconnect fights',all(p['connected'] for p in status()['browser']['profiles']))
        choose('Browser access mode',2)
        poll(lambda:surface('browser')['mode']=='automatic','Browser for owned CDP stream')
        if any(pause['reason']=='manual' for pause in surface('browser')['pauses']):
            press('Resume browser')
        with Owner(endpoint,args.claim,['browser'],profiles=[ids['Work']]) as owner:
            owner.wait()
            offered = owner.call('browser.endpoint',browserProfileId=ids['Work'])
            assert offered.get('accepted'),offered.get('errorCode')
            address = offered['data']['browserEndpoint']
            stream = cdp.CDP(address)
            try:
                targets = stream.call('Target.getTargets')
                check('owned streamed CDP reaches the selected real browser',any(row.get('url','').endswith('/Work') for row in targets.get('targetInfos',[])))
                press('Stop all access')
                rejected = False
                try:
                    stream.call('Target.getTargets')
                except (OSError,ConnectionError,ValueError,RuntimeError):
                    rejected = True
                check('Stop revokes an already open streamed CDP connection',rejected)
            finally:
                stream.close()

        # Exercise the unchanged shipped Python client, including its owned
        # capabilities negotiation before exact-profile work. Never write
        # bytecode into the sealed candidate while importing the SDK.
        sys.dont_write_bytecode=True
        os.environ['PYTHONDONTWRITEBYTECODE']='1'
        runtime=resident.parents[1]/'Resources/mc-cli'
        sys.path.insert(0,str(runtime/'client'))
        from control_session import ControlSession
        target=dict(platform='macos',command=[str(runtime/'python/bin/python3'),'-I','-B',
            str(runtime/'platforms/macos/host/machost.py')],_claimId=args.claim)
        choose('Browser access mode',2)
        poll(lambda:surface('browser')['mode']=='automatic','Browser for shipped SDK')
        with ControlSession(target,reason='Verify shipped Python profile negotiation',surfaces=['browser'],
                            profile_ids=[ids['Work']],operations=['browser.tabs'],duration=60,wait=120) as sdk:
            sdk.wait()
            result=sdk.call({'operation':'browser.tabs'})
            check('shipped Python SDK negotiates exact profiles on its live owner',result.get('accepted') is True)
        press('Stop all access')
        args.report.write_text(json.dumps({'passed':True,'checks':checks,'checkCount':len(checks),
            'effects':counters,'coverage':['native-settings','shared-admission-v2','native-observation','two-real-profiles','independent-browser-effect'],
            'physicalHidQualification':False,'protectedHelperQualification':False})+'\n')
    except BaseException:
        with contextlib.suppress(Exception):
            args.report.with_name('failure-tree.json').write_text(json.dumps(tree(''))+'\n')
        raise
    finally:
        for child in reversed(children):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(child.pid,signal.SIGTERM)
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid,signal.SIGKILL)
                child.wait(timeout=5)
        web.shutdown()
        workspace.cleanup()


if __name__=='__main__':
    main()

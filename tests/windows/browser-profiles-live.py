"""Claimed-appliance acceptance for the packaged Windows/shared browser path.

Run in the interactive session with a separately identified test Chromium.
The controller owns target claims and power restoration. This actor owns two
scratch Chrome profiles in one browser process, the inherited native operator,
HTTP effect oracle, and temporary native-host registration. No installed
product or ordinary Chrome profile is replaced. Reports remain private.
"""
import argparse
import base64
import ctypes
import faulthandler
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import queue
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import winreg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
from control_session import ControlSession
from cdp_socket import CdpSocket


def poll(observe, seconds=60):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = observe()
        if value:
            return value
        time.sleep(.1)
    raise TimeoutError('Independent observation did not settle')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--chrome', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--settings', action='store_true', help='Also qualify the staged Tauri Settings lifecycle with UI Automation')
    parser.add_argument('--chromium', action='store_true', help='Use the Chromium snapshot native-host registry key')
    parser.add_argument('--profile-data', type=Path, help='Reuse this actor-owned scratch profile directory under output')
    parser.add_argument('--configure-profiles', action='store_true', help='Repeat extension setup when reusing scratch profiles')
    parser.add_argument('--keep-profile-data-on-failure', action='store_true', help='Controller must remove retained scratch profiles after diagnosis')
    parser.add_argument('--browser-startup-seconds', type=int, default=180, choices=range(60, 901), metavar='60..900')
    args = parser.parse_args()
    assert args.chrome.name.lower() == 'chrome.exe'
    assert 'test' in str(args.chrome).lower(), 'Use a separately identified test browser'
    args.output.mkdir(parents=True, exist_ok=True)
    scratch = args.profile_data or args.output / ('profiles-' + uuid.uuid4().hex)
    assert scratch.resolve().parent == args.output.resolve() and scratch.name.startswith('profiles-')
    reused = scratch.exists()
    scratch.mkdir(exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    extension = args.install / 'runtime/browser-extension'
    session = ctypes.c_uint()
    assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    report = dict(schema='machine-control-browser-profiles-live/v1', passed=False, checks=[],
                  runtimeSha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  operatorRoute='inherited_native_operator', browserProfiles=2, browserProcesses=1)
    report['reusedFixtureProfiles'] = reused
    received = []
    processes, sockets = [], []
    runtime = owner = browser = app = None
    debug_port = None
    replies = queue.Queue()
    started = time.monotonic()
    logs = (args.output / 'actor.log').open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(90, repeat=True, file=logs)
    registry_browser = 'Chromium' if args.chromium else r'Google\Chrome'
    key_path = rf'Software\{registry_browser}\NativeMessagingHosts\org.machine_control.browser'
    access = winreg.KEY_READ | winreg.KEY_WOW64_32KEY
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, access) as key:
            old_registry = winreg.QueryValueEx(key, '')
    except FileNotFoundError:
        old_registry = None

    backup = args.output / 'registration-backup.json'
    if backup.exists():
        raise RuntimeError('Restore the previous actor registration backup before starting another run')
    backup.write_text(json.dumps({'registryKey': key_path, 'previous': old_registry}), encoding='utf-8')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self):
            profile = self.path.split('?')[0].strip('/')
            page = '''<!doctype html><meta charset="utf-8"><title>Profile fixture</title>
<button onclick="effect('click',String(event.isTrusted))">Increment fixture</button>
<input aria-label="Message" id="message" onkeydown="if(event.key==='Enter')effect('message',this.value)">
<button onclick="effect('message',document.querySelector('#message').value)">Save message</button>
<input aria-label="Upload fixture" type="file" onchange="this.files[0].arrayBuffer().then(b=>fetch('/effect/PROFILE/upload',{method:'POST',body:b}))">
<button onclick="alert('Fixture dialog')">Open dialog</button>
<script>function effect(action,value){return fetch('/effect/PROFILE/'+action,{method:'POST',body:value})}</script>'''.replace('PROFILE', profile).encode()
            self.send_response(200); self.send_header('Content-Type', 'text/html'); self.end_headers(); self.wfile.write(page)
        def do_POST(self):
            length = int(self.headers.get('Content-Length', '0'))
            if length > 4096: self.send_error(400); return
            received.append((self.path, self.rfile.read(length)))
            self.send_response(200); self.end_headers(); self.wfile.write(b'OK')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'

    def check(value, label):
        assert value, label
        report['checks'].append(label)
        report['elapsedSeconds'] = round(time.monotonic() - started, 2)
        (args.output / 'progress.json').write_text(json.dumps(report), encoding='utf-8')
        print(label, flush=True)
    def operator(method, **fields):
        runtime.stdin.write(json.dumps(dict(method=method, **fields)) + '\n'); runtime.stdin.flush()
        value = replies.get(timeout=60)
        if not value: raise RuntimeError('Native operator disconnected')
        result = json.loads(value)
        assert result.get('ok'), result
        return result
    def start_runtime():
        nonlocal runtime, replies
        replies = queue.Queue()
        runtime = subprocess.Popen([str(exe), 'desktop'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=logs, text=True, encoding='utf-8')
        processes.append(runtime)
        def read():
            for line in runtime.stdout: replies.put(line)
            replies.put(None)
        threading.Thread(target=read, daemon=True).start()
        operator('hello', processId=os.getpid())
        operator('state')
    def direct(operation, **fields):
        value = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', 'desktop',
                                '--session-id', str(session.value)], input=json.dumps(dict(operation=operation, **fields)),
                               capture_output=True, text=True, encoding='utf-8', timeout=60)
        if not value.stdout.strip():
            raise RuntimeError('Resident CLI exited without JSON: '+str(value.returncode)+' '+value.stderr[-1000:])
        return json.loads(value.stdout)
    def profiles(): return operator('state')['state']['browser']['profiles']
    def arm(ids, seconds=900): operator('arm', scopes=['browser', 'devtools'], duration=seconds, browserProfileIds=ids)
    def new_owner():
        nonlocal owner
        owner = ControlSession({'command': [str(exe), 'channel', '--profile', 'user', '--instance', 'desktop',
                                            '--session-id', str(session.value)]},
                               reason='Named-profile appliance acceptance', scopes=['browser', 'devtools'], wait=30, duration=900)
        owner.wait()
    def call(operation, profile=None, **fields):
        if profile is not None: fields['browserProfileId'] = profile
        return owner.call(dict(operation=operation, **fields))
    def accepted(operation, profile=None, **fields):
        value = call(operation, profile, **fields)
        assert value['accepted'], value
        return value['data']
    def launch(profile, url='about:blank', *, headless=False):
        nonlocal debug_port
        forwarding = browser is not None and browser.poll() is None
        if not forwarding:
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                debug_port = reservation.getsockname()[1]
        command = [str(args.chrome), *(['--headless=new', '--allow-chrome-scheme-url'] if headless else []), '--new-window', '--hide-crash-restore-bubble', '--no-first-run', '--no-default-browser-check', '--disable-gpu',
                   '--disable-background-networking', '--disable-component-update',
                   '--remote-debugging-port='+str(debug_port), '--enable-automation', '--remote-allow-origins=*', '--enable-logging=stderr', '--log-level=1',
                   '--user-data-dir=' + str(scratch / 'chrome'), '--profile-directory=' + profile,
                   '--disable-extensions-except=' + str(extension), '--load-extension=' + str(extension), url]
        if forwarding:
            # Forward only a window/profile request to the live singleton.
            # Startup-only debugger and extension flags belong to its first
            # process, rather than a second automation bootstrap.
            command = [str(args.chrome), '--user-data-dir='+str(scratch/'chrome'),
                       '--profile-directory='+profile, '--new-window', '--no-first-run', '--no-default-browser-check', url]
        value = subprocess.Popen(command, stdout=logs, stderr=logs)
        processes.append(value)
        return value
    def browser_socket():
        def ready():
            if browser and browser.poll() is not None: raise RuntimeError('Test browser exited before DevTools: '+str(browser.returncode))
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json/version', timeout=1) as response:
                    return json.load(response)['webSocketDebuggerUrl']
            except (OSError, ValueError): return None
        value = CdpSocket(poll(ready, seconds=180), timeout=60)
        sockets.append(value)
        command = value.call('Browser.getBrowserCommandLine')['result']['arguments']
        assert '--user-data-dir='+str(scratch/'chrome') in command, 'Only attach the exact owned test browser'
        return value
    def stop_browser():
        try: browser_socket().call('Browser.close')
        except (ConnectionError, OSError): pass
        if browser and browser.poll() is None: browser.wait(timeout=15)
        poll(lambda: not any(p['connected'] for p in profiles()))
    def effect(profile, action, body):
        poll(lambda: (f'/effect/{profile}/{action}', body) in received)
    def snapshot(profile, tab): return accepted('browser.snapshot', profile, tabId=tab)['elements']
    def ref(elements, name): return next(e['reference'] for e in elements if e['name'] == name)

    def open_second_profile():
        # Use the real profile switcher. A forwarded automation command can
        # acknowledge startup without opening another regular-profile window.
        # This is fixture setup before browser effects, never resident consent.
        quote = lambda value: "'"+str(value).replace("'", "''")+"'"
        script = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class FixtureProfileInput {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint flags,uint x,uint y,uint data,UIntPtr extra);
}
'@
$browserPid=BROWSER_PID
function FindButton($name){
 $roots=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,$browserPid))
 foreach($root in $roots){
  $item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,$name),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)))
  if($item){return $item}
 }
}
function Press($item){
 $pattern=$null
 try{if($item.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){$pattern.Invoke();return}}catch{}
 try{if($item.TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$pattern)){$pattern.Expand();return}}catch{}
 try{if($item.TryGetCurrentPattern([Windows.Automation.LegacyIAccessiblePattern]::Pattern,[ref]$pattern)){$pattern.DoDefaultAction();return}}catch{}
 $rect=$item.Current.BoundingRectangle
 [FixtureProfileInput]::SetCursorPos([int]($rect.Left+$rect.Width/2),[int]($rect.Top+$rect.Height/2))|Out-Null
 [FixtureProfileInput]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 [FixtureProfileInput]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
}
$until=[DateTime]::UtcNow.AddSeconds(60)
do{$avatar=FindButton DEFAULT_NAME;if($avatar){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $until)
if(-not $avatar){throw 'Owned browser profile switcher unavailable'}
$browser=Get-Process -Id $browserPid
[FixtureProfileInput]::SetForegroundWindow($browser.MainWindowHandle)|Out-Null
Press $avatar
do{$other=FindButton OTHER_NAME;if($other){break};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $until)
if(-not $other){throw 'Owned second profile missing from browser switcher'}
Press $other
'''
        script = script.replace('BROWSER_PID', str(browser.pid)).replace('DEFAULT_NAME', quote(profile_names['Default'])).replace('OTHER_NAME', quote(profile_names['Profile 1']))
        result = subprocess.run(['pwsh.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(script.encode('utf-16-le')).decode()], capture_output=True, text=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise RuntimeError(result.stderr[-2000:])

    def ui(action, name='', checked=True):
        # UIA operates only the exact staged operator process. No private
        # WebView debugging or direct arming hook is used for this phase.
        script = r'''
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
$deadline=[DateTime]::UtcNow.AddSeconds(30)
do {
 $process=Get-Process -Id APP_PID
 $process.Refresh()
 if($process.MainWindowHandle -ne [IntPtr]::Zero){
  $window=[Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
  if(ACTION -eq 'close'){$window.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close();exit}
  $all=$window.FindAll([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.Condition]::TrueCondition)
  foreach($item in $all){
   if($item.Current.Name -notmatch NAME){continue}
   if(ACTION -eq 'check' -and $item.Current.ControlType -eq [Windows.Automation.ControlType]::CheckBox){
    $toggle=$item.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
    if(($toggle.Current.ToggleState -eq 'On') -ne CHECKED){$toggle.Toggle()}
    exit
   }
   if(ACTION -eq 'press' -and $item.Current.ControlType -eq [Windows.Automation.ControlType]::Button -and $item.Current.IsEnabled){
    $item.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke();exit
   }
  }
  if(ACTION -eq 'clear_unavailable'){
   foreach($item in $all){
    if($item.Current.Name -like 'Unavailable profile*' -and $item.Current.ControlType -eq [Windows.Automation.ControlType]::CheckBox){
     $toggle=$item.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern)
     if($toggle.Current.ToggleState -eq 'On'){$toggle.Toggle();break}
    }
   }
   if(-not ($all | Where-Object {$_.Current.Name -like 'Unavailable profile*' -and $_.Current.ControlType -eq [Windows.Automation.ControlType]::CheckBox})){exit}
  }
 }
 Start-Sleep -Milliseconds 100
}while([DateTime]::UtcNow -lt $deadline)
throw 'Staged operator UI element unavailable'
'''
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        script = script.replace('APP_PID', str(app.pid)).replace('ACTION', quote(action)).replace('NAME', quote(name)).replace('CHECKED', '$true' if checked else '$false')
        result = subprocess.run(['pwsh.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', base64.b64encode(script.encode('utf-16-le')).decode()], capture_output=True, text=True, timeout=45)
        if result.returncode: raise RuntimeError(result.stderr[-2000:])

    def start_app():
        nonlocal app
        app = subprocess.Popen([str(args.install/'machine-control.exe'), '--settings', '--presentation', 'minimal'], stdout=logs, stderr=logs)
        processes.append(app)

    def stop_app():
        if app and app.poll() is None:
            subprocess.run(['taskkill.exe', '/PID', str(app.pid), '/T', '/F'], stdout=logs, stderr=logs)
            app.wait(timeout=15)

    try:
        manifest = scratch / 'native-host.json'
        manifest.write_text(json.dumps(dict(name='org.machine_control.browser', description='Claimed profile fixture',
            path=str(exe), type='stdio', allowed_origins=['chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/'])), encoding='utf-8')
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
        start_runtime()
        check(direct('browser.tabs')['errorCode'] == 'approval_required', 'Fresh packaged runtime starts without browser authority')
        # Set only extension-local availability, through a test-browser worker.
        # The production native operator remains the sole approval authority.
        for directory, name in ([] if reused and not args.configure_profiles else [('Default', 'Work'), ('Profile 1', 'Personal')]):
            print('Configuring extension-local profile: '+name, flush=True)
            marker = uuid.uuid4().hex
            settings_url = base+'/bootstrap-'+marker
            # Create each real profile independently before opening both in a
            # headed browser. Chrome's singleton does not create an unknown
            # second regular profile from a forwarded launch command.
            browser = launch(directory, settings_url, headless=True)
            debug = browser_socket()
            debug.close()
            def settings_target():
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{debug_port}/json/list', timeout=15) as response:
                        return next((value for value in json.load(response) if marker in value.get('url', '')), None)
                except (OSError, ValueError):
                    return None
            target = poll(settings_target, seconds=180)
            panel = CdpSocket(target['webSocketDebuggerUrl'], timeout=60)
            panel.call('Page.enable')
            panel.call('Page.navigate', {'url': 'chrome://extensions/'})
            poll(lambda: panel.call('Runtime.evaluate', {'expression': "typeof chrome.developerPrivate?.updateProfileConfiguration === 'function'", 'returnByValue': True}).get('result', {}).get('result', {}).get('value') is True)
            configured = panel.call('Runtime.evaluate', {'expression': 'new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))', 'awaitPromise': True})
            assert 'exceptionDetails' not in configured.get('result', {}), 'Owned test profile developer setup'
            panel.call('Page.navigate', {'url': 'chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/panel.html'})
            try:
                def panel_ready():
                    value = panel.call('Runtime.evaluate', {'expression': "!!document.querySelector('#profile-card') && !document.querySelector('#profile-card').hidden", 'returnByValue': True})
                    return value.get('result', {}).get('result', {}).get('value') is True
                try: poll(panel_ready)
                except TimeoutError:
                    diagnostic = panel.call('Runtime.evaluate', {'expression': "document.querySelector('#setup-reason')?.textContent", 'returnByValue': True})
                    raise RuntimeError('Extension profile panel unavailable: '+json.dumps(diagnostic))
                result = panel.call('Runtime.evaluate', {'expression': "document.querySelector('#profile-name').value="+json.dumps(name)+";document.querySelector('#profile-enabled').checked=true;document.querySelector('#profile-enabled').dispatchEvent(new Event('change'));", 'returnByValue': True})
                assert 'exceptionDetails' not in result.get('result', {}), json.dumps(result)
                print('Waiting for resident metadata: '+name, flush=True)
                poll(lambda: any(p['name'] == name and p['enabled'] for p in profiles()))
                print('Checking absence of browser consent: '+name, flush=True)
                check(direct('browser.tabs')['errorCode'] == 'approval_required', name+' extension availability alone cannot grant browser control')
            finally:
                panel.close()
            stop_browser()
        # Read only fixture display names while Chrome is stopped; Windows can
        # exclusively replace Local State during startup.
        cache = json.loads((scratch/'chrome/Local State').read_text(encoding='utf-8'))['profile']['info_cache']
        profile_names = {directory: cache[directory]['name'] for directory in ['Default', 'Profile 1']}
        browser = launch('Default', base+'/work')
        browser_socket()
        open_second_profile()
        print('Checking both regular profiles in one headed browser', flush=True)
        connected = poll(lambda: [p for p in profiles() if p['connected']] if len([p for p in profiles() if p['connected']]) == 2 else None, seconds=args.browser_startup_seconds)
        ids = {p['name']: p['profileId'] for p in connected}
        check(set(ids) == {'Work', 'Personal'}, 'Both configured profile names retain distinct installation identities')
        before = [p['profileId'] for p in connected]
        time.sleep(5)
        check([p['profileId'] for p in profiles() if p['connected']] == before,
              'Two profile identities remain connected through one registration')
        # The real switcher opens a regular-profile window in our exact live
        # browser process, rather than starting another automation browser.
        check(browser.poll() is None, 'Both profiles belong to one test browser process')
        arm(list(ids.values())); new_owner()
        generations = {name: accepted('browser.tabs', name)['providerGeneration'] for name in ids}
        time.sleep(5)
        check({name: accepted('browser.tabs', name)['providerGeneration'] for name in ids} == generations, 'Both live provider generations remain stable without reconnect churn')
        check(call('browser.tabs')['errorCode'] == 'browser_profile_required', 'Multiple approved profiles require an explicit selector')
        tabs = {}
        for name, slug in [('Work', 'work'), ('Personal', 'personal')]:
            tab = accepted('browser.navigate', name, url=base+'/'+slug, newTab=True)['tab']['tabId']; tabs[name] = tab
            accepted('browser.wait', name, tabId=tab)
            elements = snapshot(name, tab)
            accepted('browser.click', name, reference=ref(elements, 'Increment fixture'))
            effect(slug, 'click', b'true')
            accepted('browser.type', name, reference=ref(elements, 'Message'), text='value-'+slug)
            accepted('browser.key', name, tabId=tab, key='Enter')
            effect(slug, 'message', ('value-'+slug).encode())
            capture = accepted('browser.capture', name, tabId=tab)
            status = direct('status')['data']; path = Path(status['artifactRoot']) / (capture['artifactId']+'.png')
            check(hashlib.sha256(path.read_bytes()).hexdigest() == capture['sha256'], name+' capture has independently verified artifact bytes')
            path.unlink()
            check(accepted('browser.eval', name, tabId=tab, expression='document.title')['value'] == 'Profile fixture', name+' raw evaluation reaches its page')
            accepted('browser.cdp', name, tabId=tab, method='Runtime.enable', params={})
            upload = Path(os.environ['PUBLIC']) / ('profile-upload-'+uuid.uuid4().hex+'.txt')
            try:
                upload.write_bytes(('upload-'+slug).encode())
                accepted('browser.upload', name, reference=ref(snapshot(name, tab), 'Upload fixture'), files=[str(upload)])
                effect(slug, 'upload', upload.read_bytes())
            finally: upload.unlink(missing_ok=True)
            accepted('browser.dialog', name, tabId=tab, action='status')
            opened = call('browser.click', name, reference=ref(snapshot(name, tab), 'Open dialog'))
            # Opening a real modal can interrupt the click's CDP completion.
            # Observe its exact dialog instead of replaying an uncertain action.
            assert opened['accepted'] or (opened.get('errorCode') == 'dialog_open' and opened['delivery'] == 'unknown'), opened
            dialog = accepted('browser.dialog', name, tabId=tab, action='status')
            check(dialog['state'] == 'open' and dialog['dialog']['message'] == 'Fixture dialog', name+' modal opening is independently observed without click replay')
            accepted('browser.dialog', name, tabId=tab, action='accept', dialogId=dialog['dialog']['id'])
            poll(lambda: accepted('browser.dialog', name, tabId=tab, action='status')['state'] != 'open')
            accepted('browser.release', name)
            check(True, name+' ordinary input, upload and dialog effects are independent')
        reference = ref(snapshot('Work', tabs['Work']), 'Increment fixture')
        check(call('browser.click', 'Personal', reference=reference)['errorCode'] == 'stale_reference', 'References cannot cross profiles')
        endpoints, streams = {}, {}
        for name, slug in [('Work','work'), ('Personal','personal')]:
            endpoints[name] = accepted('browser.endpoint', name)
            stream = CdpSocket(endpoints[name]['devtoolsEndpoint'].replace('<tabId>', str(tabs[name]))); sockets.append(stream); streams[name] = stream
            response = stream.call('Runtime.evaluate', {'expression': "fetch('/effect/"+slug+"/stream',{method:'POST',body:'stream-'+document.title})", 'awaitPromise':True})
            check('result' in response and 'error' not in response, name+' per-page stream dispatch completes')
            effect(slug, 'stream', b'stream-Profile fixture')
            root = CdpSocket(endpoints[name]['browserEndpoint']); sockets.append(root)
            targets = root.call('Target.getTargets')['result']['targetInfos']
            check(any(t['url'] == base+'/'+slug for t in targets) and not any(t['url'] == base+'/'+('personal' if slug=='work' else 'work') for t in targets), name+' root discovery stays within selected profile')
            created = root.call('Target.createTarget', {'url': base+'/'+slug})['result']['targetId']
            attached = root.call('Target.attachToTarget', {'targetId': created, 'flatten': True})['result']['sessionId']
            response = root.call('Runtime.evaluate', {'expression': "fetch('/effect/"+slug+"/flattened',{method:'POST',body:'flattened'})", 'awaitPromise': True}, session_id=attached)
            check('result' in response and 'error' not in response, name+' flattened root session completes')
            effect(slug, 'flattened', b'flattened')
            root.call('Target.detachFromTarget', {'sessionId': attached})
            root.call('Target.closeTarget', {'targetId': created})
            root.close()
        owner.close(); owner = None
        for stream in streams.values():
            try: stream.read(); raise AssertionError('Owner loss left stream alive')
            except (ConnectionError, OSError): pass
            stream.close()
        check(True, 'Native owner disconnect closes both shared CDP streams')
        operator('stop')
        check(direct('browser.tabs')['errorCode'] == 'approval_required', 'Stop revokes all profile authority')
        arm([ids['Work']]); new_owner()
        check(accepted('browser.tabs')['browserProfileId'] == ids['Work'], 'Single exact approval permits omitted selector')
        check(not call('browser.click', 'Work', reference=reference)['accepted'], 'Fresh consent cannot revive an old reference')
        owner.close(); owner = None
        operator('stop'); arm(list(ids.values()), 60); new_owner()
        poll(lambda: not any(scope in ('browser', 'devtools') for scope in operator('state')['state']['deployment']['effectiveScopes']), seconds=70)
        check(True, 'Live 60-second consent expires without a Settings client')
        owner.close(); owner = None
        arm(list(ids.values())); new_owner()
        before_disconnect = ref(snapshot('Work', tabs['Work']), 'Increment fixture')
        stop_browser()
        check(call('browser.tabs', ids['Work'])['errorCode'] == 'profile_unavailable', 'Offline selection refuses without fallback')
        browser = launch('Default', base+'/work'); browser_socket(); open_second_profile()
        poll(lambda: len([p for p in profiles() if p['connected']]) == 2, seconds=args.browser_startup_seconds)
        check(not call('browser.click', 'Work', reference=before_disconnect)['accepted'], 'Reconnect invalidates old provider references')
        owner.close(); owner = None
        # Kill the exact owned policy child while a native owner exists.
        new_owner()
        endpoint = accepted('browser.endpoint', 'Work')
        stream = CdpSocket(endpoint['browserEndpoint']); sockets.append(stream)
        stream.call('Browser.getVersion')
        command = "Get-CimInstance Win32_Process -Filter 'ParentProcessId="+str(runtime.pid)+"' | Where-Object Name -eq 'node.exe' | Select-Object -ExpandProperty ProcessId"
        node_ids = subprocess.check_output(['pwsh.exe', '-NoProfile', '-Command', command], text=True).split()
        check(len(node_ids) == 1, 'Packaged native resident owns exactly one private policy child')
        subprocess.run(['taskkill.exe', '/PID', node_ids[0], '/T', '/F'], stdout=logs, stderr=logs, check=True)
        try: stream.read(); raise AssertionError('Policy death retained stream')
        except (ConnectionError, OSError): pass
        owner.close(); owner = None
        poll(lambda: not operator('state')['state']['browser']['available'])
        check(not direct('browser.tabs')['accepted'], 'Policy death revokes native browser access and closes streams')
        operator('quit'); runtime.wait(timeout=15)
        start_runtime()
        check(direct('browser.tabs')['errorCode'] == 'approval_required', 'Restart has no consent or request replay')
        if args.settings:
            operator('quit'); runtime.wait(timeout=15); runtime = None
            start_app()
            poll(lambda: len([p for p in direct('capabilities')['data']['browser']['profiles'] if p['connected']]) == 2)
            check(direct('browser.tabs')['errorCode'] == 'approval_required', 'Staged Tauri operator starts with browser access off')
            ui('press', '^Access$')
            for label, enabled in [('View desktop', False), ('Control apps and input', False), ('Browser tabs', True), ('Browser scripts and DevTools', True)]:
                ui('check', '^'+label+'$', enabled)
            ui('clear_unavailable')
            ui('check', '^Work ·')
            ui('check', '^Personal ·')
            ui('press', '^Enable access$')
            new_owner()
            tab = accepted('browser.navigate', 'Work', url=base+'/work', newTab=True)['tab']['tabId']
            ui('close')
            # Destroying Settings must not destroy or replace the resident or
            # transfer policy ownership into a WebView.
            count = received.count(('/effect/work/click', b'true'))
            accepted('browser.click', 'Work', reference=ref(snapshot('Work', tab), 'Increment fixture'))
            poll(lambda: received.count(('/effect/work/click', b'true')) > count)
            check(app.poll() is None, 'Closing the real Settings window leaves resident browser effects working')
            subprocess.run([str(args.install/'machine-control.exe'), '--settings'], stdout=logs, stderr=logs, timeout=30)
            ui('press', '^Access$')
            ui('press', '^Stop access$')
            check(not call('browser.tabs', 'Work')['accepted'], 'Recreated Settings stops the existing resident authority')
            owner.close(); owner = None
            stop_app(); start_app()
            check(direct('browser.tabs')['errorCode'] == 'approval_required', 'Tauri restart retains choices without restoring browser consent')
            ui('press', '^Access$')
            ui('press', '^Enable access$')
            new_owner()
            check(accepted('browser.tabs', 'Personal')['browserProfileId'] == ids['Personal'], 'Recreated Settings retains exact profile choices for fresh approval')
            owner.close(); owner = None
            ui('press', '^Stop access$')
            stop_app()
        report['passed'] = True
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        report['errorCode'] = getattr(error, 'code', None)
        if runtime:
            report['nativeExited'] = runtime.poll()
            try:
                state = operator('state')['state']
                report['nativeAtFailure'] = state['browser']
                report['nativeAdmissionAtFailure'] = state['admission']
                report['nativeActivityAtFailure'] = state['physicalAvailability']
            except Exception as diagnostic_error: report['nativeDiagnosticError'] = type(diagnostic_error).__name__
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, access) as key:
                report['registrationStillOwned'] = winreg.QueryValueEx(key, '')[0] == str(manifest)
        except OSError: report['registrationStillOwned'] = False
        report['scratchDirectory'] = str(scratch)
        for directory in ['Default', 'Profile 1']:
            for name in ['Preferences', 'Secure Preferences']:
                try:
                    value = json.loads((scratch/'chrome'/directory/name).read_text(encoding='utf-8'))
                    extension_state = value.get('extensions', {})
                    report.setdefault('fixturePreferences', {})[directory+'/'+name] = {
                        'developerMode': extension_state.get('ui', {}).get('developer_mode'),
                        'extension': {key: item.get('location') for key, item in extension_state.get('settings', {}).items() if key == 'ncbfifkjllmnkkjmomjohinigfgdocjc'},
                    }
                except (OSError, ValueError): pass
        raise
    finally:
        if owner: owner.close()
        for sock in sockets:
            try: sock.close()
            except OSError: pass
        stop_app()
        if browser and browser.poll() is None:
            subprocess.run(['taskkill.exe', '/PID', str(browser.pid), '/T', '/F'], stdout=logs, stderr=logs)
        if runtime and runtime.poll() is None:
            try: operator('quit'); runtime.wait(timeout=10)
            except Exception: runtime.kill(); runtime.wait(timeout=10)
        for process in processes:
            if process.poll() is None:
                process.kill(); process.wait(timeout=10)
        if old_registry:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY) as key:
                winreg.SetValueEx(key, '', 0, old_registry[1], old_registry[0])
        else:
            try: winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key_path, winreg.KEY_WOW64_32KEY)
            except FileNotFoundError: pass
        backup.unlink()
        faulthandler.cancel_dump_traceback_later()
        server.shutdown(); server.server_close(); logs.close()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not (args.keep_profile_data_on_failure and not report['passed']):
                try: shutil.rmtree(scratch); break
                except OSError: time.sleep(.2)
            report['cleanup'] = not scratch.exists()
        finally:
            (args.output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__': main()

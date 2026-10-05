"""Interactive Windows desktop streaming CDP acceptance with an independent HTTP oracle.

The outside caller owns the exact VM claim, staging and power cleanup. This
actor operates the real local approval UI and a separately identified test
browser. Concrete locators and evidence belong in private caller directories.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import winreg

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'desktop', '--session-id', sys.argv[3]]))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
from control_session import ControlSession
from machine_control import ClientError
from cdp_socket import CdpSocket

PAGE = b'''<!doctype html><meta charset="utf-8"><title>Streaming CDP Fixture</title>
<p>Independent effect fixture</p><button id="effect" onclick="fetch('/effect',
{method:'POST',body:this.dataset.marker}).then(r=>r.text()).then(()=>this.dataset.done='yes')">Effect</button>'''



def quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def ps(script):
    script = '[Console]::OutputEncoding=[Text.UTF8Encoding]::new();' + script
    encoded = base64.b64encode(script.encode('utf-16-le')).decode()
    value = subprocess.run(['pwsh.exe', '-NoProfile', '-EncodedCommand', encoded],
                           capture_output=True, text=True, encoding='utf-8', timeout=40)
    if value.returncode:
        raise RuntimeError(value.stderr)
    return value.stdout.strip().lstrip('\ufeff')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', required=True, type=Path)
    parser.add_argument('--chrome', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--node', type=Path)
    parser.add_argument('--client-modules', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    session_id = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    report = {'schema': 'machine-control-browser-cdp-live/v0', 'passed': False,
              'checks': [], 'routes': [], 'runtimeSha256': hashlib.sha256(exe.read_bytes()).hexdigest()}
    app = browser = owner = None
    received = []
    received_lock = threading.Lock()
    key_path = r'Software\Google\Chrome\NativeMessagingHosts\org.machine_control.browser'
    manifest = Path(os.environ['LOCALAPPDATA']) / 'MachineControl/packages/desktop/browser-host.json'
    old_manifest = manifest.read_bytes() if manifest.exists() else None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
            old_registry = winreg.QueryValueEx(key, '')[0]
    except FileNotFoundError:
        old_registry = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *values):
            pass

        def do_GET(self):
            page = b'<title>Child</title><p id="frame">Cross-site child</p>' if self.path == '/frame' else PAGE
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if self.path != '/effect' or not 1 <= size <= 128:
                self.send_error(400)
                return
            body = self.rfile.read(size).decode('ascii')
            with received_lock:
                received.append(body)
            self.send_response(200)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'OK')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        report['checks'].append(label)
        (args.output/'progress.json').write_text(json.dumps({'checks': report['checks']}), encoding='utf-8')
        print(label, flush=True)

    def direct(request):
        value = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance',
                                'desktop', '--session-id', session_id], input=json.dumps(request),
                               text=True, capture_output=True, timeout=45)
        return json.loads(value.stdout)

    def ui(name, checked=None):
        # Exact process, visible element and native UIA patterns; no agent API
        # can enable grants or read this test actor's operator authority.
        kind = 'Button' if checked is None else 'CheckBox'
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes; '
        script += '$deadline=[DateTime]::UtcNow.AddSeconds(15); do {'
        script += '$root=[Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,'+str(app.pid)+'));'
        script += 'if($root){$item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'+quote(name)+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::'+kind+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false)));if($item){break}};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline); if(!$item){throw '+quote('UI unavailable: '+name)+'};'
        if checked is None:
            script += '$item.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()'
        else:
            script += '$toggle=$item.GetCurrentPattern([Windows.Automation.TogglePattern]::Pattern); if($toggle.Current.ToggleState -ne [Windows.Automation.ToggleState]::'+('On' if checked else 'Off')+'){$toggle.Toggle()}'
        ps(script)
        time.sleep(.3)

    def poll(observe, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = observe()
            if value:
                return value
            time.sleep(.2)
        raise TimeoutError('Read-only observation did not settle')

    def new_owner(scopes=("browser", "devtools")):
        value = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()),
                                '--channel', str(exe), session_id]},
                               reason='Streaming CDP acceptance', scopes=scopes, wait=60, duration=300)
        value.wait()
        return value

    def accepted(request):
        value = owner.call(request)
        if not value['accepted']:
            raise AssertionError(json.dumps(value))
        if value['actualRoute'] not in report['routes']:
            report['routes'].append(value['actualRoute'])
        return value

    sockets = []

    def endpoint():
        return accepted({'operation': 'browser.endpoint'})['data']['devtoolsEndpoint'].replace('<tabId>', str(tab))

    def connect(url):
        # Socket closure precedes the bounded native detach cleanup. Retry
        # only connection establishment; no CDP commands are replayed.
        deadline = time.monotonic() + 5
        while True:
            try:
                value = CdpSocket(url)
                sockets.append(value)
                return value
            except ConnectionError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.05)

    def refused(url, origin=None):
        try:
            value = CdpSocket(url, origin)
        except ConnectionError:
            return True
        value.close()
        raise AssertionError('Forbidden WebSocket connected')

    def closed(value):
        # Any buffered event may precede shutdown; a live quiet socket times
        # out and fails this check rather than being mistaken for closure.
        try:
            while True:
                value.read()
        except ConnectionError:
            return True

    def evaluate(value, expression):
        response = value.call('Runtime.evaluate', {'expression': expression,
                              'awaitPromise': True, 'returnByValue': True})
        if 'error' in response or 'exceptionDetails' in response.get('result', {}):
            raise AssertionError('CDP evaluation failed')
        return response['result']['result'].get('value')

    def effect(value, marker):
        result = evaluate(value, "fetch('/effect',{method:'POST',body:" + json.dumps(marker) + "}).then(r=>r.text())")
        check(result == 'OK', 'CDP awaitPromise reply received')
        check(received[-1:] == [marker], 'Independent HTTP server observed exact command effect: '+marker)

    try:
        check('Chrome for Testing' in ps('(Get-Item '+quote(args.chrome)+').VersionInfo.ProductName') or
              'Chromium' in ps('(Get-Item '+quote(args.chrome)+').VersionInfo.ProductName'), 'Separately identified test browser')
        check(ps('@(Get-Process machine-control -ErrorAction SilentlyContinue).Count') == '0', 'No existing desktop operator disturbed')
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        app = subprocess.Popen([str(args.install/'machine-control.exe'), '--gui'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        poll(lambda: direct({'operation': 'status'}).get('data', {}).get('ready'))
        check(direct({'operation': 'browser.endpoint'}).get('errorCode') == 'approval_required', 'Endpoint off by default')
        ui('Permissions'); ui('Set up browser extension'); ui('Access')
        for name in ['View desktop', 'Control apps and input', 'Browser scripts and DevTools']:
            ui(name, False)
        ui('Browser tabs', True); ui('Enable access')
        check(direct({'operation': 'browser.endpoint'}).get('errorCode') == 'approval_required', 'Browser grant cannot mint DevTools endpoint')
        capabilities = direct({'operation': 'capabilities'})['data']
        check('browser.endpoint' in capabilities['operations'] and
              'raw CDP WebSocket' not in capabilities['browser']['knownOmissions'], 'Streaming endpoint advertised')
        # MV3 retains registered worker scripts across browser restarts.
        # Each candidate run needs a fresh profile to load its staged worker.
        profile = args.output / ('browser-profile-' + str(time.time_ns()))
        browser = subprocess.Popen([str(args.chrome), '--no-first-run', '--no-default-browser-check',
                                    '--user-data-dir='+str(profile),
                                    '--site-per-process', '--load-extension='+str(args.install/'runtime/browser-extension')],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner = new_owner(['browser'])
        poll(lambda: owner.call({'operation': 'browser.tabs'}).get('accepted'))
        try:
            owner.call({'operation': 'browser.endpoint'})
            raise AssertionError('Browser-only owner reached DevTools')
        except ClientError as error:
            check(error.code == 'operation_not_permitted_by_control_channel', 'Browser owner cannot borrow DevTools scope')
        owner.close(); owner = None
        ui('Stop access'); ui('Browser scripts and DevTools', True); ui('Enable access')
        check(direct({'operation': 'browser.endpoint'}).get('errorCode') == 'control_session_required', 'Standing DevTools grant requires a live owner')
        owner = new_owner()
        page = accepted({'operation': 'browser.navigate', 'newTab': True,
                         'url': 'http://127.0.0.1:'+str(server.server_port)+'/'})
        tab = page['data']['tab']['tabId']
        url = endpoint()
        check(refused(url[:-64]+'0'*64) and refused(url, 'https://fixture.invalid') and refused(url, ''), 'Wrong token and all Origin headers refused')
        stream = connect(url)
        check(evaluate(stream, 'document.title') == 'Streaming CDP Fixture', 'Raw CDP reads real page main world')
        check(refused(url), 'Second connection to same tab refused')
        stream.call('Runtime.enable')
        evaluate(stream, "console.log('streaming-fixture-event')")
        event = stream.event('Runtime.consoleAPICalled')
        check(event['params']['args'][0]['value'] == 'streaming-fixture-event', 'Real debugger console event streams over WebSocket')
        stream.send(json.dumps({'id': 201, 'method': 'Runtime.evaluate', 'params': {'expression': '1+2', 'returnByValue': True}}))
        stream.send(json.dumps({'id': 202, 'method': 'Runtime.evaluate', 'params': {'expression': '3+4', 'returnByValue': True}}))
        replies = {}
        while len(replies) < 2:
            reply = stream.read()
            if reply.get('id') in (201, 202):
                replies[reply['id']] = reply['result']['result']['value']
        check(replies == {201: 3, 202: 7}, 'Multiple outstanding commands retain CDP correlation')
        check('error' in stream.call('Fixture.invalidMethod'), 'Provider CDP error returned without effect replay')
        effect(stream, 'first')
        check(received == ['first'], 'One dispatched effect observed exactly once')
        stream.send(json.dumps({'id': 203, 'method': 'Runtime.evaluate',
                                'params': {'expression': 'new Promise(()=>{})', 'awaitPromise': True}}))
        check(evaluate(stream, '6+8') == 14, 'Pending awaitPromise does not block another CDP command')
        ui('Pause access')
        check(closed(stream) and refused(url) and received == ['first'], 'Pause closes stream and fences old endpoint')
        owner.close(); owner = None
        ui('Resume access'); owner = new_owner()
        resumed = endpoint()
        check(resumed != url and refused(url), 'Resume requires new owner and rotates token')
        stream = connect(resumed)
        effect(stream, 'resumed')
        owner.close(); owner = None
        check(closed(stream) and refused(resumed) and received == ['first', 'resumed'], 'Owner disconnect closes socket without another effect')
        owner = new_owner(); current = endpoint()
        stream = connect(current)
        # Kill only the candidate's Chrome-started native host, never the
        # operator resident, to exercise actual provider-generation loss.
        count = ps('$owned=@(Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq '+quote(exe)+' -and $_.CommandLine -like '+quote('*chrome-extension://*')+'}); if($owned.Count -ne 1){throw "Native host identity uncertain"}; $owned | ForEach-Object {Stop-Process -Id $_.ProcessId}; $owned.Count')
        check(count == '1' and closed(stream) and refused(current), 'Native messaging disconnect closes stream and revokes token')
        poll(lambda: owner.call({'operation': 'browser.tabs'}).get('accepted'), timeout=60)
        replacement = endpoint()
        check(replacement != current and refused(current), 'Reconnected provider requires a new endpoint')
        stream = connect(replacement)
        effect(stream, 'reconnected')
        stream.send('{"id":1,"method":"Runtime.evaluate","sessionId":{}}')
        check(closed(stream) and received == ['first', 'resumed', 'reconnected'], 'Malformed command closes only its connection before dispatch')
        stream = connect(replacement)
        ui('Stop access')
        check(closed(stream) and refused(replacement) and received == ['first', 'resumed', 'reconnected'], 'Stop closes stream and prevents further effects')
        if args.node and args.client_modules:
            owner.close(); owner = None
            ui('Enable access'); owner = new_owner()
            data = accepted({'operation': 'browser.endpoint'})['data']
            root_url = data['browserEndpoint']
            check(refused(root_url[:-64]+'0'*64) and refused(root_url, ''), 'Browser endpoint preserves token and Origin gates')
            stream = connect(root_url)
            check(refused(root_url) and refused(data['devtoolsEndpoint'].replace('<tabId>', str(tab))), 'Browser root owns exclusive debugger attachment')
            check(stream.call('Browser.close')['error']['code'] == -32601 and
                  stream.call('Browser.setDownloadBehavior')['error']['code'] == -32601, 'Browser shutdown and download policy refuse explicitly')
            check(stream.call('Runtime.enable', session_id='forged')['error']['code'] == -32000, 'Forged child session cannot reach debugger')
            stream.close(); time.sleep(.3)
            fixture_url = 'http://127.0.0.1:'+str(server.server_port)+'/'
            value = subprocess.run([str(args.node), str(Path(__file__).with_name('browser-root-clients.mjs')),
                                    str(args.client_modules)], input=json.dumps({'endpoint': root_url, 'fixtureUrl': fixture_url}),
                                   capture_output=True, text=True, encoding='utf-8', timeout=150)
            result = json.loads(value.stdout)
            report['clients'] = result
            for label in result['checks']:
                check(True, label)
            check(value.returncode == 0 and result['passed'], 'Real browser clients complete: '+result.get('error', 'passed'))
            check(received == ['first', 'resumed', 'reconnected', 'playwright', 'puppeteer'], 'Independent HTTP server observes both client clicks exactly once')
            stream = connect(root_url)
            stream.call('Target.setAutoAttach', {'autoAttach': True, 'flatten': True, 'waitForDebuggerOnStart': False})
            stream.call('Target.setDiscoverTargets', {'discover': True})
            ui('Pause access')
            check(closed(stream) and refused(root_url), 'Pause closes browser and all attached sessions')
            owner.close(); owner = None
            ui('Resume access'); owner = new_owner()
            fresh = accepted({'operation': 'browser.endpoint'})['data']['browserEndpoint']
            check(fresh != root_url and refused(root_url), 'Browser endpoint rotates after Resume')
            stream = connect(fresh)
            owner.close(); owner = None
            check(closed(stream) and refused(fresh), 'Browser owner disconnect closes root connection')
            owner = new_owner()
            fresh = accepted({'operation': 'browser.endpoint'})['data']['browserEndpoint']
            stream = connect(fresh)
            count = ps('$owned=@(Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq '+quote(exe)+' -and $_.CommandLine -like '+quote('*chrome-extension://*')+'}); if($owned.Count -ne 1){throw "Native host identity uncertain"}; $owned | ForEach-Object {Stop-Process -Id $_.ProcessId}; $owned.Count')
            check(count == '1' and closed(stream) and refused(fresh), 'Provider loss closes browser root and fences its endpoint')
            poll(lambda: owner.call({'operation': 'browser.tabs'}).get('accepted'), timeout=60)
            recovered = accepted({'operation': 'browser.endpoint'})['data']['browserEndpoint']
            check(recovered != fresh and refused(fresh), 'Browser provider reconnect requires a fresh endpoint')
            stream = connect(recovered); ui('Stop access')
            check(closed(stream) and refused(recovered), 'Stop closes browser connection')
        report['passed'] = True

    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        for value in sockets:
            value.close()
        if owner:
            owner.close()
        if app and app.poll() is None:
            try:
                ui('Access'); ui('Stop access')
            except Exception:
                pass
            app.terminate(); app.wait(timeout=15)
        if browser:
            # Chrome's launcher may exit before its actual profile-owning
            # process; identify only the dedicated executable/profile pair.
            ps('Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq '+quote(args.chrome)+' -and $_.CommandLine -like '+quote('*'+str(profile)+'*')+'} | ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue}')
            try:
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                browser.kill(); browser.wait(timeout=10)
        if old_registry is None:
            try:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key_path, winreg.KEY_WOW64_32KEY)
            except FileNotFoundError:
                pass
        else:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0,
                                    winreg.KEY_WRITE | winreg.KEY_WOW64_32KEY) as key:
                winreg.SetValueEx(key, '', 0, winreg.REG_SZ, old_registry)
        if old_manifest is None:
            manifest.unlink(missing_ok=True)
        else:
            manifest.write_bytes(old_manifest)
        server.shutdown(); server.server_close(); server_thread.join(timeout=5)
        report['received'] = received
        report['cleanup'] = {'appExited': app is None or app.poll() is not None,
                             'browserLauncherExited': browser is None or browser.poll() is not None,
                             'serverStopped': not server_thread.is_alive(),
                             'registrationRestored': True}
        (args.output/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

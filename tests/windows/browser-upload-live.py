"""Interactive Windows desktop upload acceptance with an HTTP byte oracle.

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
from urllib.parse import parse_qs, urlsplit
import winreg

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'desktop', '--session-id', sys.argv[3]]))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
from control_session import ControlSession
from machine_control import ClientError, browser_request

PAGE = b'''<!doctype html><meta charset="utf-8"><title>Browser Upload Fixture</title>
<input type="file" multiple aria-label="Direct file upload" onchange="upload(this,'direct')">
<input id="single" type="file" hidden onchange="upload(this,'chooser')">
<button onclick="document.querySelector('#single').click()">Choose upload file</button>
<button>No file chooser</button><output id="result"></output>
<script>async function upload(input,slot){for(const f of input.files){const r=await fetch('/upload?slot='+slot+'&name='+encodeURIComponent(f.name),{method:'POST',body:await f.arrayBuffer()});document.querySelector('#result').textContent=await r.text()}}</script>'''


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
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    session_id = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    report = {'schema': 'machine-control-browser-upload-live/v0', 'passed': False,
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
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(PAGE)))
            self.end_headers()
            self.wfile.write(PAGE)

        def do_POST(self):
            query = parse_qs(urlsplit(self.path).query)
            size = int(self.headers.get('Content-Length', '0'))
            if urlsplit(self.path).path != '/upload' or not 1 <= size <= 1048576:
                self.send_error(400)
                return
            body = self.rfile.read(size)
            with received_lock:
                received.append({'slot': query['slot'][0], 'name': query['name'][0],
                                 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
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

    def new_owner():
        value = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()),
                                '--channel', str(exe), session_id]},
                               reason='Browser file upload acceptance', scopes=['browser'], wait=60, duration=300)
        value.wait()
        return value

    def accepted(request):
        value = owner.call(request)
        if not value['accepted']:
            raise AssertionError(json.dumps(value))
        if value['actualRoute'] not in report['routes']:
            report['routes'].append(value['actualRoute'])
        return value

    def refs():
        snap = accepted({'operation': 'browser.snapshot', 'tabId': tab, 'interactiveOnly': False})
        report['lastSnapshot'] = snap
        elements = snap['data']['elements']
        names = ['Direct file upload', 'Choose upload file', 'No file chooser']
        if not all(any(e.get('name') == name for e in elements) for name in names):
            return None
        return {name: next(e['reference'] for e in elements if e.get('name') == name) for name in names}

    def uploads(expected):
        def observe():
            with received_lock:
                return list(received) if len(received) >= len(expected) else None
        actual = poll(observe)
        check(actual == expected, 'HTTP server received exact file names, lengths and SHA-256 hashes')

    try:
        check('Chrome for Testing' in ps('(Get-Item '+quote(args.chrome)+').VersionInfo.ProductName') or
              'Chromium' in ps('(Get-Item '+quote(args.chrome)+').VersionInfo.ProductName'), 'Separately identified test browser')
        check(ps('@(Get-Process machine-control -ErrorAction SilentlyContinue).Count') == '0', 'No existing desktop operator disturbed')
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        app = subprocess.Popen([str(args.install/'machine-control.exe'), '--gui'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        poll(lambda: direct({'operation': 'status'}).get('data', {}).get('ready'))
        check(direct({'operation': 'browser.upload', 'files': []}).get('errorCode') == 'approval_required', 'Off-state upload refusal')
        ui('Permissions'); ui('Set up browser extension'); ui('Access')
        for name in ['View desktop', 'Control apps and input', 'Browser scripts and DevTools']:
            ui(name, False)
        ui('Browser tabs', True); ui('Enable access')
        check(direct({'operation': 'browser.upload', 'files': []}).get('errorCode') == 'control_session_required', 'Standing browser grant cannot bypass owner')
        check('browser.upload' in direct({'operation': 'capabilities'})['data']['operations'], 'Upload advertised in runtime capabilities')
        profile = args.output / 'browser-profile'
        browser = subprocess.Popen([str(args.chrome), '--no-first-run', '--no-default-browser-check',
                                    '--user-data-dir='+str(profile),
                                    '--load-extension='+str(args.install/'runtime/browser-extension')],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        owner = new_owner()
        poll(lambda: owner.call({'operation': 'browser.tabs'}).get('accepted'))
        page = accepted({'operation': 'browser.navigate', 'newTab': True,
                         'url': 'http://127.0.0.1:'+str(server.server_port)+'/'})
        tab = page['data']['tab']['tabId']
        references = poll(refs)
        fixture = args.output / 'files'
        fixture.mkdir(exist_ok=True)
        files = [fixture/'space resum\u00e9.txt', fixture/'second file.bin']
        contents = [b'First independent upload\x00\xff\n', bytes(range(256))]
        for file, body in zip(files, contents):
            file.write_bytes(body)
        request = {'operation': 'browser.upload', 'reference': references['Direct file upload']}
        for paths, code in [([], 'invalid_request'), ([str(fixture/'missing.txt')], 'upload_file_unavailable'),
                            ([str(fixture)], 'upload_file_unavailable'), ([str(files[0])+':stream'], 'invalid_request'),
                            ([r'\\invalid-server\share\file.txt'], 'invalid_request')]:
            refused = owner.call({**request, 'files': paths})
            check(not refused['accepted'] and refused['errorCode'] == code and not received,
                  'Refused invalid upload before any HTTP effect: '+code)
        hidden = fixture/'.private.txt'; hidden.write_text('not uploaded')
        denied = owner.call({**request, 'files': [str(files[0]), str(hidden)]})
        check(denied['errorCode'] == 'upload_path_not_permitted' and not received, 'Entire mixed batch refused before effect')
        try:
            owner.call({'operation': 'browser.eval', 'tabId': tab, 'expression': 'document.title'})
            raise AssertionError('Browser owner reached DevTools')
        except ClientError as error:
            check(error.code == 'operation_not_permitted_by_control_channel', 'Browser-only owner lacks DevTools')
        supplied = browser_request(['upload', '--reference', request['reference'], '--file', str(files[0]), '--file', str(files[1])], 'windows')
        result = accepted(supplied)
        check(result['data']['route'] == 'file_input' and result['data']['files'] == 2, 'CLI request uploads two files through direct CDP input')
        check(result['delivery'] == 'confirmed' and result['effect'] == 'unverifiable' and result['retrySafety'] == 'unsafe_to_replay', 'Attachment acknowledgement keeps application effect separate')
        expected = [{'slot': 'direct', 'name': f.name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
                    for f, b in zip(files, contents)]
        uploads(expected)
        references = poll(refs)
        stale = owner.call({**request, 'files': [str(files[0])]})
        check(stale['errorCode'] == 'stale_reference' and len(received) == 2, 'Superseded upload reference refused')
        result = accepted({'operation': 'browser.upload', 'reference': references['Choose upload file'], 'files': [str(files[0])]})
        check(result['data']['route'] == 'intercepted_file_chooser', 'Upload button intercepts stock chooser without OS dialog')
        expected.append({**expected[0], 'slot': 'chooser'})
        uploads(expected)
        # Repeating a different attempted selection is deliberate negative
        # coverage, never an automatic retry of an uncertain effect.
        references = poll(refs)
        refused = owner.call({'operation': 'browser.upload', 'reference': references['Choose upload file'], 'files': list(map(str, files))})
        check(refused['errorCode'] == 'file_chooser_single' and len(received) == 3, 'Single chooser refuses multiple files without upload')
        refused = owner.call({'operation': 'browser.upload', 'reference': references['No file chooser'], 'files': [str(files[0])]})
        check(refused['errorCode'] == 'file_chooser_not_opened' and len(received) == 3, 'Button without chooser returns bounded refusal and no upload')
        references = poll(refs)
        ui('Pause access')
        try:
            owner.call({'operation': 'browser.upload', 'reference': references['Direct file upload'], 'files': [str(files[0])]})
            raise AssertionError('Paused owner dispatched')
        except ClientError:
            check(len(received) == 3, 'Pause fences upload effects')
        owner.close(); owner = None
        ui('Resume access'); owner = new_owner()
        denied = owner.call({'operation': 'browser.upload', 'reference': references['Direct file upload'], 'files': [str(files[0])]})
        check(denied['errorCode'] == 'stale_reference', 'New owner cannot reuse old upload reference')
        ui('Stop access')
        check(direct({'operation': 'browser.upload', 'files': list(map(str, files))})['errorCode'] == 'approval_required' and len(received) == 3, 'Stop revokes uploads without another HTTP effect')
        report['passed'] = True
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
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
            ps('Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq '+quote(args.chrome)+' -and $_.CommandLine -like '+quote('*'+str(args.output/'browser-profile')+'*')+'} | ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue}')
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
        if report['passed']:
            report.pop('lastSnapshot', None)
        report['received'] = received
        report['cleanup'] = {'appExited': app is None or app.poll() is not None,
                             'browserLauncherExited': browser is None or browser.poll() is not None,
                             'serverStopped': not server_thread.is_alive(),
                             'registrationRestored': True}
        (args.output/'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

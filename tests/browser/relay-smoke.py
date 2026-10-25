#!/usr/bin/env python3
"""Short real-browser smoke for staged Windows/Linux desktop relays.

Run in a claimed dedicated VM's interactive session. The caller owns staging
and power cleanup. Uses an empty Chrome for Testing profile and restores its
temporary native-host registration. Does not exercise lock or protected input.
"""
import argparse
import concurrent.futures
import ctypes
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'desktop', '--session-id', sys.argv[3]]))

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--platform', choices=['windows', 'linux'], required=True)
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--chrome', type=Path, required=True)
p.add_argument('--cdp-client', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--no-sandbox', action='store_true', help='Explicit isolated Linux VM fixture only')
a = p.parse_args()
a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
profile = a.output / 'profile'
checks, received = [], []
child = chrome = server = root_cdp = owner = None
host_name = 'org.machine_control.browser'
key_path = 'Software\\Google\\Chrome\\NativeMessagingHosts\\' + host_name
old_key = None
key_existed = False
registered = False
log = (a.output / 'actor.log').open('w')
result = {'passed':False, 'checks':checks, 'platform':a.platform}
replies = queue.Queue()


def check(name, condition=True):
    assert condition, name
    checks.append(name)
    (a.output / 'progress.json').write_text(json.dumps({'checks':checks, 'updatedAt':time.time()}))
    print('PASS: ' + name, flush=True)


def poll(fn, label, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = fn()
        if value:
            return value
        time.sleep(.1)
    raise AssertionError('Timed out: ' + label)


def operator(method, **fields):
    child.stdin.write(json.dumps({'method':method, **fields}) + '\n')
    child.stdin.flush()
    reply = replies.get(timeout=30)
    assert reply is not None, 'Private operator disconnected'
    return reply


def raw(operation, **fields):
    if owner is not None and operation.startswith('browser.'):
        return owner.call({'operation':operation, **fields})
    request = json.dumps({'operation':operation, **fields}) + '\n'
    if a.platform == 'windows':
        value = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', 'desktop',
            '--session-id', str(session.value)], input=request, text=True,
            capture_output=True, timeout=35)
        if operation == 'status' and (value.returncode or not value.stdout.strip()):
            return {}
        return json.loads(value.stdout)
    with socket.socket(socket.AF_UNIX) as channel:
        channel.settimeout(35)
        channel.connect(endpoint)
        channel.sendall(request.encode())
        return json.loads(channel.makefile('rb').readline(24 * 1024 * 1024))


def call(operation, **fields):
    reply = raw(operation, **fields)
    assert reply.get('accepted'), operation + ': ' + str(reply.get('errorCode'))
    return reply['data']


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        body = b'''<!doctype html><meta charset="utf-8"><title>Relay smoke</title>
<button onclick="fetch('/effect',{method:'POST',body:'click'})">Increment</button>'''
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Content-Type', 'text/html;charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if self.path != '/effect' or not 0 < length <= 128:
            self.send_error(400)
            return
        received.append(self.rfile.read(length).decode())
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'ok')


try:
    if a.platform == 'linux':
        version = subprocess.check_output([str(a.chrome), '--version']).decode()
        assert 'Chrome for Testing' in version, 'Use a separately identified test browser'
        os.environ['XDG_DATA_HOME'] = str(a.output / 'data')
        os.environ['XDG_CONFIG_HOME'] = str(a.output / 'config')
        data = a.output / 'data/machine-control'
        data.mkdir(mode=0o700, parents=True)
        shutil.copyfile(a.runtime / 'browser_host.py', data / 'browser_host.py')
        (data / 'browser_host.py').chmod(0o700)
        host = str(data / 'browser_host.py')
        extension = a.runtime / 'extension'
        command = ['/usr/bin/python3', str(a.runtime / 'desktop.py')]
        assert not (Path(os.environ['XDG_RUNTIME_DIR']) / 'machine-control-desktop/desktop.sock').exists(), 'Existing desktop socket must be preserved'
    else:
        import winreg
        session = ctypes.c_uint()
        assert ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)) and session.value > 0
        version = subprocess.check_output(['powershell.exe', '-NoProfile', '-Command',
            '(Get-Item -LiteralPath ' + "'" + str(a.chrome).replace("'", "''") + "').VersionInfo.ProductName"]).decode()
        assert 'Chrome for Testing' in version, 'Use a separately identified test browser'
        exe = a.runtime / 'machine-control-windows.exe'
        host = str(exe)
        extension = a.runtime / 'browser-extension'
        command = [str(exe), 'desktop', '--presentation', 'minimal']
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
                key_existed = True
                try:
                    old_key = winreg.QueryValueEx(key, '')
                except FileNotFoundError:
                    pass
        except FileNotFoundError:
            pass
    (a.output / 'registration-before.json').write_text(json.dumps({
        'keyExisted':key_existed, 'defaultValue':old_key}))
    # Registration is fixture plumbing, confined to this empty browser profile
    # on Linux; Windows' per-user registry value is restored in finally.
    result['runtimeSha256'] = hashlib.sha256(Path(command[1] if a.platform == 'linux' else exe).read_bytes()).hexdigest()
    result['extensionVersion'] = json.loads((extension / 'manifest.json').read_text())['version']
    result['extensionWorkerSha256'] = hashlib.sha256((extension / 'service_worker.js').read_bytes()).hexdigest()
    manifest = a.output / (host_name + '.json')
    manifest.write_text(json.dumps({'name':host_name, 'description':'Relay smoke fixture',
        'path':host, 'type':'stdio', 'allowed_origins':['chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/']}))
    if a.platform == 'windows':
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_32KEY) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
        registered = True
    hosts = profile / 'NativeMessagingHosts'
    hosts.mkdir(parents=True)
    shutil.copyfile(manifest, hosts / manifest.name)
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log, text=True)
    def read_replies():
        try:
            for line in child.stdout:
                replies.put(json.loads(line))
        finally:
            replies.put(None)
    threading.Thread(target=read_replies, daemon=True).start()
    assert operator('hello', processId=os.getpid(), executable='/usr/bin/true')['ok']
    state = operator('state')['state']
    endpoint = state.get('socket')
    status = poll(lambda: (v if v.get('data', {}).get('ready') else None)
        if (v := raw('status')) else None, 'interactive resident ready')
    if a.platform == 'windows':
        assert status['data']['processId'] == child.pid, 'Wrong desktop runtime process'
    check('access starts Off', raw('browser.tabs').get('errorCode') == 'approval_required')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = 'http://127.0.0.1:' + str(server.server_port) + '/'
    flags = [str(a.chrome), '--user-data-dir=' + str(profile), '--no-first-run', '--no-default-browser-check',
        '--password-store=basic', '--disable-gpu', '--remote-debugging-port=0',
        '--force-renderer-accessibility', '--disable-extensions-except=' + str(extension), '--load-extension=' + str(extension)]
    if a.platform == 'linux':
        flags += ['--ozone-platform=wayland'] + (['--no-sandbox'] if a.no_sandbox else [])
    chrome = subprocess.Popen(flags + [url], stdout=log, stderr=log, start_new_session=a.platform == 'linux')
    poll((profile / 'DevToolsActivePort').exists, 'dedicated browser startup')
    port, path = (profile / 'DevToolsActivePort').read_text().splitlines()[:2]
    spec = importlib.util.spec_from_file_location('fixture_cdp', a.cdp_client)
    cdp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cdp)
    def connect_cdp(url):
        if not hasattr(cdp, 'CdpSocket'):
            return cdp.CDP(url)
        class Adapter:
            def __init__(self):
                self.socket = cdp.CdpSocket(url, timeout=30)
            def call(self, method, **params):
                reply = self.socket.call(method, params)
                assert 'error' not in reply, 'Fixture CDP refused: ' + method
                return reply.get('result', {})
            def close(self):
                self.socket.close()
        return Adapter()
    root_cdp = connect_cdp('ws://127.0.0.1:' + port + path)
    target = root_cdp.call('Target.createTarget', url='chrome://extensions/')['targetId']
    with urlopen('http://127.0.0.1:' + port + '/json/list', timeout=5) as response:
        page = next(t for t in json.load(response) if t['id'] == target)
    setup = connect_cdp(page['webSocketDebuggerUrl'])
    try:
        setup.call('Runtime.evaluate', expression='new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))', awaitPromise=True)
    finally:
        setup.close(); root_cdp.call('Target.closeTarget', targetId=target)
    poll(lambda: operator('state')['state']['browser']['connected'], 'native messaging connection')
    check('extension connects to current native relay')
    assert operator('arm', scopes=['browser', 'devtools'], duration=300)['ok']
    poll(lambda: operator('state')['state'].get('safetyNoticeReady', True), 'visible access notice')
    if a.platform == 'windows':
        sys.path.insert(0, str(a.runtime.parent / 'client'))
        from control_session import ControlSession
        owner = ControlSession({'command':[sys.executable, str(Path(__file__).resolve()),
            '--channel', str(exe), str(session.value)]}, reason='Focused browser relay smoke',
            scopes=['browser', 'devtools'], wait=60, duration=300)
        owner.wait()
    tab = poll(lambda: next((t['tabId'] for t in call('browser.tabs')['tabs'] if t['url'] == url), None), 'fixture tab')
    snapshot = call('browser.snapshot', tabId=tab)
    reference = next(e['reference'] for e in snapshot['elements'] if e.get('name') == 'Increment' and e.get('role') == 'button')
    call('browser.click', reference=reference)
    poll(lambda: received == ['click'], 'independent HTTP click effect')
    check('snapshot and click have an independent page effect')
    capture = call('browser.capture', tabId=tab)
    artifact = capture.get('artifact', capture)
    file = Path(artifact['guestPath']) if 'guestPath' in artifact else Path(call('status')['artifactRoot']) / (artifact['artifactId'] + '.png')
    image = file.read_bytes()
    check('capture is a PNG with the declared hash', image.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(image).hexdigest() == artifact['sha256'])
    file.unlink()
    call('browser.eval', tabId=tab, expression="setTimeout(()=>alert('relay smoke'),50);true")
    dialog = poll(lambda: call('browser.dialog', tabId=tab, action='status').get('dialog'), 'observed JavaScript dialog')
    check('discovery progresses while a dialog is open', any(t['tabId'] == tab for t in call('browser.tabs')['tabs']))
    check('typed dialog handling works', call('browser.dialog', tabId=tab, action='accept', dialogId=dialog['id'])['handled'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(raw, 'browser.eval', tabId=tab, expression='new Promise(()=>{})', timeoutMs=3000)
        time.sleep(.1)
        started = time.monotonic()
        if owner is not None:
            assert owner.status()['state'] == 'active'
            check('control status stays responsive during stalled work', time.monotonic() - started < 2)
        else:
            call('browser.tabs')
            check('discovery stays responsive during stalled work', time.monotonic() - started < 2)
        timeout = pending.result(timeout=10)
    check('dispatched timeout reports uncertainty', not timeout['accepted'] and timeout['delivery'] == 'unknown')
    assert call('browser.release')['released'] is True, 'Browser detach was not confirmed'
    check('release recovers the timed-out route', call('browser.eval', tabId=tab, expression='document.title')['value'] == 'Relay smoke')
    assert operator('stop')['ok']
    if owner:
        owner.close(); owner = None
    check('Stop revokes browser access', raw('browser.tabs').get('errorCode') == 'approval_required')
    result['passed'] = True
except BaseException as error:
    result['error'] = type(error).__name__ + ': ' + str(error)
    result['errorCode'] = getattr(error, 'code', None)
    raise
finally:
    cleanup_errors = []
    def clean(label, action):
        try:
            action()
        except Exception as error:
            cleanup_errors.append(label + ": " + type(error).__name__)
    if owner:
        clean("owner", owner.close)
    if child and child.poll() is None:
        try:
            operator('quit')
            child.wait(timeout=10)
        except Exception:
            clean("resident termination", lambda: (child.kill(), child.wait(timeout=10)))
    if root_cdp:
        try:
            root_cdp.call('Browser.close')
        except Exception:
            pass
        clean("fixture CDP", root_cdp.close)
    if chrome:
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if a.platform == 'linux':
                os.killpg(chrome.pid, signal.SIGKILL)
            else:
                chrome.kill()
            chrome.wait(timeout=10)
    if a.platform == 'windows' and chrome:
        # The launcher may exit before its profile-owning process. Match both
        # the dedicated executable and unique profile, never a process name.
        literal = lambda value: "'" + str(value).replace("'", "''") + "'"
        cleanup = ('Get-CimInstance Win32_Process | Where-Object {$_.ExecutablePath -eq ' + literal(a.chrome) +
            ' -and $_.CommandLine -like ' + literal('*' + str(profile) + '*') +
            '} | ForEach-Object {Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue}')
        clean('browser processes', lambda: subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', cleanup],
            check=True, capture_output=True, timeout=30))
    def restore_registration():
        if old_key is None:
            if key_existed:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_32KEY) as key:
                    winreg.DeleteValue(key, '')
            else:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, key_path, winreg.KEY_WOW64_32KEY)
        else:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_32KEY) as key:
                winreg.SetValueEx(key, '', 0, old_key[1], old_key[0])
    if registered:
        clean("native registration", restore_registration)
    if server:
        clean('HTTP fixture', lambda: (server.shutdown(), server.server_close()))
    result['cleanupErrors'] = cleanup_errors
    result['passed'] = result['passed'] and not cleanup_errors
    (a.output / 'result.json').write_text(json.dumps(result, indent=2))
    log.close()

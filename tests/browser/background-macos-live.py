#!/usr/bin/env python3
"""Claimed VM-only background browser acceptance with independent effects.

Uses a separate Chrome for Testing identity/profile, the installed resident,
an owned native foreground sentinel and an HTTP effect oracle. Caller owns
claim, staging, power restoration and private evidence retention.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--chrome', type=Path, required=True)
    p.add_argument('--host-executable', type=Path, required=True)
    p.add_argument('--socket', type=Path, required=True)
    p.add_argument('--claim', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--focus-emulation', action='store_true', help='Explicit diagnostic experiment')
    a = p.parse_args()
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).decode().startswith('VirtualMac')
    assert 'Google Chrome for Testing.app/Contents/MacOS/' in str(a.chrome)
    a.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('cdp', a.source_root / 'platforms/chromeos/cdp.py')
    cdp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cdp)
    checks, effects, clients = [], [], []
    focus_reports = {}
    browser = sentinel = server = None
    failure = None

    def check(name, condition=True):
        assert condition, name
        checks.append(name)
        print('PASS:', name, flush=True)

    def poll(fn, seconds=20):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            value = fn()
            if value:
                return value
            time.sleep(.05)
        raise AssertionError('Timed out waiting for independent state')

    def raw(operation, **params):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(35)
            channel.connect(str(a.socket))
            channel.sendall(json.dumps(dict(operation=operation, claimId=a.claim, **params)).encode() + b'\n')
            return json.loads(channel.makefile('rb').readline(24 * 1024 * 1024))

    def call(operation, **params):
        reply = raw(operation, **params)
        assert reply.get('accepted'), (operation, reply.get('errorCode'), reply.get('message'))
        return reply.get('data', {})

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            body = b'''<!doctype html><title>Background fixture</title>
<button onclick="fetch('/effect',{method:'POST',body:'clicked'})">Increment</button>
<input aria-label="Background text" oninput="fetch('/effect',{method:'POST',body:this.value})">
<script>function reportFocus(){fetch('/focus',{method:'POST',body:JSON.stringify({
path:location.pathname,focused:document.hasFocus(),visible:document.visibilityState})})}
setInterval(reportFocus,50); addEventListener('focus',reportFocus); addEventListener('blur',reportFocus);
document.addEventListener('visibilitychange',reportFocus); reportFocus();</script>'''
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0))).decode()
            if self.path == '/focus':
                value = json.loads(body)
                focus_reports[value['path']] = {**value, 'at':time.monotonic()}
            else:
                effects.append(body)
            self.send_response(204)
            self.end_headers()

    scratch = tempfile.TemporaryDirectory(prefix='mc-background-')
    try:
        root = Path(scratch.name)
        profile = root / 'profile'
        hosts = profile / 'NativeMessagingHosts'
        hosts.mkdir(parents=True)
        (hosts / 'org.machine_control.browser.json').write_text(json.dumps({
            'name': 'org.machine_control.browser', 'description': 'Background fixture',
            'path': str(a.host_executable), 'type': 'stdio',
            'allowed_origins': ['chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/']}))
        extension = a.source_root / 'providers/chrome-extension'
        server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_port}/'
        log = (a.output / 'chrome.log').open('w')
        browser = subprocess.Popen([str(a.chrome), '--user-data-dir=' + str(profile),
            '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
            '--use-mock-keychain', '--no-proxy-server', '--disable-extensions-except=' + str(extension),
            '--load-extension=' + str(extension), url], stdout=log, stderr=log, start_new_session=True)
        port_file = profile / 'DevToolsActivePort'
        poll(port_file.exists)
        port, endpoint = port_file.read_text().splitlines()[:2]
        browser_cdp = cdp.CDP(f'ws://127.0.0.1:{port}{endpoint}')
        clients.append(browser_cdp)
        settings_id = browser_cdp.call('Target.createTarget', url='chrome://extensions/')['targetId']

        def connect_target(predicate):
            with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as response:
                targets = json.load(response)
            target = next((t for t in targets if predicate(t)), None)
            if target:
                client = cdp.CDP(target['webSocketDebuggerUrl'])
                clients.append(client)
                return client

        settings = poll(lambda: connect_target(lambda t: t['id'] == settings_id))
        settings.call('Runtime.evaluate', expression='new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))', awaitPromise=True)
        settings.close()
        browser_cdp.call('Target.closeTarget', targetId=settings_id)
        observer = poll(lambda: connect_target(lambda t: t['type'] == 'service_worker' and
            'chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/' in t['url']))

        def js(expression):
            result = observer.call('Runtime.evaluate', expression=expression, awaitPromise=True, returnByValue=True)
            assert not result.get('exceptionDetails'), result.get('exceptionDetails')
            return result.get('result', {}).get('value')

        poll(lambda: call('capabilities').get('browser', {}).get('connected'))
        selected = js('chrome.tabs.query({active:true})')
        sentinel_bin = root / 'sentinel'
        subprocess.run(['swiftc', str(a.source_root / 'tests/browser/focus-sentinel.swift'), '-o', str(sentinel_bin)], check=True)
        state_path = root / 'sentinel.json'
        sentinel = subprocess.Popen([str(sentinel_bin), str(state_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def state():
            return json.loads(state_path.read_text()) if state_path.exists() else {}

        before = poll(lambda: (s := state()) and s['frontPid'] == sentinel.pid and s['keyWindow'] and s)
        time.sleep(.1)
        before = state()
        new = call('browser.navigate', url=url + 'controlled', newTab=True)['tab']['tabId']
        check('new tab is inactive by default', not js(f'chrome.tabs.get({new})')['active'])
        check('user selected tabs unchanged', js('chrome.tabs.query({active:true}).then(ts=>ts.map(t=>t.id))') == [t['id'] for t in selected])
        snapshot = call('browser.snapshot', tabId=new)
        initial_focus = call('browser.cdp', tabId=new, method='Runtime.evaluate', params={'expression':'document.hasFocus()', 'returnByValue':True})
        js("globalThis.focusCommands=[]; globalThis.originalCommand=chrome.debugger.sendCommand; chrome.debugger.sendCommand=(target,method,params)=>{if(method==='Emulation.setFocusEmulationEnabled')focusCommands.push(params.enabled); return originalCommand(target,method,params);}")
        button = next(e for e in snapshot['elements'] if e['name'] == 'Increment')
        field = next(e for e in snapshot['elements'] if e['name'] == 'Background text')
        if a.focus_emulation:
            call('browser.cdp', tabId=new, method='Emulation.setFocusEmulationEnabled', params={'enabled': True})
        call('browser.click', reference=button['reference'])
        poll(lambda: 'clicked' in effects, seconds=3)
        check('inactive-tab click has independent HTTP effect', effects.count('clicked') == 1)
        call('browser.type', reference=field['reference'], text='background input')
        poll(lambda: 'background input' in effects, seconds=3)
        check('background text reaches only the target page', state()['text'] == '')
        capture = call('browser.capture', tabId=new)
        artifact = Path(capture['artifactPath'])
        check('background screenshot produces PNG', artifact.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n')
        artifact.unlink()
        denied = raw('browser.cdp', tabId=new, method='Page.bringToFront')
        check('foreground CDP refuses without opt-in', denied.get('errorCode') == 'foreground_required')
        time.sleep(.15)
        after = state()
        check('sentinel retains foreground and keyboard focus', after['frontPid'] == sentinel.pid and after['keyWindow'])
        check('no sampled foreground transition or cursor movement', after['foregroundChanges'] == before['foregroundChanges'] and after['cursor'] == before['cursor'])
        check('user selected tabs still unchanged', js('chrome.tabs.query({active:true}).then(ts=>ts.map(t=>t.id))') == [t['id'] for t in selected])
        release_time = time.monotonic()
        released = call('browser.release')
        check('release does not steal focus', state()['frontPid'] == sentinel.pid)
        (a.output / 'focus-diagnostics.json').write_text(json.dumps(dict(initialFocus=initial_focus,
            released=released, focusCommands=js('focusCommands'), focusReports=focus_reports,
            selected=js('chrome.tabs.query({active:true}).then(ts=>ts.map(t=>t.id))'), sentinel=state()), indent=2))
        # Connecting a native DevTools page observer can itself change page
        # focus. Use the page's own HTTP heartbeat, with no new attachment.
        poll(lambda: (s := focus_reports.get('/controlled')) and s['at'] > release_time and s['visible'] == 'hidden', seconds=5)
        check('page HTTP heartbeat confirms normal hidden visibility restored')
        endpoint = call('browser.endpoint')['browserEndpoint']
        bridge = cdp.CDP(endpoint)
        clients.append(bridge)
        created = bridge.call('Target.createTarget', url=url)['targetId']
        check('streamed CDP creates inactive tabs by default', js('chrome.tabs.query({active:true}).then(ts=>ts.map(t=>t.id))') == [t['id'] for t in selected])
        try:
            bridge.call('Target.activateTarget', targetId=created)
            raise AssertionError('Foreground stream unexpectedly accepted')
        except RuntimeError as error:
            check('streamed activation requires foreground opt-in', 'explicit opt-in' in str(error))
        bridge.call('MachineControl.setForegroundAllowed', allowed=True)
        bridge.call('Target.activateTarget', targetId=created)
        created_tab = next(t['tabId'] for t in js('chrome.debugger.getTargets()') if t['id'] == created)
        check('explicit stream foreground opt-in selects target', js(f'chrome.tabs.get({created_tab})')['active'])
        bridge.close()
        time.sleep(.2)
        bridge = cdp.CDP(endpoint)
        clients.append(bridge)
        try:
            bridge.call('Target.activateTarget', targetId=created)
            raise AssertionError('Reconnect inherited foreground opt-in')
        except RuntimeError as error:
            check('stream foreground opt-in resets on reconnect', 'explicit opt-in' in str(error))
        bridge.close()
        call('browser.cdp', tabId=new, method='Page.bringToFront', allowForeground=True)
        check('one-shot foreground opt-in selects requested tab', js(f'chrome.tabs.get({new})')['active'])
        default = call('browser.navigate', url=url, newTab=True)['tab']['tabId']
        check('one-shot opt-in never changes later creation defaults', not js(f'chrome.tabs.get({default})')['active'])
    except BaseException as error:
        import traceback
        failure = str(error)
        (a.output / 'failure.log').write_text(traceback.format_exc())
        (a.output / 'last-focus-reports.json').write_text(json.dumps(focus_reports, indent=2))
    finally:
        try:
            call('browser.release')
        except Exception:
            pass
        for client in clients:
            try:
                client.close()
            except Exception:
                pass
        if sentinel:
            sentinel.terminate()
            sentinel.wait(timeout=10)
        if browser:
            try:
                os.killpg(browser.pid, signal.SIGTERM)
                browser.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait(timeout=10)
        if server:
            server.shutdown()
            server.server_close()
        scratch.cleanup()
        result = dict(passed=failure is None, checks=checks, failure=failure, focusEmulation=a.focus_emulation)
        (a.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
    return 1 if failure else 0


if __name__ == '__main__':
    raise SystemExit(main())

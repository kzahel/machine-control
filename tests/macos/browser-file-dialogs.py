#!/usr/bin/env python3
"""Guest-only browser/download crash smoke for native or packaged residents.

Caller owns read-only doctor, an exclusive VM claim, source staging, deployment
and lifecycle cleanup. Requires Chrome for Testing, the owned extension and an
unlocked VirtualMac. Reaps its browser/profile/server even on a failed action.
"""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import shutil
import signal
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--claim', required=True)
    parser.add_argument('--repeat', type=int, default=5)
    parser.add_argument('--expected-policy', choices=['standing', 'approval'], default='standing')
    parser.add_argument('--observer-socket', type=Path,
                        help='Separate standing observer presses the real native approval')
    parser.add_argument('--keyboard-environment', type=Path,
                        help='Guest-only helper; change enabled layouts before each panel choice')
    parser.add_argument('--settings-cycle', action='store_true',
                        help='Recreate and close the packaged Settings window between download/upload cycles')
    args = parser.parse_args()
    assert 1 <= args.repeat <= 30
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).decode().startswith('VirtualMac')
    app = Path.home() / 'mc-cft/chrome-mac-arm64/Google Chrome for Testing.app'
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    assert info['CFBundleIdentifier'] == 'com.google.chrome.for.testing'
    binary = app / 'Contents/MacOS' / info['CFBundleExecutable']
    resident = Path.home() / 'Applications/Machine Control.app/Contents/MacOS/macui'
    endpoint = Path.home() / 'Library/Application Support/MachineControl/control.sock'
    spec = importlib.util.spec_from_file_location('cdp', args.source_root / 'platforms/chromeos/cdp.py')
    cdp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cdp)
    generation = None
    checks = []
    effects = {'upload': None, 'text': None, 'clicks': 0}
    payload = b'Machine Control harmless download fixture\n'
    reports = Path.home() / 'Library/Logs/DiagnosticReports'
    before_reports = set(reports.glob('macui-*.ips'))

    def exchange(socket_path, operation, **fields):
        with socket.socket(socket.AF_UNIX) as channel:
            channel.settimeout(30)
            channel.connect(str(socket_path))
            channel.sendall(json.dumps(dict(operation=operation, claimId=args.claim, **fields)).encode() + b'\n')
            line = channel.makefile('rb').readline(32 * 1024 * 1024)
            if not line:
                raise ConnectionError('Resident disconnected during ' + operation + '; outcome unknown; do not replay')
            result = json.loads(line)
        return result

    def raw(operation, **fields):
        nonlocal generation
        result = exchange(endpoint, operation, **fields)
        if generation is None:
            generation = result['generation']
        assert result.get('generation') == generation, 'Resident restarted during smoke'
        return result

    def call(operation, **fields):
        result = raw(operation, **fields)
        assert result.get('accepted'), operation + ': ' + str(result.get('errorCode'))
        assert result.get('hostInterference') == 'none'
        return result.get('data', {})

    def poll(fn, label, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = fn()
            if value:
                return value
            time.sleep(.15)
        raise AssertionError('Timed out: ' + label)

    def check(label, condition=True):
        assert condition, label
        checks.append(label)
        print('PASS:', label, flush=True)

    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            if self.path == '/upload':
                effects['upload'] = body
            elif self.path == '/text':
                effects['text'] = body.decode()
            elif self.path == '/click':
                effects['clicks'] += 1
            self.send_response(204)
            self.end_headers()

        def do_GET(self):
            if self.path == '/download':
                body = payload
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Disposition', 'attachment; filename="fixture.txt"')
            else:
                body = '''<!doctype html><meta charset="utf-8"><title>Browser file dialog smoke</title>
<h1>Browser file dialog smoke</h1><a href="/download">Download fixture</a>
<button onclick="fetch('/click',{method:'POST'})">Increment</button>
<input aria-label="Fixture text" oninput="fetch('/text',{method:'POST',body:this.value})">
<input type="file" aria-label="Upload fixture" onchange="this.files[0].text().then(t=>fetch('/upload',{method:'POST',body:t}))">
'''.encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    initial = call('status')
    assert initial['deployment']['policy']['grantMode'] == args.expected_policy
    assert initial['desktopState'] == 'unlocked'
    pid = initial['processId']
    layout_state = None
    layouts = []
    layout_index = 0
    if args.keyboard_environment:
        layout_state = json.loads(subprocess.check_output([str(args.keyboard_environment), 'status']))
        layouts = [name for name in ['com.apple.keylayout.US', 'com.apple.keylayout.Dvorak',
                                    'com.apple.keylayout.DVORAK-QWERTYCMD']
                   if name in layout_state['enabledLayouts']]
        assert len(layouts) >= 2, 'Enable the dedicated guest layout fixture first'

    server = ThreadingHTTPServer(('127.0.0.1', 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    browser = None
    tab = None
    workspace = tempfile.TemporaryDirectory(prefix='mc-browser-dialogs-')
    try:
        root = Path(workspace.name)
        if args.expected_policy == 'approval':
            assert args.observer_socket, 'Workstation approval requires an independent observer'
            assert call('grant.status')['grant'] is None, 'Packaged trial must start with access Off'
            with concurrent.futures.ThreadPoolExecutor() as pool:
                pending = pool.submit(call, 'grant.request', scopes=['observe', 'control', 'browser'],
                                      reason='Verify packaged browser file dialogs',
                                      durationSeconds=900, timeoutSeconds=120)
                def allow():
                    result = exchange(args.observer_socket, 'snapshot', target=str(pid), query='Allow',
                                      projection='compact', maxDepth=30, maxElements=600)
                    assert result.get('accepted'), 'Observer could not inspect native approval'
                    return next((e['reference'] for e in result['data']['elements']
                                 if e.get('label') == 'Allow' and e.get('role') == 'AXButton'), None)
                reference = poll(allow, 'native approval Allow')
                result = exchange(args.observer_socket, 'action', reference=reference, action='press')
                assert result.get('accepted'), 'Observer could not press native approval'
                pending.result(timeout=30)
            check('packaged workstation native approval')
        last_blockers = None
        def available():
            nonlocal last_blockers
            state = call('grant.status')['availability']
            blockers = state['blockingReasons']
            if blockers != last_blockers:
                print('AVAILABILITY:', json.dumps(blockers), flush=True)
                last_blockers = blockers
            return not state['paused']
        # A new process conservatively seeds its activity guard from HID idle
        # time, including recent synthetic input from the preceding trial.
        # Observe the normal quiet window; never disable or resume the guard.
        poll(available, 'native availability quiet window', timeout=45)
        profile = root / 'profile'
        hosts = profile / 'NativeMessagingHosts'
        hosts.mkdir(parents=True)
        (profile / 'Default').mkdir()
        (profile / 'Default/Preferences').write_text(json.dumps({'download': {
            'prompt_for_download': True, 'default_directory': str(root), 'directory_upgrade': True,
        }}))
        extension = root / 'extension'
        extension_source = (resident.parents[1] / 'Resources/chrome-extension'
                            if args.expected_policy == 'approval'
                            else args.source_root / 'providers/chrome-extension')
        shutil.copytree(extension_source, extension)
        (hosts / 'org.machine_control.browser.json').write_text(json.dumps({
            'name': 'org.machine_control.browser', 'description': 'Browser dialog smoke',
            'path': str(resident), 'type': 'stdio',
            'allowed_origins': ['chrome-extension://ncbfifkjllmnkkjmomjohinigfgdocjc/'],
        }))
        url = f'http://127.0.0.1:{server.server_port}/'
        browser = subprocess.Popen([str(binary), '--user-data-dir=' + str(profile),
            '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
            '--use-mock-keychain', '--no-proxy-server', '--force-renderer-accessibility',
            '--disable-extensions-except=' + str(extension), '--load-extension=' + str(extension), url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        port_file = profile / 'DevToolsActivePort'
        poll(port_file.exists, 'test browser ready')
        port, path = port_file.read_text().splitlines()[:2]
        # Enable only this isolated profile's extension developer mode.
        connection = cdp.CDP(f'ws://127.0.0.1:{port}{path}')
        settings_id = connection.call('Target.createTarget', url='chrome://extensions/')['targetId']
        try:
            with urlopen(f'http://127.0.0.1:{port}/json/list', timeout=5) as response:
                settings_page = next(t for t in json.load(response) if t['id'] == settings_id)
            settings = cdp.CDP(settings_page['webSocketDebuggerUrl'])
            try:
                settings.call('Runtime.evaluate', expression='new Promise(r=>chrome.developerPrivate.updateProfileConfiguration({inDeveloperMode:true},r))', awaitPromise=True)
            finally:
                settings.close()
        finally:
            connection.call('Target.closeTarget', targetId=settings_id)
            connection.close()
        poll(lambda: call('status')['browser']['connected'], 'extension connected')
        tab = poll(lambda: next((t['tabId'] for t in call('browser.tabs')['tabs'] if t['url'] == url), None), 'fixture tab')

        def reference(label):
            return poll(lambda: next((e['reference'] for e in call('browser.snapshot', tabId=tab)['elements']
                                      if e.get('name') == label), None), label)

        def click(label):
            call('browser.click', reference=reference(label))

        def native_elements():
            return call('snapshot', target=str(browser.pid), provider='macos-native',
                        maxDepth=24, maxElements=1000, projection='compact')['elements']

        def native_button(label):
            return next((e['reference'] for e in native_elements()
                         if e.get('role') == 'AXButton' and e.get('label') == label), None)

        def press(label):
            ref = poll(lambda: native_button(label), 'native button ' + label)
            call('action', reference=ref, action='press', provider='macos-native')

        def panel():
            poll(lambda: native_button('Cancel'), 'native file panel')

        def choose(path, confirm=True):
            nonlocal layout_index
            if layouts:
                selected = layouts[layout_index % len(layouts)]
                layout_index += 1
                state = json.loads(subprocess.check_output([str(args.keyboard_environment), 'select', selected]))
                assert state['inputSourceId'] == selected
                print('LAYOUT:', selected, flush=True)
            return call('dialog.choose', target=str(browser.pid), path=str(path), confirm=confirm)

        def cycle_settings():
            assert args.expected_policy == 'approval' and args.observer_socket
            subprocess.run([str(resident), 'serve', str(endpoint), '--settings'],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            poll(lambda: call('status')['presentation']['settingsWebViews'] == 1, 'Settings recreated')
            def close_button():
                # Compact projection omits subrole. Inspect native window
                # chrome with the full fields needed to identify the close button.
                result = exchange(args.observer_socket, 'snapshot', target=str(pid),
                                  query='AXCloseButton', projection='full', maxDepth=6, maxElements=300)
                assert result.get('accepted'), 'Observer could not inspect packaged Settings'
                elements = result['data']['elements']
                buttons = [e['reference'] for e in elements if e.get('subrole') == 'AXCloseButton']
                return buttons[0] if len(buttons) == 1 else None
            ref = poll(close_button, 'Settings close button')
            result = exchange(args.observer_socket, 'action', reference=ref, action='press')
            assert result.get('accepted'), 'Observer could not close packaged Settings'
            poll(lambda: call('status')['presentation']['settingsWebViews'] == 0, 'Settings destroyed')
            check('Settings recreated and closed in the same runtime')

        click('Increment')
        poll(lambda: effects['clicks'] == 1, 'HTTP click effect')
        call('browser.type', reference=reference('Fixture text'), text='Browser café 世界')
        poll(lambda: effects['text'] == 'Browser café 世界', 'Unicode typing effect')
        check('extension click and Unicode text independently observed')
        image = call('browser.capture', tabId=tab)
        artifact = Path(image['artifactPath'])
        try:
            check('browser capture PNG', artifact.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
        finally:
            artifact.unlink(missing_ok=True)

        upload = root / 'upload fixture.txt'
        upload.write_bytes(payload)
        for index in range(args.repeat):
            if args.settings_cycle:
                cycle_settings()
            destination = root / f'download {index}.txt'
            click('Download fixture')
            panel()
            data = choose(destination)
            assert data['dialog']['panelClosed']
            poll(lambda: destination.exists() and destination.read_bytes() == payload, 'download contents')
            check(f'download/save {index + 1}: exact bytes')

            effects['upload'] = None
            click('Upload fixture')
            panel()
            choose(upload)
            poll(lambda: effects['upload'] == payload, 'upload bytes received')
            check(f'upload/open {index + 1}: exact HTTP body')
            # Reset the input through the browser's typed route so the same
            # file raises a new change event on the next iteration.
            call('browser.navigate', tabId=tab, url=url)
            reference('Download fixture')

        cancelled = root / 'cancelled.txt'
        click('Download fixture')
        panel()
        data = choose(cancelled, confirm=False)
        assert not data['dialog']['confirmed']
        press('Cancel')
        check('download cancellation leaves no file', not cancelled.exists())

        existing = root / 'download 0.txt'
        click('Download fixture')
        panel()
        data = choose(existing)
        assert not data['dialog']['panelClosed'] and data['dialog']['followUp']
        check('overwrite follow-up is reported and left unanswered', existing.read_bytes() == payload)
        press('Cancel')
        press('Cancel')

        # Browser Save Page As uses its own native save panel.
        native_elements()  # Inspect current surface before the shortcut.
        call('input.key', target=str(browser.pid), provider='macos-native', key='cmd-s')
        panel()
        page_path = root / 'saved page.html'
        choose(page_path)
        poll(lambda: page_path.exists() and b'Browser file dialog smoke' in page_path.read_bytes(), 'saved HTML')
        check('Save Page As writes fixture HTML')
        refused = raw('dialog.choose', target=str(browser.pid), path=str(upload))
        check('missing panel refuses without crashing', not refused['accepted'] and refused.get('errorCode') == 'dialog_not_found')
        final = call('status')
        check('resident PID and generation survive the full suite', final['processId'] == pid)
        check('no new macui OS crash report', set(reports.glob('macui-*.ips')) == before_reports)
        print(json.dumps({'passed': True, 'checks': len(checks), 'repeat': args.repeat,
            'macOS': subprocess.check_output(['sw_vers', '-productVersion']).decode().strip(),
            'browserVersion': info['CFBundleShortVersionString'],
            'residentSha256': hashlib.sha256(resident.read_bytes()).hexdigest(),
            'frameworkSha256': hashlib.sha256((resident.parents[1] / 'Frameworks/MCResident.framework/MCResident').read_bytes()).hexdigest()
                if args.expected_policy == 'approval' else None}), flush=True)
    finally:
        if tab is not None:
            try:
                raw('browser.release', tabId=tab)
            except (OSError, ValueError, AssertionError):
                pass
        if browser is not None:
            try:
                os.killpg(browser.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                browser.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(browser.pid, signal.SIGKILL)
                browser.wait()
        server.shutdown()
        server.server_close()
        workspace.cleanup()
        if layout_state is not None:
            restored = json.loads(subprocess.check_output([
                str(args.keyboard_environment), 'select', layout_state['inputSourceId']]))
            assert restored['inputSourceId'] == layout_state['inputSourceId']
        if args.expected_policy == 'approval':
            try:
                exchange(endpoint, 'grant.revoke')
            except (OSError, ValueError):
                pass


if __name__ == '__main__':
    main()

"""Isolated, interactive Medium-session presentation acceptance.

The caller owns doctor/claim/cleanup. No installed app or policy is modified.
Operator actions use UIA; agent effects use the ordinary retained channel.
"""
import argparse
import base64
import concurrent.futures
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'presentation-fixture', '--session-id', sys.argv[3]]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'client'))
from control_session import ControlSession


def ps(script):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode()
    result = subprocess.run(['pwsh.exe', '-NoProfile', '-EncodedCommand', encoded],
                            capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    app_exe = args.install / 'machine-control.exe'
    instance = 'presentation-fixture'
    session = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    report = {'schema': 'machine-control-runtime-presentation-live/v0', 'passed': False,
              'checks': [], 'appSha256': hashlib.sha256(app_exe.read_bytes()).hexdigest(),
              'runtimeSha256': hashlib.sha256(exe.read_bytes()).hexdigest()}
    report['results'] = []
    app = fixture = owner = None
    preference = Path(os.environ['LOCALAPPDATA']) / 'MachineControl/presentation' / (instance + '.json')
    original = preference.read_bytes() if preference.exists() else None
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"

    def check(value, label):
        if not value:
            raise AssertionError(label)
        report['checks'].append(label)
        print(label, flush=True)

    def wait(predicate, label, seconds=30):
        until = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= until:
                raise TimeoutError(label)
            time.sleep(.15)

    def direct(request):
        result = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', instance,
                                 '--session-id', session], input=json.dumps(request),
                                capture_output=True, text=True, timeout=20)
        if not result.stdout.strip():
            raise RuntimeError('Presentation CLI failed: ' + result.stderr.strip())
        return json.loads(result.stdout)

    def config(*arguments):
        result = subprocess.run([str(app_exe), 'presentation', *arguments, '--instance', instance],
                                capture_output=True, text=True, timeout=45)
        if not result.stdout.strip():
            raise RuntimeError('Presentation CLI failed: ' + result.stderr.strip())
        return json.loads(result.stdout)

    def windows(pid, title=None):
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
        script += '$items=[Windows.Automation.AutomationElement]::RootElement.FindAll([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,' + str(pid) + '));'
        script += '$names=@($items | ForEach-Object {$_.Current.Name});ConvertTo-Json -InputObject $names -Compress'
        names = json.loads(ps(script))
        return title in names if title else names

    def ui(title, name=None):
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;$until=[DateTime]::UtcNow.AddSeconds(12);do{'
        script += '$root=[Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,' + quote(title) + '));'
        if name:
            script += 'if($root){$item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,' + quote(name) + '),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::Button)));if($item){break}};'
        else:
            script += 'if($root){break};'
        script += 'Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $until);'
        script += '$item.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()' if name else '$root.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).Close()'
        ps(script)
        time.sleep(.4)

    def stop_hotkey():
        ps('Add-Type -TypeDefinition \'using System;using System.Runtime.InteropServices;public static class StopKey{[DllImport("user32.dll")] public static extern void keybd_event(byte key,byte scan,uint flags,UIntPtr extra);}\';'
           'foreach($k in @(17,18,16,190)){[StopKey]::keybd_event($k,0,0,[UIntPtr]::Zero)};foreach($k in @(190,16,18,17)){[StopKey]::keybd_event($k,0,2,[UIntPtr]::Zero)}')

    try:
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        check(config('reset')['ok'], 'Offline CLI recovery')
        marker = args.output / 'pointer.json'
        fixture = subprocess.Popen([str(args.install / 'runtime/fixtures/machine-control-medium-fixture.exe'), '--pointer-output', str(marker)])
        wait(lambda: marker.exists() and json.loads(marker.read_text())['processId'] == fixture.pid, 'fixture ready')
        for profile in ('personal', 'minimal', 'appliance'):
            check(config('set', profile)['ok'], profile + ': persist offline')
            app = subprocess.Popen([str(app_exe), '--instance', instance], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            wait(lambda: config('status').get('runtimeId') is not None, 'runtime ready', 60)
            runtime = config('status')['runtimeId']
            check(all(config('status').get('runtimeId') == runtime for _ in range(8)), profile + ': repeated configuration replies retain runtime')
            time.sleep(2)
            check(windows(app.pid, 'Machine Control') == (profile == 'personal'), profile + ': startup Settings policy')
            check(not direct({'operation': 'move', 'x': 20, 'y': 20})['accepted'], profile + ': presentation grants no access')
            if profile == 'personal':
                ui('Machine Control')
            check(not windows(app.pid, 'Machine Control'), profile + ': Settings absent')
            with concurrent.futures.ThreadPoolExecutor() as pool:
                requested = pool.submit(direct, {'operation': 'grant.request', 'scopes': ['observe', 'control'],
                                                'durationSeconds': 300, 'timeoutSeconds': 25, 'reason': 'Native presentation fixture'})
                wait(lambda: windows(runtime, 'Machine Control access request'), 'native approval visible')
                check(not config('set', 'personal')['ok'], profile + ': pending approval defers configuration')
                ui('Machine Control access request', 'Allow')
                check(requested.result(timeout=30)['accepted'], profile + ': native approval without Settings')
            owner = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session]},
                                   reason='Native presentation fixture effect', scopes=('observe', 'control'), wait=120, duration=300)
            wait(lambda: windows(runtime, 'Machine Control is ready to use the desktop'), 'native activation notice')
            ui('Machine Control is ready to use the desktop', 'Start now')
            owner.wait()
            time.sleep(.4)
            before = json.loads(marker.read_text())
            x, y = before['bounds']['x'] + 60, before['bounds']['y'] + 60
            if before['events'] and before['events'][-1]['x'] == x and before['events'][-1]['y'] == y:
                x += 35
                y += 35
            effect = owner.call({'operation': 'move', 'x': x, 'y': y})
            report['results'].append(effect)
            check(effect['accepted'] and effect['delivery'] == 'confirmed', profile + ': native delivery')
            wait(lambda: len(json.loads(marker.read_text())['events']) > len(before['events']), 'independent native effect')
            check(True, profile + ': independent fixture effect')
            old_fence = dict(owner.view)
            owner.close(); owner = None
            replacement = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session]},
                                         reason='Owner loss replacement fixture', scopes=('observe', 'control'), wait=120, duration=300)
            owner = replacement
            owner.wait()
            check(owner.view['sessionId'] != old_fence['sessionId'], profile + ': disconnect releases owner and replaces session')
            try:
                owner._rpc({'operation': 'control.dispatch', 'sessionId': old_fence['sessionId'],
                            'resourceGenerations': old_fence['resourceGenerations'], 'request': {'operation': 'click', 'x': x, 'y': y}})
                raise AssertionError('Stale ownership dispatched')
            except Exception as error:
                check(getattr(error, 'code', None) is not None, profile + ': stale ownership refused')
            subprocess.run([str(app_exe), '--instance', instance, '--settings'], timeout=10, check=True)
            wait(lambda: windows(app.pid, 'Machine Control'), 'same-runtime recovery')
            check(config('status')['runtimeId'] == runtime, profile + ': second launch retains resident')
            ui('Machine Control', 'Pause access')
            wait(lambda: owner.status()['state'] != 'active', 'Pause acknowledgement', 10)
            paused = owner.status()
            report['pauseStatus'] = paused
            check(paused['state'] != 'active', profile + ': Pause removes active ownership')
            owner.close(); owner = None
            ui('Machine Control', 'Resume access')
            owner = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session]},
                                   reason='Resume replacement fixture', scopes=('observe', 'control'), wait=120, duration=300)
            owner.wait()
            ui('Machine Control')
            if profile == 'minimal':
                timings = []
                def discovery(_):
                    start = time.monotonic()
                    value = direct({'operation': 'status'})
                    timings.append((time.monotonic() - start) * 1000)
                    return value['accepted']
                with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                    check(all(pool.map(discovery, range(60))), 'Load: 60 discovery requests across six clients')
                report['discoveryLatencyMs'] = {'maximum': max(timings), 'p95': sorted(timings)[int(len(timings)*.95)-1]}
                # Exhaust public handshake capacity without completing frames.
                # The inherited operator and local configuration pipes remain
                # independent of these six stalled peers plus the owner.
                sid = ps('[Security.Principal.WindowsIdentity]::GetCurrent().User.Value')
                pipe_name = '\\\\.\\pipe\\machine-control-user-' + sid + '-' + session + '-' + instance
                kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
                kernel.CreateFileW.restype = ctypes.c_void_p
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                peers = []
                try:
                    for _ in range(6):
                        until = time.monotonic() + 3
                        while True:
                            handle = kernel.CreateFileW(pipe_name, 0xC0000000, 0, None, 3, 0, None)
                            if handle not in (None, ctypes.c_void_p(-1).value):
                                break
                            if ctypes.get_last_error() != 231 or time.monotonic() >= until:
                                raise OSError(ctypes.get_last_error(), 'Handshake peer connect failed')
                            time.sleep(.02)
                        peers.append(handle)
                    recovery_start = time.monotonic()
                    subprocess.run([str(app_exe), '--instance', instance, '--settings'], timeout=10, check=True)
                    wait(lambda: windows(app.pid, 'Machine Control'), 'Settings recovery under handshake load', 10)
                    report['handshakeRecoveryMs'] = (time.monotonic() - recovery_start) * 1000
                    check(config('status')['runtimeId'] == runtime, 'Stalled public handshakes preserve Settings and configuration recovery')
                    ui('Machine Control')
                finally:
                    for handle in peers:
                        kernel.CloseHandle(handle)
            baseline = len([e for e in json.loads(marker.read_text())['events'] if e['kind'] == 'down'])
            with concurrent.futures.ThreadPoolExecutor() as pool:
                dragging = pool.submit(owner.call, {'operation': 'drag', 'x': x, 'y': y, 'x2': x + 150, 'y2': y + 100, 'durationMs': 5000})
                wait(lambda: len([e for e in json.loads(marker.read_text())['events'] if e['kind'] == 'down']) > baseline, 'drag dispatched')
                stop_hotkey()
                check(not dragging.result(timeout=20)['accepted'], profile + ': Stop cancels native drag')
            wait(lambda: len([e for e in json.loads(marker.read_text())['events'] if e['kind'] == 'up']) > baseline, 'native release after Stop')
            check(True, profile + ': independent release after cancellation')
            wait(lambda: direct({'operation': 'grant.status'})['data'].get('grant') is None, 'Stop revokes')
            check(owner.status()['state'] == 'ended', profile + ': independent Stop ends owner')
            owner.close(); owner = None
            check(config('status')['runtimeId'] == runtime, profile + ': resident survives closed Settings and Stop')
            app.terminate(); app.wait(timeout=10); app = None
            wait(lambda: config('status').get('runtimeId') is None, 'owned resident reaped')
        check(config('set', 'minimal')['ok'], 'Saved minimal before override')
        app = subprocess.Popen([str(app_exe), '--instance', instance, '--presentation', 'personal', '--settings'])
        wait(lambda: config('status').get('runtimeId') is not None, 'override launch')
        old_runtime = config('status')['runtimeId']
        check(config('status')['presentation']['temporaryOverride'], 'Launch override is temporary')
        ui('Machine Control', 'Settings')
        ui('Machine Control', 'Restart')
        wait(lambda: config('status').get('runtimeId') not in (None, old_runtime), 'restart replacement', 60)
        check(config('status')['presentation']['profile'] == 'minimal' and not config('status')['presentation']['temporaryOverride'], 'Restart expires override and reloads saved profile')
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if owner:
            owner.close()
        # Only processes in this caller-owned staging directory are reaped.
        ps('$stage=' + quote(str(args.install.resolve())) + ';Get-Process | Where-Object {$_.Id -ne ' + str(os.getpid()) + ' -and $_.Path -and $_.Path.StartsWith($stage+"\\",[StringComparison]::OrdinalIgnoreCase)} | Stop-Process -Force')
        if original is None:
            preference.unlink(missing_ok=True)
        else:
            preference.write_bytes(original)
        (args.output / 'result.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

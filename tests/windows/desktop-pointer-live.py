"""Native desktop pointer acceptance with independent window-message effects.

Run as the logged-in console user in an owned staged desktop package. The
operator actor uses UIA; agent actions use the retained desktop owner channel.
"""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'desktop', '--session-id', sys.argv[3]]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'client'))
from control_session import ControlSession
spec = importlib.util.spec_from_file_location('uac_actor', Path(__file__).with_name('desktop-uac-live.py'))
actor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actor)
ps, quote = actor.ps, actor.quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    session = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    marker = args.output / 'pointer.json'
    report = {'schema': 'machine-control-pointer-live/v0', 'passed': False, 'checks': [],
              'runtimeSha256': hashlib.sha256(exe.read_bytes()).hexdigest(), 'results': []}
    app = fixture = owner = None

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
            time.sleep(.1)

    def direct(request):
        result = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', 'desktop', '--session-id', session],
                                input=json.dumps(request), capture_output=True, text=True, timeout=40)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return json.loads(result.stdout)

    def ui(name):
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
        script += '$root=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]' + str(operator_hwnd) + ');'
        script += '$item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,' + quote(name) + '));'
        script += 'if(!$item){throw ' + quote('Missing operator button: ' + name) + '};$item.GetCurrentPattern([Windows.Automation.InvokePattern]::Pattern).Invoke()'
        ps(script)
        time.sleep(.3)

    def minimized():
        ps('Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
           '$root=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]' + str(operator_hwnd) + ');'
           '$root.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).SetWindowVisualState([Windows.Automation.WindowVisualState]::Minimized)')

    def new_owner(scopes=('observe', 'control')):
        value = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session]},
                               reason='Native pointer fixture acceptance', scopes=scopes, wait=120, duration=300)
        value.wait()
        # The native announcement has ended; the UI polling loop still needs
        # its next tick to hide the protected notice window.
        time.sleep(1.5)
        return value

    def evidence():
        return json.loads(marker.read_text())

    def accepted(request):
        value = owner.call(request)
        report['results'].append(value)
        check(value['accepted'] and value.get('delivery') == 'confirmed', request['operation'] + ': native delivery accepted')
        check(value['effect'] == 'unverifiable', request['operation'] + ': delivery does not claim fixture effect')
        return value

    def interrupted_drag(control):
        baseline = len([e for e in evidence()['events'] if e['kind'] == 'down'])
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pending = pool.submit(owner.call, {'operation': 'drag', 'x': x, 'y': y, 'x2': x + 200, 'y2': y + 160, 'durationMs': 5000})
            wait(lambda: len([e for e in evidence()['events'] if e['kind'] == 'down']) > baseline, 'drag pressed')
            ui(control)
            result = pending.result(timeout=20)
        report['results'].append(result)
        check(not result['accepted'], control + ': running drag interrupted')
        wait(lambda: evidence()['events'][-1]['kind'] == 'up' or
             len([e for e in evidence()['events'] if e['kind'] == 'up']) >= baseline + 1, 'release after interruption')
        released = ps('Add-Type -TypeDefinition \'using System;using System.Runtime.InteropServices;public static class PointerState {[DllImport("user32.dll")] public static extern short GetAsyncKeyState(int key);}\';([PointerState]::GetAsyncKeyState(1) -band 32768) -eq 0')
        check(released == 'True', control + ': native button state released')

    try:
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        app = subprocess.Popen([str(args.install / 'machine-control.exe'), '--gui'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait(lambda: direct({'operation': 'status'}).get('data', {}).get('ready'), 'desktop ready', 120)
        operator_hwnd = int(ps('(Get-Process -Id ' + str(app.pid) + ').MainWindowHandle'))
        check(bool(operator_hwnd), 'Real operator settings window available')
        capabilities = direct({'operation': 'capabilities'})['data']
        check(all(op in capabilities['operations'] for op in ('move', 'drag', 'scroll')), 'Desktop advertises pointer operations')
        check(not direct({'operation': 'move', 'x': 600, 'y': 200})['accepted'], 'Access-off pointer request refused')
        ui('Enable access')
        owner = new_owner()
        # Arrange operator controls for exact self-protection checks. These
        # adjustments belong to the independent operator actor, not the agent.
        layout = json.loads(ps('Add-Type -TypeDefinition \'using System;using System.Runtime.InteropServices;public static class PointerWindow {[DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr w,int x,int y,int width,int height,bool repaint);[DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr w,out R r);public struct R{public int Left,Top,Right,Bottom;}}\';'
                               '[PointerWindow]::MoveWindow([IntPtr]' + str(operator_hwnd) + ',100,100,700,500,$true)|Out-Null;'
                               '$r=[PointerWindow+R]::new();[PointerWindow]::GetWindowRect([IntPtr]' + str(operator_hwnd) + ',[ref]$r)|Out-Null;$r|ConvertTo-Json -Compress'))
        sy = round((layout['Top'] + layout['Bottom']) / 2)
        protected = owner.call({'operation': 'move', 'x': layout['Left'] + 50, 'y': sy})
        check(not protected['accepted'] and protected.get('errorCode') == 'self_target_refused', 'Pointer cannot target operator controls')
        protected = owner.call({'operation': 'drag', 'x': layout['Left'] - 10, 'y': sy,
                                'x2': layout['Right'] + 10, 'y2': sy})
        check(not protected['accepted'] and protected.get('errorCode') == 'self_target_refused', 'Drag crossing operator controls refused before button press')
        owner.close(); owner = None
        minimized()
        fixture = subprocess.Popen([str(args.install / 'runtime/fixtures/machine-control-medium-fixture.exe'), '--pointer-output', str(marker)])
        wait(lambda: marker.exists() and evidence()['processId'] == fixture.pid, 'fixture ready', 60)
        bounds = evidence()['bounds']
        x, y = bounds['x'] + 60, bounds['y'] + 60
        report['fixturePid'] = fixture.pid
        owner = new_owner(('observe',))
        try:
            owner.call({'operation': 'move', 'x': x, 'y': y})
            raise AssertionError('Observe owner gained pointer control')
        except Exception as error:
            check(getattr(error, 'code', None) == 'operation_not_permitted_by_control_channel', 'Observe-only owner refuses pointer control')
        owner.close()
        owner = new_owner()
        accepted({'operation': 'move', 'x': x, 'y': y})
        wait(lambda: any(e['kind'] == 'move' and abs(e['x'] - x) <= 1 and abs(e['y'] - y) <= 1 for e in evidence()['events']), 'independent pointer motion')
        check(True, 'Fixture independently observes requested pointer position')
        accepted({'operation': 'click', 'x': x, 'y': y})
        before = evidence()
        scroll = accepted({'operation': 'scroll', 'deltaX': -120, 'deltaY': 240})
        wait(lambda: evidence()['horizontal'] == before['horizontal'] - 120 and evidence()['vertical'] == before['vertical'] + 240, 'independent wheel effects')
        check(scroll['data']['units'] == 'windows.wheel_delta', 'Wheel units explicitly reported')
        check(True, 'Fixture receives signed vertical and horizontal wheel messages')
        for button in ('left', 'right'):
            accepted({'operation': 'drag', 'x': x, 'y': y, 'x2': x + 160, 'y2': y + 120, 'button': button, 'durationMs': 500})
            wait(lambda: any(e['kind'] == 'up' and e['button'].lower() == button and abs(e['x'] - x - 160) <= 1 and abs(e['y'] - y - 120) <= 1 for e in evidence()['events']), 'independent drag release')
            check(True, button + ': fixture observes release at requested destination')
            up = next(e for e in reversed(evidence()['events']) if e['kind'] == 'up' and e['button'].lower() == button)
            down = next(e for e in reversed(evidence()['events']) if e['kind'] == 'down' and e['button'].lower() == button)
            check(0 < up['atMs'] - down['atMs'] < 2500, button + ': slow checks do not multiply requested hold duration')
        for invalid in ({'operation': 'move', 'x': -2147483648, 'y': 0},
                        {'operation': 'drag', 'x': x, 'y': y, 'x2': x + 10, 'y2': y + 10, 'durationMs': 5001},
                        {'operation': 'scroll', 'deltaY': 0}, {'operation': 'scroll', 'deltaY': 12001}):
            result = owner.call(invalid)
            check(not result['accepted'] and result.get('errorCode') == 'invalid_request', 'Invalid pointer request refused: ' + invalid['operation'])
        interrupted_drag('Pause access')
        check(direct({'operation': 'grant.status'})['data']['grant'] is not None, 'Pause retains standing consent')
        ui('Resume access')
        owner.wait()
        accepted({'operation': 'move', 'x': x, 'y': y})
        interrupted_drag('Stop access')
        check(direct({'operation': 'grant.status'})['data'].get('grant') is None, 'Stop removes standing consent')
        owner.close(); owner = None
        check(direct({'operation': 'status'})['data']['ready'], 'Unlocked-origin cleanup leaves console unlocked')
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if owner:
            owner.close()
        for process in (fixture, app):
            if process and process.poll() is None:
                process.terminate(); process.wait(timeout=10)
        (args.output / 'result.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

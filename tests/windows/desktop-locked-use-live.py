"""Real operator and existing-session desktop unlock/relock acceptance.

An outside claimed controller supplies setup consent and the existing dedicated
unlock relay. Passwords never enter this actor, its mailbox or evidence.
The activity scenario also requests independently generated virtual HID
diagnostic input; resident SendInput cannot substitute for that classification.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user',
                                     '--instance', 'desktop', '--session-id', sys.argv[3]]))

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'client'))
from control_session import ControlSession
spec = importlib.util.spec_from_file_location('desktop_uac_live', Path(__file__).with_name('desktop-uac-live.py'))
uac_actor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uac_actor)
ps, quote = uac_actor.ps, uac_actor.quote


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scenario', choices=('lifecycle', 'stop', 'service-crash', 'resident-crash',
                                               'covered', 'activity', 'unlocked', 'idle-lock'), default='lifecycle')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    exe = args.install / 'runtime/machine-control-windows.exe'
    session = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    marker = Path(os.environ['LOCALAPPDATA']) / 'MachineControl/conformance/counter.json'
    app = fixture = owner = None
    operator_hwnd = None
    run_id = uuid.uuid4().hex
    report = {'schema': 'machine-control-desktop-locked-use-live/v0', 'passed': False, 'scenario': args.scenario,
              'checks': [], 'runtimeSha256': hashlib.sha256(exe.read_bytes()).hexdigest()}

    def save():
        temporary = args.output / 'result.pending'
        temporary.write_text(json.dumps(report, indent=2))
        temporary.replace(args.output / 'result.json')

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        report['checks'].append(label)
        print(label, flush=True)

    def external(phase, data=None):
        name = phase + '.done'
        temporary = args.output / 'phase.pending'
        temporary.write_text(json.dumps({'phase': phase, 'data': data, 'runId': run_id}))
        temporary.replace(args.output / 'phase.json')
        failure = args.output / (phase + '.failure.json')
        wait(lambda: ((args.output / name).exists() and (args.output / name).read_text() == run_id)
             or (failure.exists() and json.loads(failure.read_text()).get('runId') == run_id),
             'outside actor ' + phase, 300)
        if failure.exists() and json.loads(failure.read_text()).get('runId') == run_id:
            raise RuntimeError('Outside actor refused: ' + phase + ': ' + json.loads(failure.read_text())['errorCode'])
        time.sleep(.5)

    def wait(predicate, description, seconds=25):
        deadline = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= deadline:
                raise TimeoutError(description)
            time.sleep(.2)

    def direct(request):
        try:
            result = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', 'desktop',
                                     '--session-id', session], input=json.dumps(request),
                                    capture_output=True, text=True, timeout=40)
        except subprocess.TimeoutExpired:
            return {}
        if result.returncode:
            return {}
        return json.loads(result.stdout)

    def ready():
        return direct({'operation': 'status'}).get('data', {}).get('ready') is True

    def ui(name, toggle=False):
        nonlocal operator_hwnd
        # Retain the settings window before ownership can create a second,
        # same-process control-notice window with the same product title.
        if operator_hwnd is None:
            operator_hwnd = int(ps('(Get-Process -Id ' + str(app.pid) + ').MainWindowHandle'))
            if not operator_hwnd:
                raise RuntimeError('Operator main window unavailable')
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
        script += 'Add-Type -TypeDefinition \'using System;using System.Runtime.InteropServices;public static class LockedActorWindow {[DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hwnd,int state);}\';'
        script += '$deadline=[DateTime]::UtcNow.AddSeconds(15);do {'
        script += '$hwnd=[IntPtr]'+str(operator_hwnd)+';$root=$null;'
        script += 'if($hwnd -ne 0){[LockedActorWindow]::ShowWindowAsync($hwnd,3)|Out-Null;$root=[Windows.Automation.AutomationElement]::FromHandle($hwnd)};'
        script += 'if($root){$item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'+quote(name)+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::'+('CheckBox' if toggle else 'Button')+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false)));if($item){break}};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline);if(!$item){throw '+quote('UI unavailable: '+name)+'};'
        script += '$item.GetCurrentPattern([Windows.Automation.'+('TogglePattern' if toggle else 'InvokePattern')+']::Pattern).'+('Toggle' if toggle else 'Invoke')+'()'
        ps(script)
        time.sleep(.4)

    def new_owner(prepared=True, duration=120, scopes=('observe', 'control')):
        value = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session]},
                               reason='Bounded Windows locked-use fixture', scopes=scopes,
                               prepared_console=prepared, wait=300 if args.scenario == 'activity' else 90, duration=duration)
        try:
            value.wait()
        except BaseException:
            report['admissionFailure'] = value.view
            value.close()
            raise
        return value

    def unlock(phase, duration=120):
        nonlocal owner
        external('lock-' + phase)
        wait(lambda: not ready(), 'independent lock')
        owner = new_owner(duration=duration)
        check(not owner.call({'operation': 'snapshot'})['accepted'], phase + ': ordinary dispatch refuses while locked')
        preparation = owner.call({'operation': 'session.unlock.prepare'})
        check(preparation['accepted'], phase + ': owned preparation accepted')
        external('unlock-' + phase, preparation['data'])
        wait(ready, 'independent unlock')
        check(ready(), phase + ': ordinary session is unlocked')

    try:
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        with (args.output / 'app.stderr').open('w') as diagnostic:
            app = subprocess.Popen([str(args.install / 'machine-control.exe'), '--gui'], stdout=subprocess.DEVNULL, stderr=diagnostic)
        wait(ready, 'desktop readiness', 100)
        check(not direct({'operation': 'snapshot'})['accepted'], 'Desktop begins with access off')
        if not direct({'operation': 'capabilities'})['data']['protectedDesktop']['installed']:
            ui('Permissions'); ui('Install helper…'); external('setup-helper')
            wait(ready, 'installed helper companion', 90)
        check(direct({'operation': 'capabilities'})['data']['protectedDesktop']['installed'], 'Protected helper installed through operator UI')
        ui('Access')
        if not direct({'operation': 'capabilities'})['data']['lockedUse']['permissionReady']:
            ui('Set up Machine Control helper'); external('approve-controller')
            wait(ready, 'controller approval completion', 90)
        check(direct({'operation': 'capabilities'})['data']['lockedUse']['permissionReady'], 'Exact local account controller approval is ready')
        ui('Also while the screen is locked', toggle=True)
        ui('Enable access')
        check(direct({'operation': 'capabilities'})['data']['lockedUse']['enabled'], 'Explicit operator opt-in enabled')
        check(not direct({'operation': 'session.unlock.prepare'})['accepted'], 'An unowned caller cannot prepare unlock')
        if args.scenario in ('unlocked', 'idle-lock'):
            owner = new_owner()
            check(ready(), 'Task starts with an unlocked console')
            if args.scenario == 'idle-lock':
                external('lock-idle-origin')
                try:
                    response = owner.call({'operation': 'session.unlock.prepare'})
                except Exception as refusal:
                    check(getattr(refusal, 'code', None) == 'task_did_not_start_locked',
                          'Later idle lock refuses before credential preparation')
                else:
                    check(not response['accepted'], 'Unlocked-origin task cannot unlock after idle lock')
                owner.close(); owner = None
                external('verify-relock-idle-origin')
            else:
                owner.close(); owner = None
                time.sleep(1)
                external('verify-unlocked-origin')
                check(ready(), 'Unlocked-origin task completion leaves console unlocked')
            report['passed'] = True
            return
        # The operator UI is protected even where another window overlaps it.
        # Arrange the fixture desktop through the operator actor before input.
        ps('Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
           '$root=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]' + str(operator_hwnd) + ');'
           '$root.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).SetWindowVisualState('
           '[Windows.Automation.WindowVisualState]::Minimized)')
        fixture = subprocess.Popen([str(args.install / 'runtime/fixtures/machine-control-medium-fixture.exe')])
        report['fixturePid'] = fixture.pid
        wait(lambda: marker.exists() and json.loads(marker.read_text())['processId'] == fixture.pid,
             'independent fixture marker')
        if args.scenario == 'activity':
            owner = new_owner(prepared=False, duration=300)
            original_session = owner.status()['sessionId']
            check(owner.call({'operation': 'snapshot', 'scope': 'system', 'processId': fixture.pid})['accepted'],
                  'Ordinary owner can observe before activity')
            external('diagnostic-human-ordinary')
            wait(lambda: 'physical_activity' in owner.status()['blockingReasons'], 'native human activity pause')
            check(owner.status()['state'] == 'paused', 'Virtual HID diagnostic input pauses real product ownership')
            check(ready(), 'Ordinary takeover leaves unlocked console unlocked')
            check(direct({'operation': 'grant.status'})['data']['grant'] is not None, 'Ordinary takeover retains consent')
            try:
                owner.call({'operation': 'snapshot', 'scope': 'system'})
            except Exception as refusal:
                check(getattr(refusal, 'code', None) == 'control_interrupted', 'Interrupted action is refused without replay')
            else:
                raise AssertionError('Interrupted action unexpectedly dispatched')
            ui('Pause access')
            wait(lambda: 'physical_activity' not in owner.status()['blockingReasons'], 'real physical quiet timer', 45)
            check('manual' in owner.status()['blockingReasons'], 'Quiet does not clear real operator Pause')
            ui('Resume access')
            owner.wait()
            check(owner.status()['sessionId'] != original_session, 'Operator Resume accepts fresh ordinary ownership')
            check(owner.call({'operation': 'snapshot', 'scope': 'system', 'processId': fixture.pid})['accepted'],
                  'Fresh ordinary observation succeeds')
            # Pause/Resume deliberately raised the settings window. Restore
            # the fixture arrangement; operator overlap must remain protected.
            ps('Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes;'
               '$root=[Windows.Automation.AutomationElement]::FromHandle([IntPtr]' + str(operator_hwnd) + ');'
               '$root.GetCurrentPattern([Windows.Automation.WindowPattern]::Pattern).SetWindowVisualState('
               '[Windows.Automation.WindowVisualState]::Minimized)')
            owner.close(); owner = None
        if args.scenario != 'lifecycle':
            unlock(args.scenario, duration=300)
            if args.scenario in ('stop', 'covered', 'activity'):
                windows = owner.call({'operation': 'windows', 'scope': 'system'})
                hwnd = next(w['hwnd'] for w in windows['data']['windows'] if w['processId'] == fixture.pid)
                if args.scenario in ('covered', 'activity'):
                    cover = next(w for w in windows['data']['windows'] if w['title'] == 'Machine Control privacy cover')
                    refused = owner.call({'operation': 'window.state', 'hwnd': cover['hwnd'], 'state': 'closed'})
                    check(not refused['accepted'] and refused.get('errorCode') == 'self_target_refused',
                          'Agent cannot close its independent privacy guardian')
                owner.call({'operation': 'window.state', 'hwnd': hwnd, 'state': 'maximized'})
                snapshot = owner.call({'operation': 'snapshot', 'scope': 'system', 'hwnd': hwnd})
                button = next(e for e in snapshot['data']['elements'] if e['name'] == 'Increment counter')
                bounds = button['bounds']
                report['inputBounds'] = bounds
                report['inputDesktop'] = direct({'operation': 'status'})
                click = owner.call({'operation': 'click', 'x': round(bounds['x'] + bounds['width'] / 2),
                                    'y': round(bounds['y'] + bounds['height'] / 2)})
                report['pointerResult'] = click
                check(click['accepted'], 'Owned pointer delivery accepted')
                wait(lambda: json.loads(marker.read_text())['counter'] == 1, 'independent pointer effect')
                check(click['accepted'] and ready(), 'Injected pointer input preserves guarded ownership')
                key = owner.call({'operation': 'key', 'key': 'space'})
                wait(lambda: json.loads(marker.read_text())['counter'] == 2, 'independent keyboard effect')
                check(key['accepted'] and ready(), 'Injected keyboard input preserves guarded ownership')
                if args.scenario in ('covered', 'activity'):
                    capture = owner.call({'operation': 'screenshot', 'scope': 'system'})
                    report['coveredCapture'] = capture
                    check(capture['accepted'], 'Full-display native capture accepted behind cover')
                    path = quote(capture['data']['targetLocalPath'])
                    colored = ps('Add-Type -AssemblyName System.Drawing; $image=[Drawing.Bitmap]::new('+path+');'
                                 'try{$count=0; for($y=0;$y -lt $image.Height;$y+=10){for($x=0;$x -lt $image.Width;$x+=10){'
                                 '$p=$image.GetPixel($x,$y);if(($p.R+$p.G+$p.B) -gt 30){$count++}}};$count}finally{$image.Dispose()}')
                    check(int(colored) > 100, 'Captured pixels contain underlying apps while cover is opaque')
                    external('verify-cover-' + args.scenario)
                    if args.scenario == 'activity':
                        original_session = owner.status()['sessionId']
                        external('diagnostic-human-covered')
                        wait(lambda: not ready(), 'covered takeover independent relock', 30)
                        external('verify-relock-activity')
                        check(direct({'operation': 'grant.status'})['data']['grant'] is not None,
                              'Covered takeover retains real ordinary consent')
                        owner.wait()
                        check(owner.status()['sessionId'] != original_session,
                              'Locked quiet permits fresh covered ownership without reapproval')
                        check(not ready(), 'Fresh covered ownership does not itself unlock or replay work')
                    owner.close(); owner = None
                else:
                    ui('Stop access')
            else:
                external('verify-cover-' + args.scenario)
                external('crash-' + args.scenario)
            external('verify-relock-' + args.scenario)
            check(not ready(), args.scenario + ': independent guardian relocks after interruption')
            report['passed'] = True
            return
        unlock('completion')
        windows = owner.call({'operation': 'windows', 'scope': 'system'})
        hwnd = next(w['hwnd'] for w in windows['data']['windows'] if w['processId'] == fixture.pid)
        # Pin the deep native route for this boundary fixture. Broad Cua/package
        # qualification remains a separate acceptance campaign.
        observed = owner.call({'operation': 'snapshot', 'scope': 'system', 'hwnd': hwnd})
        report['observationResult'] = observed
        report['ownerAfterUnlock'] = owner.status()
        report['runtimeAfterUnlock'] = direct({'operation': 'status'})
        check(observed['accepted'], 'Owned post-unlock semantic observation')
        reference = next(e['reference'] for e in observed['data']['elements'] if e['name'] == 'Increment counter')
        effect = owner.call({'operation': 'invoke', 'hwnd': hwnd, 'reference': reference})
        check(effect['accepted'] and json.loads(marker.read_text())['counter'] == 1, 'Independent fixture counter confirms the owned effect')
        capture = owner.call({'operation': 'screenshot', 'scope': 'system', 'hwnd': hwnd})
        check(capture['accepted'], 'Target-local capture after guarded unlock')
        owner.close(); owner = None
        external('verify-relock-completion')
        check(not ready(), 'Task completion relocks the existing session')
        unlock('disconnect')
        owner.process.kill(); owner.close(); owner = None
        external('verify-relock-disconnect')
        check(not ready(), 'Owner transport failure independently relocks')
        unlock('expiry', duration=45)
        external('verify-relock-expiry')
        check(not ready(), 'Finite task expiry relocks without a local prompt')
        owner.close(); owner = None
        unlock('pause')
        ui('Pause access')
        external('verify-relock-pause')
        check(not ready(), 'Operator Pause fences and relocks')
        owner.close(); owner = None
        ui('Resume access')
        unlock('stop')
        ui('Stop access')
        external('verify-relock-stop')
        check(not ready(), 'Operator Stop revokes and relocks')
        owner.close(); owner = None
        # Stop deliberately leaves Windows locked. The outside controller owns
        # canonical-credential recovery and helper removal after this actor has
        # saved its report; it must not weaken Stop to recover the testbed.
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        report['errorCode'] = getattr(error, 'code', None)
        raise
    finally:
        if owner:
            owner.close()
        if fixture and fixture.poll() is None:
            fixture.terminate(); fixture.wait(timeout=10)
        if app and app.poll() is None:
            app.terminate(); app.wait(timeout=10)
        save()


if __name__ == '__main__':
    main()

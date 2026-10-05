"""Interactive VM actor for the real desktop UI and protected product route.

The controller must hold the exact VM claim. A separate appliance actor handles
only the install/remove UAC prompts; all application effects use the desktop
owner channel. Evidence and the actor mailbox stay private.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if len(sys.argv) > 2 and sys.argv[1] == '--channel':
    raise SystemExit(subprocess.call([sys.argv[2], 'channel', '--profile', 'user', '--instance', 'desktop', '--session-id', sys.argv[3]]))

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
from control_session import ControlSession
from machine_control import ClientError


def ps(script):
    encoded = base64.b64encode(script.encode('utf-16-le')).decode()
    result = subprocess.run(['pwsh.exe', '-NoProfile', '-EncodedCommand', encoded], capture_output=True, text=True, timeout=40)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--mailbox', type=Path, required=True)
    args = parser.parse_args()
    exe = args.install / 'runtime/machine-control-windows.exe'
    app_exe = args.install / 'machine-control.exe'
    session_id = ps('[Diagnostics.Process]::GetCurrentProcess().SessionId')
    report = {'schema': 'machine-control-desktop-uac-live/v0', 'passed': False, 'checks': [], 'routes': [],
              'runtimeSha256': hashlib.sha256(exe.read_bytes()).hexdigest()}
    args.mailbox.mkdir(parents=True, exist_ok=True)
    app = None
    owner = None
    fixture = None
    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        report['checks'].append(label)
        print(label, flush=True)
    def save():
        temporary = args.evidence.with_suffix('.pending')
        temporary.write_text(json.dumps(report, indent=2))
        temporary.replace(args.evidence)
    def direct(request):
        result = subprocess.run([str(exe), 'call', '--profile', 'user', '--instance', 'desktop', '--session-id', session_id],
                                input=json.dumps(request), text=True, capture_output=True, timeout=40)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return json.loads(result.stdout)
    def accepted(request):
        value = owner.call(request)
        if not value['accepted']:
            raise AssertionError(json.dumps(value))
        if value.get('actualRoute') not in report['routes']:
            report['routes'].append(value.get('actualRoute'))
        return value
    def ui(name, toggle=False):
        script = 'Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes; '
        script += '$deadline=[DateTime]::UtcNow.AddSeconds(15); do {'
        script += '$root=[Windows.Automation.AutomationElement]::RootElement.FindFirst([Windows.Automation.TreeScope]::Children,[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ProcessIdProperty,'+str(app.pid)+'));'
        script += 'if($root){$item=$root.FindFirst([Windows.Automation.TreeScope]::Descendants,[Windows.Automation.AndCondition]::new([Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::NameProperty,'+quote(name)+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::ControlTypeProperty,[Windows.Automation.ControlType]::'+('CheckBox' if toggle else 'Button')+'),[Windows.Automation.PropertyCondition]::new([Windows.Automation.AutomationElement]::IsOffscreenProperty,$false)));if($item){break}};Start-Sleep -Milliseconds 100}while([DateTime]::UtcNow -lt $deadline); if(!$item){throw '+quote('UI unavailable: '+name)+'};'
        script += '$item.GetCurrentPattern([Windows.Automation.'+('TogglePattern' if toggle else 'InvokePattern')+']::Pattern).'+('Toggle' if toggle else 'Invoke')+'()'
        ps(script)
        time.sleep(.5)
    def external(phase):
        temporary = args.mailbox / 'phase.pending'
        temporary.write_text(json.dumps({'phase': phase}))
        temporary.replace(args.mailbox / 'phase.json')
        reply = args.mailbox / (phase + '.done')
        deadline = time.monotonic() + 90
        while not reply.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError('Independent setup actor: '+phase)
            time.sleep(.2)
        time.sleep(2)
    def wait_ready():
        # Setup completes asynchronously after consent and copies the protected
        # payload before restarting the companion. Cold VM disks need a bounded
        # allowance for that completion, rather than a fixed post-consent sleep.
        deadline = time.monotonic() + 90
        last = None
        while True:
            try:
                last = direct({'operation': 'status'})
                if last.get('data', {}).get('ready'):
                    return
            except Exception as error:
                last = str(error)
            if time.monotonic() >= deadline:
                raise TimeoutError('Desktop resident readiness: '+json.dumps(last))
            time.sleep(.3)
    def new_owner(scopes=('observe', 'control')):
        value = ControlSession({'command': [sys.executable, str(Path(__file__).resolve()), '--channel', str(exe), session_id]},
                               reason='Desktop UAC fixture acceptance', scopes=scopes, wait=60, duration=300)
        value.wait()
        return value
    def uac_policy():
        return json.loads(ps("Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' | Select-Object EnableLUA,PromptOnSecureDesktop,ConsentPromptBehaviorAdmin | ConvertTo-Json -Compress"))
    try:
        policy = uac_policy()
        check(policy['EnableLUA'] == 1 and policy['PromptOnSecureDesktop'] == 1, 'UAC and secure desktop remain enabled')
        os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--force-renderer-accessibility'
        app = subprocess.Popen([str(app_exe), '--gui'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_ready()
        check(not direct({'operation': 'snapshot'})['accepted'], 'Desktop starts off')
        ui('Permissions')
        ui('Install helper…')
        external('setup-cancel')
        check(ps('(Test-Path '+quote(Path(os.environ['ProgramFiles']) / 'MachineControlDesktopUac')+')') == 'False', 'Cancelled setup installs no helper')
        ui('Install helper…')
        external('setup-approve')
        wait_ready()
        ui('Settings')
        helper = direct({'operation': 'capabilities'})['data']['protectedDesktop']
        check(helper['installed'], 'Administrator-owned helper is running')
        check(not helper['enabled'], 'Installation leaves UAC control off')
        # A different Medium executable cannot impersonate the protected
        # resident, even though it can connect to the service's public pipe.
        denied = ps("$p=[IO.Pipes.NamedPipeClientStream]::new('.', 'machine-control-desktop-uac', [IO.Pipes.PipeDirection]::InOut); try {$p.Connect(2000); $w=[IO.StreamWriter]::new($p);$w.AutoFlush=$true;$w.WriteLine('{}');$r=[IO.StreamReader]::new($p); if($null -ne $r.ReadLine()){throw 'Unexpected helper response'}; 'refused'} finally {$p.Dispose()}")
        check(denied == 'refused', 'Untrusted Medium helper caller refused')
        ui('Allow UAC and elevated app control', toggle=True)
        ui('Access')
        ui('Enable access')
        check(direct({'operation': 'uac.respond', 'state': 'approve'})['errorCode'] == 'control_session_required', 'Idle grant cannot approve UAC')
        owner = new_owner(('observe',))
        try:
            owner.call({'operation': 'uac.respond', 'state': 'approve'})
            raise AssertionError('Observe owner gained UAC control')
        except ClientError as error:
            check(error.code == 'operation_not_permitted_by_control_channel', 'Observe-only owner cannot approve UAC')
        owner.close(); owner = None
        marker = Path(os.environ['LOCALAPPDATA']) / 'MachineControl/conformance/elevation-approved.json'
        marker.unlink(missing_ok=True)
        # Prepare the independent fixture before acquiring ownership. A cold
        # self-contained process image may take longer than the owner watchdog
        # to start on this VM; that existing app.launch gate is a separate concern.
        fixture = subprocess.Popen([str(args.install / 'runtime/fixtures/machine-control-medium-fixture.exe')])
        time.sleep(5)
        owner = new_owner()
        credentials = owner.call({'operation': 'snapshot', 'credentialKind': 'password'})
        check(not credentials['accepted'] and credentials['errorCode'] == 'profile_refused', 'Credential transport refused before protected dispatch')
        launch = accepted({'operation': 'windows', 'scope': 'system', 'query': 'Machine Control Medium Fixture'})
        medium = next(w for w in launch['data']['windows'] if w['title'] == 'Machine Control Medium Fixture' and w['processId'] == fixture.pid)
        medium_hwnd = medium['hwnd']
        snapshot = accepted({'operation': 'snapshot', 'hwnd': medium_hwnd})
        old = next(e['reference'] for e in snapshot['data']['elements'] if e['name'] == 'Increment counter')
        def elevation():
            accepted({'operation': 'invoke', 'hwnd': medium_hwnd, 'query': 'Request elevation'})
            deadline = time.monotonic()+20
            while True:
                value = owner.call({'operation': 'snapshot', 'scope': 'system', 'maxDepth': 12, 'maxElements': 150})
                if value['accepted'] and value.get('desktop') == 'Winlogon':
                    return value
                if time.monotonic() >= deadline:
                    raise AssertionError('UAC consent did not become observable: '+json.dumps(value))
                time.sleep(.2)
        elevation()
        capture = accepted({'operation': 'screenshot'})
        image = Path(capture['data']['targetLocalPath'])
        check(image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(image.read_bytes()).hexdigest() == capture['data']['sha256'], 'Desktop secure capture and artifact hash')
        refused = owner.call({'operation': 'key', 'key': 'enter'})
        check(not refused['accepted'] and refused['errorCode'] == 'secure_desktop_operation_refused', 'Generic secure-desktop input refused')
        cancel = accepted({'operation': 'uac.respond', 'state': 'cancel'})
        check(cancel['effect'] == 'confirmed', 'Typed UAC cancellation returns to Default')
        check(not marker.exists(), 'Cancellation has no elevated application effect')
        stale = owner.call({'operation': 'invoke', 'hwnd': medium_hwnd, 'reference': old})
        check(not stale['accepted'] and stale['errorCode'] == 'stale_or_unknown_reference', 'Desktop transition invalidates semantic reference')
        elevation()
        approve = accepted({'operation': 'uac.respond', 'state': 'approve'})
        check(approve['effect'] == 'confirmed', 'Typed UAC approval returns to Default')
        deadline = time.monotonic()+15
        while not marker.exists():
            if time.monotonic() >= deadline:
                raise AssertionError('Independent elevated fixture marker absent')
            time.sleep(.2)
        elevated_pid = json.loads(marker.read_text())['processId']
        deadline = time.monotonic()+30
        while True:
            inventory = accepted({'operation': 'windows', 'scope': 'system', 'query': 'Machine Control Elevated Fixture'})
            elevated = next((w for w in inventory['data']['windows'] if w['title'] == 'Machine Control Elevated Fixture' and w['processId'] == elevated_pid), None)
            if elevated:
                break
            if time.monotonic() >= deadline:
                raise AssertionError('Independent elevated fixture window absent')
            time.sleep(.2)
        snap = accepted({'operation': 'snapshot', 'hwnd': elevated['hwnd'], 'maxDepth': 8})
        button = next(e for e in snap['data']['elements'] if e['name'] == 'Increment elevated counter')
        accepted({'operation': 'invoke', 'hwnd': elevated['hwnd'], 'reference': button['reference']})
        check('counter=1' in marker.read_text(), 'Independent elevated UI counter effect')
        owner.close(); owner = None
        check(direct({'operation': 'invoke', 'hwnd': elevated['hwnd'], 'query': 'Increment elevated counter'})['errorCode'] == 'control_session_required'
              and 'counter=2' not in marker.read_text(), 'Owner disconnection fences elevated effects')
        owner = new_owner()
        ui('Pause access')
        try:
            owner._rpc({'operation': 'control.dispatch', 'sessionId': owner.view['sessionId'], 'resourceGenerations': owner.view['resourceGenerations'], 'request': {'operation': 'invoke', 'hwnd': elevated['hwnd'], 'query': 'Increment elevated counter'}})
            raise AssertionError('Paused owner gained elevated control')
        except ClientError as error:
            check(error.code == 'stale_control_session' and 'counter=2' not in marker.read_text(), 'Pause fences elevated effects')
        owner.close(); owner = None
        ui('Resume access')
        owner = new_owner()
        accepted({'operation': 'window.state', 'hwnd': elevated['hwnd'], 'state': 'closed'})
        accepted({'operation': 'window.state', 'hwnd': medium_hwnd, 'state': 'closed'})
        ui('Stop access')
        check(not direct({'operation': 'snapshot'})['accepted'], 'Stop revokes protected observation')
        owner.close(); owner = None
        ui('Permissions')
        ui('Remove helper…')
        external('remove-approve')
        wait_ready()
        check(not direct({'operation': 'capabilities'})['data']['protectedDesktop']['installed'], 'Helper removal restores ordinary desktop')
        check(uac_policy() == policy, 'Installation and control preserve UAC policy')
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if owner:
            owner.close()
        if app and app.poll() is None:
            try:
                ui('Access'); ui('Stop access')
            except Exception:
                pass
            app.terminate(); app.wait(timeout=10)
        if fixture and fixture.poll() is None:
            fixture.terminate(); fixture.wait(timeout=10)
        save()


if __name__ == '__main__':
    main()

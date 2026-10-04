"""Claimed VM acceptance for a staged Windows desktop product.

Runs from the controller. The separate UI actor is an explicitly authorized
operator fixture, never an agent-facing approval endpoint. Raw evidence and
resolved inventory stay in the caller's private output directory.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'client'))
import machine_control as mc
from control_session import ControlSession


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


class SilentSession(ControlSession):
    """Test owner that deliberately stops heartbeats; no resident test hook."""
    def _keepalive(self):
        pass


class Stream:
    def __init__(self, command, log):
        self.log = log.open('wb')
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=self.log, text=True)
        self.replies = queue.Queue()
        def read():
            for line in self.process.stdout:
                self.replies.put(line)
            self.replies.put(None)
        threading.Thread(target=read, daemon=True).start()

    def call(self, request):
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        reply = self.replies.get(timeout=90)
        if reply is None:
            raise RuntimeError('Stream closed without a result; inspect private stderr')
        return json.loads(reply)

    def close(self, kill=False):
        if self.process.poll() is None:
            if kill:
                self.process.kill()
            else:
                try: self.process.stdin.close()
                except BrokenPipeError: pass
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait()
                raise RuntimeError('Stream did not exit promptly')
        if not self.process.stdin.closed:
            try: self.process.stdin.close()
            except BrokenPipeError: pass
        self.process.stdout.close()
        self.log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--claim', required=True, help='Already acquired exact VM claim; caller renews/releases')
    parser.add_argument('--registry')
    parser.add_argument('--install', required=True, help='Staged guest app directory')
    parser.add_argument('--guest-root', required=True, help='Owned guest fixture directory')
    parser.add_argument('--session', required=True, type=int)
    parser.add_argument('--chrome', required=True, help='Separate Chrome for Testing executable')
    parser.add_argument('--fixture', required=True, help='Guest native counter fixture executable')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--runtime-revision', required=True, help='Exact source revision used for the staged runtime build')
    parser.add_argument('--runtime-sha256', required=True, help='Expected staged native executable digest')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(args.output, 0o700)
    targets, _ = mc.load_registry(args.registry)
    _, base = mc.select_target(targets, args.target)
    if base['platform'] != 'windows' or base.get('claimPolicy') != 'required':
        raise RuntimeError('Use a dedicated claimed Windows VM')
    base = dict(base, _claimId=args.claim, environment={**base.get('environment', {}),
        'MACHINE_CONTROL_CLAIM_POLICY':'required', 'MACHINE_CONTROL_CLAIM_ID':args.claim})
    mc.require_selected_claim(base)
    target = dict(base, environment={**base['environment'], 'WINVM_RESIDENT_PROFILE':'desktop',
        'WINVM_USER_SESSION_ID':str(args.session), 'WINVM_DESKTOP_INSTALL_DIR':args.install})
    registry = args.output / 'targets.json'
    registry.write_text(json.dumps({'schema':mc.TARGET_SCHEMA, 'targets':{args.target:{
        k:v for k,v in target.items() if not k.startswith('_')}}}))
    registry.chmod(0o600)
    command = [sys.executable, str(ROOT/'bin/machine-control'), '--registry', str(registry),
               '--target', args.target, '--claim', args.claim]
    mailbox = args.guest_root + '\\run-' + uuid.uuid4().hex
    report = {'schema':'machine-control-owner-acceptance/v0', 'passed':False, 'checks':[],
              'routes':[], 'runtimeRevision':args.runtime_revision,
              'runnerRevision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    fixture_pid = None
    actor_started = False
    sessions = []
    streams = []

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)
        print(name, flush=True)

    def admin(script):
        mc.require_selected_claim(base)
        completed, _, _ = mc.run_adapter(base, ['ps', script])
        return completed.stdout.strip().lstrip('\ufeff')

    def remote_json(path):
        text = admin('if(Test-Path -LiteralPath '+quote(path)+'){Get-Content -LiteralPath '+quote(path)+' -Raw}')
        return json.loads(text) if text else None

    def upload(local, remote):
        # Binary stdin avoids command-line limits and preserves exact source.
        code = 'import sys,pathlib; p=pathlib.Path('+repr(remote)+'); p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(sys.stdin.buffer.read())'
        mc.require_selected_claim(base)
        with local.open('rb') as source:
            subprocess.run([*mc.resolved_adapter_command(base), 'ssh', 'python.exe -c "'+code+'"'],
                stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env={**os.environ, **base['environment']}, check=True, timeout=120)
        digest = admin('(Get-FileHash -LiteralPath '+quote(remote)+' -Algorithm SHA256).Hash').lower()
        check(digest == hashlib.sha256(local.read_bytes()).hexdigest(), 'Exact uploaded '+local.name)

    def actor(action):
        identifier = uuid.uuid4().hex
        data = json.dumps({'id':identifier,'action':action})
        admin('[IO.File]::WriteAllText('+quote(mailbox+'\\request.tmp')+','+quote(data)+'); Move-Item '+
              quote(mailbox+'\\request.tmp')+' '+quote(mailbox+'\\request.json')+' -Force')
        return wait_reply(identifier)

    def wait_reply(identifier):
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            reply = remote_json(mailbox+'\\reply.json')
            if reply and reply['id'] == identifier:
                if not reply['ok']:
                    raise AssertionError('Operator actor refused: '+str(reply.get('error')))
                check(True, 'Operator UI ready' if identifier == 'ready' else 'Operator command completed')
                return reply
            time.sleep(.2)
        raise TimeoutError('Operator actor response timeout')

    def direct(request):
        return mc.run_adapter(target, ['control', json.dumps(request)], accept_json_failure=True)[1]

    def cli(*arguments):
        result = subprocess.run([*command,*arguments], capture_output=True, text=True, timeout=90)
        value = json.loads(result.stdout)
        return value

    def session(cls=ControlSession):
        value = cls(target, reason='Native owner acceptance', scopes=['observe','control','browser','devtools'], wait=60, duration=300)
        sessions.append(value)
        return value

    def accepted(value):
        if not value['accepted']:
            raise AssertionError('Operation refused: '+json.dumps(value))
        route = value.get('actualRoute')
        if route and route not in report['routes']: report['routes'].append(route)
        return value

    def invoke(call):
        snap = accepted(call({'operation':'snapshot','hwnd':hwnd,'maxDepth':8,'maxElements':100}))
        button = next(e for e in snap['data']['elements'] if e.get('name') == 'Increment counter')
        action = accepted(call({'operation':'invoke','hwnd':hwnd,'reference':button['reference']}))
        report['nativeActionSemantics'] = {key:action.get(key) for key in ('accepted','delivery','effect','uncertainty','retrySafety')}
        after = accepted(call({'operation':'snapshot','hwnd':hwnd,'maxDepth':8,'maxElements':100}))
        return next(e['reference'] for e in after['data']['elements'] if e.get('name') == 'Increment counter')

    def browser_snapshot(call, tab):
        # Tab load completion can precede the accessibility tree update.
        # Poll observations only; never repeat navigation or an input action.
        deadline = time.monotonic()+15
        observations = 0
        while True:
            snap = accepted(call({'operation':'browser.snapshot','tabId':tab,'interactiveOnly':True}))
            observations += 1
            if any(e.get('name') == 'Increment browser counter' for e in snap['data']['elements']):
                report.setdefault('browserReadinessObservations', []).append(observations)
                return snap
            if time.monotonic() >= deadline:
                report['unreadyBrowserSnapshot'] = snap
                raise AssertionError('Loaded fixture tab did not expose its expected accessible control')
            time.sleep(.2)

    def counter(expected):
        value = json.loads(admin('Get-Content (Join-Path $env:LOCALAPPDATA "MachineControl\\conformance\\counter.json") -Raw'))
        check(value['processId'] == fixture_pid and value['counter'] == expected, 'Independent native counter '+str(expected))

    try:
        doctor = mc.run_adapter(base, ['doctor','--json'], accept_json_failure=True)[1]
        (args.output/'doctor.json').write_text(json.dumps(doctor,indent=2))
        check(doctor['ready'], 'Dedicated VM doctor ready')
        runtime_hash = admin('(Get-FileHash -LiteralPath '+quote(args.install+'\\runtime\\machine-control-windows.exe')+' -Algorithm SHA256).Hash').lower()
        check(runtime_hash == args.runtime_sha256.lower(), 'Exact candidate runtime digest')
        report['runtimeSha256'] = runtime_hash
        report['candidate'] = json.loads(admin('$exe='+quote(args.install+'\\machine-control.exe')+'; '
            '$browser='+quote(args.chrome)+'; '
            '[pscustomobject]@{operatorVersion=(Get-Item $exe).VersionInfo.ProductVersion; '
            'operatorSha256=(Get-FileHash $exe).Hash.ToLowerInvariant(); '
            'operatorSignature=(Get-AuthenticodeSignature $exe).Status.ToString(); '
            'guestArchitecture=$env:PROCESSOR_ARCHITECTURE; '
            'browserVersion=(Get-Item $browser).VersionInfo.ProductVersion}|ConvertTo-Json'))
        actor_path = args.guest_root+'\\owner-session-actor.ps1'
        upload(Path(__file__).with_name('owner-session-actor.ps1'), actor_path)
        browser_fixture = args.guest_root+'\\browser-fixture.py'
        upload(Path(__file__).with_name('browser-fixture.py'), browser_fixture)
        launch_request = {'operation':'app.launch',
            'executablePath':r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            'arguments':subprocess.list2cmdline(['-NoProfile','-STA','-ExecutionPolicy','Bypass',
                '-File',actor_path,'-Install',args.install,'-Mailbox',mailbox,
                '-Chrome',args.chrome,'-BrowserFixture',browser_fixture])}
        launched = mc.run_adapter(base, ['control',json.dumps(launch_request)], accept_json_failure=True)[1]
        check(launched['accepted'], 'Appliance launches independent interactive UI actor')
        (args.output/'actor-launch.json').write_text(json.dumps(launched))
        actor_started = True
        wait_reply('ready')
        status = accepted(direct({'operation':'status'}))
        check(status['data'].get('controlSessionRequired') is True, 'Candidate requires owner sessions')
        report['assembly'] = 'staged installed operator with source-built runtime; not signed release acceptance'
        actor('arm')
        denied = direct({'operation':'snapshot'})
        check(not denied['accepted'] and denied.get('errorCode') == 'control_session_required', 'Idle grant refuses unowned native call')
        check(not direct({'operation':'snapshot','controlOwnership':{'owner':'forged'}})['accepted'], 'JSON cannot forge owner')
        a = session(); check(a.view['state'] == 'announcing', 'Real native notice precedes admission'); a.wait()
        launch = accepted(a.call({'operation':'app.launch','executablePath':args.fixture}))
        fixture_pid = launch['data']['processId']
        hwnd = next(w['hwnd'] for w in launch['data']['windows'] if w['visible'] and w['title']=='Machine Control Medium Fixture')
        old_reference = invoke(a.call); counter(1)
        b = session()
        check(b.status()['state']=='waiting_for_resource', 'Second connection waits')
        try:
            b._rpc({'operation':'control.dispatch','sessionId':a.view['sessionId'],
                    'resourceGenerations':a.view['resourceGenerations'], 'request':{'operation':'invoke','reference':old_reference}})
            raise AssertionError('Borrowed owner unexpectedly dispatched')
        except mc.ClientError:
            check(True, 'Other connection cannot borrow active fence')
        a.close(); b.wait()
        stale = b.call({'operation':'invoke','reference':old_reference})
        check(not stale['accepted'], 'Old owner reference rejected after handoff'); counter(1)
        invoke(b.call); counter(2)
        actor('pause')
        try:
            b.call({'operation':'invoke','reference':old_reference})
            raise AssertionError('Paused owner dispatched')
        except mc.ClientError:
            check(True, 'Pause interrupts existing owner')
        counter(2); b.close(); actor('resume')
        # Silent protocol owner expires even though its transport remains open.
        silent = session(SilentSession); silent.wait()
        fence = dict(silent.view)
        time.sleep(6)
        check(silent.status()['state']=='ended', 'Resident heartbeat expiry ends live transport ownership')
        try:
            silent._rpc({'operation':'control.dispatch','sessionId':fence['sessionId'],
                'resourceGenerations':fence['resourceGenerations'],'request':{'operation':'invoke','reference':old_reference}})
            raise AssertionError('Expired owner dispatched')
        except mc.ClientError:
            check(True, 'Expired owner refused before effect')
        silent.close(); counter(2)
        stream = Stream([*command,'control','stream','--reason','Native retained CLI acceptance'], args.output/'stream.stderr')
        streams.append(stream)
        invoke(stream.call); counter(3)
        contender = session()
        contention = contender.status()
        if contention['state'] != 'waiting_for_resource':
            report['unexpectedContention'] = contention
            report['streamAfterLostOwnership'] = stream.call({'operation':'snapshot','hwnd':hwnd})
            report['grantAfterLostOwnership'] = direct({'operation':'grant.status'})
        check(contention['state']=='waiting_for_resource','SDK waits behind CLI owner')
        stream.close(kill=True); contender.wait()
        invoke(contender.call); counter(4); contender.close()
        short = accepted(cli('desktop','call',json.dumps({'operation':'snapshot','hwnd':hwnd})))
        check(short['operation']=='snapshot', 'One-shot CLI negotiates native ownership')
        browser = actor('browser')
        c = session(); c.wait()
        deadline=time.monotonic()+30
        while True:
            tabs = c.call({'operation':'browser.tabs'})
            if tabs['accepted']: break
            if time.monotonic()>deadline: accepted(tabs)
            time.sleep(.3)
        page=accepted(c.call({'operation':'browser.navigate','url':browser['url'],'newTab':True}))
        tab=page['data']['tab']['tabId']
        accepted(c.call({'operation':'browser.wait','tabId':tab}))
        snap=browser_snapshot(c.call, tab)
        ref=next(e['reference'] for e in snap['data']['elements'] if e.get('name')=='Increment browser counter')
        accepted(c.call({'operation':'browser.click','reference':ref}))
        effect=remote_json(mailbox+'\\browser-effect.json')
        check(effect['counter']==1,'Independent browser counter effect')
        denied=direct({'operation':'browser.click','reference':ref})
        check(not denied['accepted'] and denied.get('errorCode')=='control_session_required','Direct browser mutation cannot bypass owner')
        actor('stop')
        try:
            c.call({'operation':'browser.click','reference':ref})
            raise AssertionError('Stopped owner dispatched')
        except mc.ClientError:
            check(True,'Operator Stop revokes active browser owner')
        check(remote_json(mailbox+'\\browser-effect.json')['counter']==1,'Stop left browser effect unchanged')
        c.close()
        actor('arm')
        accepted(cli('browser','tabs'))
        check(True, 'One-shot browser CLI negotiates ownership')
        browser_stream = Stream([*command,'control','stream','--reason','Browser retained CLI acceptance',
                                 '--scope','browser'], args.output/'browser-stream.stderr')
        streams.append(browser_stream)
        snap=browser_snapshot(browser_stream.call, tab)
        ref=next(e['reference'] for e in snap['data']['elements'] if e.get('name')=='Increment browser counter')
        accepted(browser_stream.call({'operation':'browser.click','reference':ref}))
        check(remote_json(mailbox+'\\browser-effect.json')['counter']==2,'Independent retained browser CLI effect')
        browser_stream.close()
        actor('stop')
        report['passed']=True
    except BaseException as error:
        report['error']=type(error).__name__+': '+str(error)
        raise
    finally:
        cleanup=[]
        for value in streams:
            try: value.close()
            except Exception as error: cleanup.append(str(error))
        for value in sessions:
            try: value.close()
            except Exception as error: cleanup.append(str(error))
        if fixture_pid:
            try: admin('Stop-Process -Id '+str(int(fixture_pid))+' -ErrorAction SilentlyContinue')
            except Exception as error: cleanup.append(str(error))
        if actor_started:
            try:
                actor('quit')
                deadline=time.monotonic()+25
                while not remote_json(mailbox+'\\closed.json'):
                    if time.monotonic()>deadline: raise TimeoutError('Actor cleanup timeout')
                    time.sleep(.2)
            except Exception as error: cleanup.append(str(error))
        report['cleanupErrors']=cleanup
        report['passed']=report['passed'] and not cleanup
        (args.output/'result.json').write_text(json.dumps(report,indent=2))
        registry.unlink(missing_ok=True)
        if cleanup: print('Cleanup needs inspection: '+str(cleanup),file=sys.stderr)
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

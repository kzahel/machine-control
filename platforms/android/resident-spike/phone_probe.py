"""Deterministic on-phone interpreter acceptance. No ADB or provider inference."""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session import AndroidTransport, Worker


def run() -> None:
    # Runtime witness is private. This proves ordinary app execution, not shell UID.
    domain = Path('/proc/self/attr/current').read_text().strip('\x00\n')
    # PRoot -0 intentionally reports getuid()==0; /proc exposes the kernel UID.
    status = Path('/proc/self/status').read_text()
    uid = int(next(line for line in status.splitlines() if line.startswith('Uid:')).split()[1])
    assert uid >= 10000 and domain.startswith('u:r:untrusted_app'), domain
    if Path('inference.json').exists():
        from provider_probe import run as providers
        providers()
    nonce = Path('challenge.txt').read_text().strip()
    worker = Worker({'receipt': str(Path('bridge.json').resolve())}, timeout=15,
                    command=[sys.executable, str(Path('session.py').resolve()), '--worker'])
    reports = []
    def code(source):
        reply = worker.request({'code': source})
        reports.append(reply)
        assert not reply['isError'], reply
        return reply
    try:
        code("app = mc.app('MC Android Fixture'); remembered = 41")
        # A separate snippet must retain both application handle and variables.
        code("assert remembered + 1 == 42; app.tree(); field = next(n for n,e in app.elements.items() if e['role'] == 'textfield')")
        code(f"app.set_value(field, {nonce!r})")
        code("apply = next(n for n,e in app.elements.items() if e['label'].casefold() == 'apply'); app.press(apply)")
        # The independent host reads the fixture's private result file later.
        code(f"app.tree(); assert any(e['label'] == 'Result: ' + {nonce!r} for e in app.elements.values())")
        captured = code("shot = app.screenshot()")
        image = next(c for c in captured['content'] if c['type'] == 'image')
        import base64
        png = base64.b64decode(image['data'])
        assert png.startswith(b'\x89PNG\r\n\x1a\n')
        Path('capture.png').write_bytes(png)
        # Replace the input with an identical label/resource ID. Send the old
        # opaque native reference directly, bypassing client-side stale checks.
        code("app.tree(); old = next(e['reference'] for e in app.elements.values() if e['role'] == 'textfield')")
        Path('await-replace').write_text('ready')
        deadline = time.monotonic()+15
        while not Path('replaced-by-controller').exists():
            assert time.monotonic() < deadline, 'Controller did not replace input'
            time.sleep(.05)
        code("reply = mc.transport.call({'operation':'action','reference':old,'action':'set_value','text':'WRONG'}); assert reply['accepted'] is False and reply['errorCode'] == 'stale_reference'")
        worker.close()
        time.sleep(.1)  # Let socket EOF release the one native owner.
        # Wrong credentials are rejected before any operation.
        receipt = json.loads(Path('bridge.json').read_text())
        receipt['token'] = 'wrong'
        bad = Path('wrong-grant.json'); bad.write_text(json.dumps(receipt)); bad.chmod(0o600)
        try:
            AndroidTransport(bad)
            raise AssertionError('Wrong grant accepted')
        except Exception as error:
            assert getattr(error, 'code', '') == 'approval_denied', type(error).__name__
        # Explicit re-admission after refusal; no automatic replay.
        fresh = AndroidTransport(Path('bridge.json'))
        try:
            scope = fresh.call({'operation':'snapshot','target':'com.android.settings'})
            assert scope['accepted'] is False and scope['errorCode'] == 'unsupported_scope'
        finally:
            fresh.close()
        time.sleep(.1)
        # Native operator controls cannot be used to renew the agent's grant.
        operator = AndroidTransport(Path('bridge.json'))
        try:
            snapshot = operator.call({'operation':'snapshot'})
            arm = next(e['reference'] for e in snapshot['data']['elements'] if e['label'].casefold().startswith('arm bridge'))
            denied = operator.call({'operation':'action','reference':arm,'action':'press'})
            assert denied['errorCode'] == 'unsupported_action'
        finally:
            operator.close()
        time.sleep(.1)
        waiting = AndroidTransport(Path('bridge.json'))
        try:
            Path('await-revoke').write_text('ready')
            deadline = time.monotonic() + 15
            while not Path('revoked-by-controller').exists():
                assert time.monotonic() < deadline, 'Controller did not revoke'
                time.sleep(.05)
            try:
                waiting.call({'operation':'snapshot'})
                raise AssertionError('Revoked connection still active')
            except Exception as error:
                assert getattr(error,'code','') == 'bridge_lost', type(error).__name__
            try:
                AndroidTransport(Path('bridge.json'))
                raise AssertionError('Revoked grant was re-admitted')
            except Exception as error:
                assert getattr(error,'code','') == 'approval_denied', type(error).__name__
        finally:
            waiting.close()
        Path('phone-witness.json').write_text(json.dumps({'appUid':uid,'guestReportedUid':os.getuid(),'domain':domain,
            'persistentSnippets':len(reports),'semanticTextAndClick':True,'pngCapture':True,
            'sameLabelReplacementRefused':True,'wrongGrantRefused':True,'outsideScopeRefused':True,
            'operatorRearmRefused':True,'liveRevocationClosedOwner':True,'revokedGrantRefused':True,
            'adbInOperationPath':False},indent=2)+'\n')
        # Keep text reports without embedding the PNG a second time.
        for report in reports:
            report['content'] = [c for c in report['content'] if c['type'] != 'image']
        Path('python-snippets.json').write_text(json.dumps(reports,indent=2)+'\n')
    finally:
        worker.close()


if __name__ == '__main__':
    run()

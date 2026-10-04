#!/usr/bin/env python3
"""Focused installed lifetime acceptance in a claimed GNOME test appliance.

The independent AT-SPI actor uses the actual operator UI. Product requests
use its ordinary socket; an independent GTK fixture records the effect.
Run through the graphical systemd user manager to inherit its session context.
Caller owns installation, guest claim, and source/package authentication.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--app', type=Path, required=True)
p.add_argument('--runtime', type=Path, required=True)
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--revision', required=True)
a = p.parse_args()
sys.path.insert(0, str(a.runtime))
import linuxui
from gi.repository import Atspi, GLib

endpoint = Path(os.environ['XDG_RUNTIME_DIR']) / 'machine-control-desktop/desktop.sock'
checks = []
app = fixture = None
result = {'passed': False, 'checks': checks}
log = a.output.with_suffix('.log').open('w')


def check(label, value):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def poll(fn):
    end = time.monotonic() + 25
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except (OSError, linuxui.UIError):
            pass
        time.sleep(.2)
    raise AssertionError('Timed out waiting for native effect')


def call(operation, **params):
    with socket.socket(socket.AF_UNIX) as client:
        client.settimeout(20)
        client.connect(str(endpoint))
        client.sendall((json.dumps({'operation': operation, **params}) + '\n').encode())
        return json.loads(client.makefile().readline())


def nodes():
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)
    root = linuxui.choose_application(linuxui.desktop(), 'machine-control')
    root.clear_cache()
    return list(linuxui.walk(root, 30, 2000))


def widget(label, role=None):
    matches = [n for n, i in nodes() if i['name'] == label and 'showing' in i['states']
               and (role is None or i['role'] == role)]
    return matches[0] if len(matches) == 1 else None


def press(label, role=None, action=0):
    node = poll(lambda: widget(label, role))
    check('Native UI ' + label, node.do_action(action))
    time.sleep(.3)


try:
    check('No predecessor product', not endpoint.exists())
    app = subprocess.Popen([str(a.app)], stdout=log, stderr=log, start_new_session=True)
    state = poll(lambda: call('status'))
    check('Exact installed source', state['data']['sourceRevision'] == a.revision)
    check('Supported session ready', state['data']['ready'])
    check('Starts off', state['data']['grant'] is None)
    press('Access duration')
    # GTK exposes both the HTML option and the open native popup row.
    # Activate the visible popup row rather than an ambiguous duplicate.
    press('Until I turn it off', role='table cell', action=2)
    press('Enable access')
    grant = poll(lambda: call('status')['data']['grant'])
    check('Explicit indefinite lifetime', grant['lifetime'] == 'until_stopped')
    check('No countdown', grant['remainingSeconds'] is None)
    check('Visible indefinite status', poll(
        lambda: any('Until you turn it off' in (i['name'] + (
            (linuxui.safe(lambda: Atspi.Text.get_text(n, 0, -1), '') or '') if 'Text' in i['interfaces'] else ''))
            for n, i in nodes() if 'showing' in i['states'])))
    state_path = a.output.with_suffix('.fixture.json')
    state_path.unlink(missing_ok=True)
    source = a.output.with_suffix('.fixture.py')
    source.write_text(a.fixture.read_text().replace(
        'Path.home() / ".cache/linuxvm-testbed/fixture/state.json"',
        'Path(' + repr(str(state_path)) + ')'))
    fixture = subprocess.Popen(['/usr/bin/python3', str(source)], stdout=log, stderr=log)
    poll(state_path.exists)
    snapshot = call('snapshot', target='machine-control-fixture', maxDepth=16)
    check('Indefinite observation', snapshot['accepted'])
    button = next(e for e in snapshot['data']['elements'] if e['label'] == 'Semantic Increment')
    before = json.loads(state_path.read_text())['semanticPresses']
    action = call('action', reference=button['reference'])
    check('Semantic delivery', action['accepted'])
    poll(lambda: json.loads(state_path.read_text())['semanticPresses'] == before + 1)
    check('Independent fixture effect', True)
    press('Stop access')
    poll(lambda: call('status')['data']['grant'] is None)
    check('Stop revokes access', call('snapshot', target='machine-control-fixture')['errorCode'] == 'approval_required')
    check('Fixture survives Stop', fixture.poll() is None)
    result['passed'] = True
except BaseException as error:
    result['error'] = str(error)
    raise
finally:
    if endpoint.exists():
        try:
            call('grant.revoke')
        except Exception:
            pass
    if app and app.poll() is None:
        os.killpg(app.pid, signal.SIGTERM)
        app.wait(10)
    if fixture and fixture.poll() is None:
        fixture.terminate()
        fixture.wait(10)
    a.output.write_text(json.dumps(result, indent=2))
    log.close()

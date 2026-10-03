#!/usr/bin/env python3
"""Drive Activity in an isolated candidate using a claimed appliance observer."""
import argparse
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--target', required=True)
parser.add_argument('--claim', required=True)
parser.add_argument('--candidate-app', required=True)
parser.add_argument('--candidate-socket', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
mc = [str(Path(__file__).resolve().parents[2] / 'bin/machine-control'), '--target', args.target, '--claim', args.claim]
binary = args.candidate_app + '/Contents/MacOS/macui'
checks = []


def call(*argv, allow_failure=False):
    result = subprocess.run(mc + list(argv), capture_output=True, text=True, timeout=60)
    if not allow_failure:
        assert result.returncode == 0, result.stderr
    return result.stdout


def base(request):
    result = json.loads(call('desktop', 'raw', json.dumps(request)))
    assert result['accepted'], result.get('errorCode')
    return result.get('data', {})


def candidate(request):
    return json.loads(call('os', '--', binary, 'request', args.candidate_socket, json.dumps(request), allow_failure=True))


def check(name, value):
    checks.append({'name': name, 'passed': bool(value)})
    if not value:
        raise AssertionError(name)


def snapshot(pid, query=''):
    return base(dict(operation='snapshot', target=str(pid), query=query, projection='compact', maxDepth=35, maxElements=1500))['elements']


def press(pid, label):
    for _ in range(15):
        elements = snapshot(pid, label)
        matches = [e for e in elements if e['label'] == label and e['role'] == 'AXButton']
        if len(matches) == 1:
            base(dict(operation='action', reference=matches[0]['reference'], action='press'))
            return
        time.sleep(.2)
    raise AssertionError('Missing button: ' + label)


try:
    status = candidate({'operation': 'status'})
    check('candidate ready', status['accepted'])
    pid = status['data']['processId']
    check('approval profile', candidate({'operation': 'grant.status'})['data']['policy']['grantMode'] == 'approval')
    reply = candidate({'operation': 'input.text', 'text': 'SENTINEL-audit-payload', 'requestId': 'SENTINEL-audit-id'})
    check('input refused with access off', reply['errorCode'] == 'approval_required')
    base(dict(operation='application.activate', target=str(pid)))
    press(pid, 'Activity')
    for _ in range(15):
        elements = snapshot(pid)
        if any('input.text' in e['label'] for e in elements):
            break
        time.sleep(.2)
    check('Activity reads retained operations', any('input.text' in e['label'] for e in elements))
    press(pid, 'Preview diagnostic export')
    for _ in range(15):
        elements = snapshot(pid)
        if any(e['label'] == 'Save diagnostics' for e in elements):
            break
        time.sleep(.2)
    check('export preview visible', any(e['label'] == 'Save diagnostics' for e in elements))
    check('payload absent from preview', not any('SENTINEL' in e['label'] for e in elements))
    press(pid, 'Save diagnostics')
    text = call('os', '--', '/bin/sh', '-c', 'cat "$HOME/Library/Logs/MachineControl/exports/diagnostics.json"')
    exported = json.loads(text)
    check('native export saved', exported['schema'] == 'machine-control-diagnostics-export/v0')
    check('export excludes payloads', 'SENTINEL' not in text)
    rows = [e for e in exported['audit'] if e['operation'] == 'input.text']
    check('intent and result persisted', {'intent', 'result'} <= {e['phase'] for e in rows})
    check('correlation matches', len({e['requestId'] for e in rows if e.get('requestId')}) == 1)
    # Fail the candidate's own audit directory, with exact restoration.
    press(pid, 'Access')
    press(pid, 'Enable access')
    call('os', '--', '/bin/sh', '-c', 'root="$HOME/Library/Logs/MachineControl"; mv "$root/audit" "$root/audit-fixture-backup"; printf fixture > "$root/audit"')
    try:
        refused = candidate({'operation': 'input.text', 'text': 'SENTINEL-audit-payload'})
        check('storage failure refuses before input', refused['errorCode'] == 'audit_storage_unavailable' and refused['delivery'] == 'refused')
        press(pid, 'Stop access')
        check('Stop remains available', candidate({'operation': 'grant.status'})['data'].get('grant') is None)
    finally:
        call('os', '--', '/bin/sh', '-c', 'root="$HOME/Library/Logs/MachineControl"; rm "$root/audit"; mv "$root/audit-fixture-backup" "$root/audit"')
    candidate({'operation': 'snapshot', 'target': 'com.example.audit-missing-fixture'})
    args.output.write_text(json.dumps({'passed': True, 'checks': checks}, indent=2))
except BaseException:
    args.output.write_text(json.dumps({'passed': False, 'checks': checks}, indent=2))
    raise

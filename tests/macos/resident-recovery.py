#!/usr/bin/env python3
"""Claimed dedicated-guest recovery test; never use on a personal workstation.

Owns a previously absent fixture. Temporarily removes probe execute permission,
restores it in finally, and checks fail-closed input, fresh session readback,
supported stop/maintenance recovery, and stale references. Run on the
controller under `machine-control --target macos run`; caller owns power state.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence-dir', type=Path, required=True)
args = parser.parse_args()
root = args.evidence_dir
root.mkdir(mode=0o700, parents=True, exist_ok=True)
mc = str(Path(__file__).resolve().parents[2] / 'bin/machine-control')
os.environ['MACVM_FORBID_OUTER_UI'] = 'true'
fixture = 'org.machine-control.fixture'


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


signal.signal(signal.SIGTERM, interrupted)


def call(*arguments, check=True, timeout=180):
    result = subprocess.run([mc, *arguments], capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError((arguments[:3], result.returncode, result.stdout[-500:], result.stderr[-500:]))
    return result


def raw(operation, check=True, **fields):
    return json.loads(call('desktop', 'raw', json.dumps(dict(operation=operation, **fields)), check=check).stdout)


def reference():
    result = raw('snapshot', target=fixture, query='Increment', projection='compact')
    value = next(e['reference'] for e in result['data']['elements']
                 if e['label'] == 'Increment' and e['role'] == 'AXButton')
    return result, value


def record(name, value):
    (root / name).write_text(json.dumps(value) + '\n')


# Include every path removed by remove-fixture, not just the application.
call('os', '--', '/usr/bin/python3', '-c', '''
from pathlib import Path
home = Path.home()
for relative in ['Applications/Machine Control Fixture.app',
                 'Library/Caches/machine-control-fixture',
                 'Documents/MachineControlSurfaceCorpus',
                 'Library/Application Support/macvm-testbed/MachineControlFixture.swift']:
    assert not (home / relative).exists(), 'inherited fixture; refusing ownership'
''')

try:
    call('testbed', '--', 'deploy-fixture')
    raw('application.launch', applicationId=fixture)
    for _ in range(20):
        capture = json.loads(call('desktop', 'capture', '--scope', 'window', '--target', fixture).stdout)
        guest_path = capture['data']['artifactPath']
        try:
            with tempfile.TemporaryDirectory(prefix='mc-artifact-check-') as directory:
                local = Path(directory) / 'capture.png'
                call('desktop', 'artifact', guest_path, str(local))
                assert local.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
        finally:
            call('os', '--', '/bin/rm', '-f', guest_path)
    record('artifact-roundtrips.json', dict(roundtrips=20, pngChecks=20, ownedArtifactsRemoved=True))

    # No credentials, arbitrary UI, or TCC edits. Only this bundled observer's
    # execution is faulted; preserve bytes and restore its original mode.
    fault = r'''
import json
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile

def interrupted(signum, frame):
    raise SystemExit(128 + signum)
signal.signal(signal.SIGTERM, interrupted)
home = Path.home()
exe = home / 'Applications/Machine Control.app/Contents/MacOS/macui'
probe = exe.parent.parent / 'Resources/mc-session-probe'
endpoint = home / 'Library/Application Support/MachineControl/control.sock'
def request(obj):
    return json.loads(subprocess.check_output(
        [str(exe), 'request', str(endpoint), json.dumps(obj)], text=True, timeout=15))
healthy = request({'operation': 'status'})
assert healthy['data']['desktopState'] == 'unlocked'
mode = stat.S_IMODE(probe.stat().st_mode)
with tempfile.TemporaryDirectory(prefix='mc-probe-fault-') as directory:
    independent = Path(directory) / 'probe'
    shutil.copy2(probe, independent)
    try:
        probe.chmod(mode & ~0o111)
        failed = request({'operation': 'status'})
        refusal = request({'operation': 'input.key', 'target': 'org.machine-control.fixture',
                           'key': 'a', 'provider': 'macos-native'})
        observed = json.loads(subprocess.check_output([str(independent)], text=True, timeout=15))
        assert observed['desktopState'] == 'unlocked'
        assert failed['data']['desktopState'] == 'unknown'
        assert failed['data']['sessionProbe']['failure'] == 'launch_failed'
        assert failed['data']['semanticAuthorizationState'] == 'ready'
        assert failed['data']['semanticState'] == 'unavailable'
        assert not refusal['accepted'] and refusal['errorCode'] == 'desktop_not_unlocked'
        print(json.dumps(dict(fault='probe_execution_denied', independentDesktop='unlocked',
            residentDesktop='unknown', probe=failed['data']['sessionProbe'],
            semanticAuthorization='ready', semanticReadiness='unavailable',
            inputRefusal=refusal['errorCode'])))
    finally:
        probe.chmod(mode)
restored = request({'operation': 'status'})
assert restored['data']['desktopState'] == 'unlocked'
assert restored['data']['desktopGeneration'] != healthy['data']['desktopGeneration']
assert restored['generation'] == healthy['generation']
print(json.dumps(dict(probeRestored=True, sameResident=True, desktopGenerationChanged=True,
                     ready=restored['data']['inputState'] == 'ready')))
'''
    (root / 'probe-fault.log').write_text(call('os', '--', '/usr/bin/python3', '-c', fault).stdout)
    snapshot, old_reference = reference()
    call('testbed', '--', 'ui', 'resident-stop')
    audit = json.loads(call('maintenance', 'audit', check=False).stdout)
    record('stopped-audit.json', audit)
    assert not audit['data']['healthy']
    repair = json.loads(call('maintenance', 'repair').stdout)
    record('recovery-repair.json', repair)
    assert repair['data']['healthy'] and not repair['data']['reboot']['requested']
    before = json.loads(call('testbed', '--', 'fixture-state').stdout)['count']
    stale = raw('action', reference=old_reference, action='press', check=False)
    assert not stale['accepted'] and stale['errorCode'] == 'stale_reference'
    assert json.loads(call('testbed', '--', 'fixture-state').stdout)['count'] == before
    status = json.loads(call('desktop', 'status').stdout)
    assert status['generation'] != snapshot['generation']
    _, fresh_reference = reference()
    assert raw('action', reference=fresh_reference, action='press')['accepted']
    after = json.loads(call('testbed', '--', 'fixture-state').stdout)['count']
    assert after == before + 1
    record('restart-proof.json', dict(ready=status['data']['inputState'] == 'ready',
        generationChanged=True, staleReferenceRefused=stale['errorCode'], freshActionEffect=True))
finally:
    call('testbed', '--', 'remove-fixture')
print('Artifact round trips, probe failure/refusal/recovery, shutdown, maintenance and stale-reference checks passed')

#!/usr/bin/env python3
"""Bounded, guest-local native workload; caller owns claim, fixture and power.

Run through common `os -- /usr/bin/python3` in a dedicated claimed guest.
Only the deterministic AppKit fixture is queried/captured/acted on. Output
contains aggregate resources and results, never titles, paths or pixels.
"""
import argparse
import collections
import json
from pathlib import Path
import socket
import statistics
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--rounds', type=int, default=300)
parser.add_argument('--idle-seconds', type=int, default=120)
args = parser.parse_args()
assert 1 <= args.rounds <= 10000 and 0 <= args.idle_seconds <= 3600
home = Path.home()
binary = home / 'Applications/Machine Control.app/Contents/MacOS/macui'
endpoint = home / 'Library/Application Support/MachineControl/control.sock'
probe = binary.parent.parent / 'Resources/mc-session-probe'
oracle = home / 'Library/Caches/machine-control-fixture/state.json'
fixture = 'org.machine-control.fixture'
counts = collections.Counter()
latencies = collections.defaultdict(list)
started = time.monotonic()
generation = None
samples = []


def call(operation, **kw):
    request = dict(operation=operation, provider='macos-native', **kw)
    t = time.monotonic()
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(15)
        sock.connect(str(endpoint))
        sock.sendall(json.dumps(request).encode() + b'\n')
        sock.shutdown(socket.SHUT_WR)
        data = b''
        while not data.endswith(b'\n'):
            part = sock.recv(65536)
            assert part, 'resident closed before response'
            data += part
    reply = json.loads(data)
    counts[operation] += 1
    latencies[operation].append(round((time.monotonic() - t) * 1000, 1))
    assert reply.get('accepted'), (operation, reply.get('errorCode'))
    if generation is not None:
        assert reply['generation'] == generation, 'unexpected resident restart'
    return reply


def sample(label):
    status = call('status')['data']
    pid = status['processId']
    lines = subprocess.check_output(['/usr/sbin/lsof', '-nP', '-p', str(pid), '-Ffat'], text=True).splitlines()
    fd = None
    types = collections.Counter()
    access = collections.Counter()
    other = 0
    for line in lines:
        if line.startswith('f'):
            fd = line[1:]
            other += not fd.isdigit()
        elif fd and fd.isdigit():
            if line.startswith('t'): types[line[1:]] += 1
            if line.startswith('a'): access[line[1:]] += 1
    rss = int(subprocess.check_output(['/bin/ps', '-o', 'rss=', '-p', str(pid)], text=True))
    threads = len(subprocess.check_output(['/bin/ps', '-M', '-p', str(pid)], text=True).splitlines()) - 1
    children = subprocess.run(['/usr/bin/pgrep', '-P', str(pid)], capture_output=True, text=True).stdout.splitlines()
    independent = json.loads(subprocess.check_output([str(probe)], text=True))['desktopState']
    ready = {key: status.get(key) for key in ('desktopState', 'inputState', 'semanticState',
              'nativeSemanticState', 'captureState', 'nativeCaptureState')}
    row = dict(phase=label, elapsedSeconds=round(time.monotonic()-started, 1),
               fds=sum(types.values()), fdTypes=dict(types), access=dict(access),
               nonDescriptorEntries=other, rssKiB=rss, threads=threads, children=len(children),
               outstandingTestRequests=0, operations=dict(counts), readiness=ready,
               independentDesktop=independent)
    samples.append(row)
    print(json.dumps(row), flush=True)
    assert independent == 'unlocked' and ready['desktopState'] == 'unlocked'
    assert all(v == 'ready' for k, v in ready.items() if k != 'desktopState')
    assert row['fds'] <= samples[0]['fds'] + 8, 'resident descriptor growth'
    assert row['children'] <= 1, 'resident child accumulation'


def state():
    return json.loads(oracle.read_text())


def wait_effect(key, previous):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if state()[key] > previous: return
        time.sleep(.02)
    raise AssertionError('fixture effect missing: ' + key)


def snapshot():
    reply = call('snapshot', target=fixture, query='Increment', maxDepth=12,
                 maxElements=120, projection='compact')
    elements = reply['data']['elements']
    return next(e['reference'] for e in elements if e['role'] == 'AXButton' and e['label'] == 'Increment')


def action():
    ref = snapshot()
    previous = state()['count']
    call('action', reference=ref, action='press')
    wait_effect('count', previous)


def key():
    previous = state()['keyEventCount']
    call('input.key', target=fixture, key='cmd-a', deliveryMode='foreground')
    wait_effect('keyEventCount', previous)


def capture():
    result = call('capture', target=fixture)
    path = Path(result['data']['artifactPath'])
    root = home / 'Library/Caches/machine-control/artifacts'
    assert path.parent == root and path.name.startswith('capture-')
    try:
        assert path.stat().st_size > 0
        with path.open('rb') as stream: assert stream.read(8) == b'\x89PNG\r\n\x1a\n'
    finally:
        path.unlink(missing_ok=True)


initial = call('status')
generation = initial['generation']
assert oracle.is_file(), 'caller must launch the owned fixture first'
sample('baseline')
for name, operation, count in [
    ('status', lambda: call('status'), 200),
    ('AX-observation', snapshot, 100),
    ('AX-action', action, 100),
    ('activation', lambda: call('application.activate', target=fixture), 100),
    ('keyboard', key, 100),
    ('capture', capture, 30),
]:
    for i in range(count): operation()
    sample(name)
for i in range(args.rounds):
    action()
    call('application.activate', target=fixture)
    key()
    if i % 10 == 0: capture()
    if (i + 1) % 50 == 0: sample('mixed-' + str(i + 1))
sample('mixed-complete')
for i in range(0, args.idle_seconds, 30):
    time.sleep(min(30, args.idle_seconds - i))
    sample('idle-' + str(min(i+30, args.idle_seconds)))
print(json.dumps(dict(summary='passed', operations=dict(counts),
    latencyMs={op:dict(p50=statistics.median(values), p95=sorted(values)[int((len(values)-1)*.95)], maximum=max(values))
               for op, values in latencies.items()}, samples=len(samples))), flush=True)

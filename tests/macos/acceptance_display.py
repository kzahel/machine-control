"""Request an unfiltered VM frame from the claimed controller, with no guest capture."""

import json
import os
import re
import subprocess
import time
import uuid


MARKER = b'MC_ACCEPTANCE_FRAME '
PNG = b'\x89PNG\r\n\x1a\n'


def frame_path(stage, token):
    return stage / f'display-frame-{token}.png'


def request_frame(stage):
    token = uuid.uuid4().hex
    frame = frame_path(stage, token)
    print(MARKER.decode('ascii') + token, flush=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            contents = frame.read_bytes()
        except FileNotFoundError:
            time.sleep(.1)
            continue
        frame.unlink()
        if not contents.startswith(PNG):
            raise ValueError('Controller did not return a PNG display frame')
        return contents
    raise TimeoutError('Controller did not return a passive display frame')


def observe_cover(source_root, evidence, prefix, *, covered):
    tool = source_root.parent / 'observe-acceptance-cover'
    if not tool.exists():
        subprocess.run(['xcrun', 'swiftc', str(source_root / 'tests/macos/cover-observation.swift'),
                        '-o', str(tool)], check=True, capture_output=True, timeout=90)
    image = evidence / (prefix + '.png')
    with os.fdopen(os.open(image, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(request_frame(source_root.parent))
    observation = subprocess.run([str(tool), str(image)], capture_output=True, timeout=30)
    report = json.loads(observation.stdout)
    with os.fdopen(os.open(evidence / (prefix + '.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(report, stream)
    # An uncovered frame before each observed owner prevents an old painted
    # cover from passing again if Tart no longer refreshes its window.
    if covered:
        assert observation.returncode == 0 and report['sampledConcealment'] is True, report
    else:
        assert observation.returncode == 1 and report['coverTextObserved'] is False, report


def deliver_frame(line, stage, capture, send, seen):
    if not line.startswith(MARKER):
        return False
    token = line.removeprefix(MARKER).rstrip(b'\n')
    if not re.fullmatch(rb'[0-9a-f]{32}', token) or len(seen) >= 16 or token in seen:
        raise ValueError('Invalid or repeated acceptance display request')
    seen.add(token)
    contents = capture()
    if not contents.startswith(PNG) or len(contents) > 64 * 1024 * 1024:
        raise ValueError('Unexpected passive display frame')
    send(frame_path(stage, token.decode('ascii')), contents)
    return True


def stage_frame(call, frame, contents):
    # Publish atomically so the waiting guest cannot read a partial screenshot.
    call('testbed', '--', 'exec', '-i', '/bin/sh', '-c',
         'umask 077; /bin/cat > "$1.tmp" && /bin/mv "$1.tmp" "$1"',
         'acceptance-frame', str(frame), input=contents)

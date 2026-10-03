#!/usr/bin/env python3
"""Bound a live byte transport to its adapter-selected exact target claim.

Labels/claim IDs coordinate same-user callers; this is not authentication.
The guardian never acquires or renews a claim and never replays a frame.
"""
from __future__ import annotations

import argparse
import os
import queue
import signal
import subprocess
import sys
import threading
import time

import claims

MAX_FRAME = 65536
CHECK_INTERVAL = 1.0


def run(command: list[str], check, *, input_stream=None, output_stream=None) -> int:
    input_stream = input_stream or sys.stdin.buffer
    output_stream = output_stream or sys.stdout.buffer
    check()  # refuse before launching a provider
    parent = os.getppid()
    child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, start_new_session=os.name != 'nt')
    ended = threading.Event()
    frames = queue.Queue(maxsize=8)
    errors = queue.Queue(maxsize=1)

    def fail(error):
        try: errors.put_nowait(error)
        except queue.Full: pass
        ended.set()

    def read_input():
        try:
            buffer = bytearray()
            while not ended.is_set():
                chunk = os.read(input_stream.fileno(), 16384)
                if not chunk: ended.set(); return
                buffer.extend(chunk)
                while b'\n' in buffer:
                    newline = buffer.index(b'\n') + 1
                    if newline > MAX_FRAME: raise claims.ClaimError('control_frame_too_large', 'Control frame exceeds its bound')
                    frame = bytes(buffer[:newline]); del buffer[:newline]
                    while not ended.is_set():
                        try: frames.put(frame, timeout=.1); break
                        except queue.Full: pass
                if len(buffer) > MAX_FRAME:
                    raise claims.ClaimError('control_frame_too_large', 'Control frame exceeds its bound')
        except (OSError, ValueError, claims.ClaimError) as error: fail(error)

    def write_input():
        try:
            while not ended.is_set():
                try: frame = frames.get(timeout=.1)
                except queue.Empty: continue
                check()  # immediately before forwarding each complete frame
                if ended.is_set(): return
                child.stdin.write(frame); child.stdin.flush()
        except (OSError, ValueError, claims.ClaimError) as error: fail(error)

    def read_output():
        try:
            while not ended.is_set():
                chunk = os.read(child.stdout.fileno(), 65536)
                if not chunk: ended.set(); return
                output_stream.write(chunk); output_stream.flush()
        except (OSError, ValueError) as error: fail(error)

    workers = [threading.Thread(target=operation, daemon=True)
               for operation in [read_input, write_input, read_output]]
    for worker in workers: worker.start()
    next_check = time.monotonic() + CHECK_INTERVAL
    try:
        while not ended.wait(.1):
            if os.getppid() != parent or child.poll() is not None: break
            if time.monotonic() >= next_check:
                check(); next_check = time.monotonic() + CHECK_INTERVAL
    except (OSError, claims.ClaimError) as error: fail(error)
    finally:
        ended.set()
        if child.poll() is None:
            try:
                if os.name == 'nt': child.terminate()
                else: os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError: pass
        try: child.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                if os.name == 'nt': child.kill()
                else: os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            child.wait(timeout=2)
        # Termination releases pipe writers before closing buffered handles.
        for stream in [child.stdin, child.stdout]:
            try: stream.close()
            except (OSError, ValueError): pass
        for worker in workers: worker.join(timeout=.1)
    if not errors.empty():
        error = errors.get()
        print(getattr(error, 'code', 'control_transport_closed'), file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--provider', required=True)
    parser.add_argument('--resource-id', required=True)
    parser.add_argument('--claim-id', required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    options = parser.parse_args(argv)
    command = options.command[1:] if options.command[:1] == ['--'] else options.command
    if not command: parser.error('a transport command is required')
    checker = claims.parser().parse_args(['--state-dir', options.state_dir, 'check',
        '--provider', options.provider, '--resource-id', options.resource_id, '--claim-id', options.claim_id])
    try: return run(command, lambda: claims.command_check(checker))
    except KeyboardInterrupt: return 130
    except (claims.ClaimError, OSError) as error:
        print(getattr(error, 'code', 'control_transport_unavailable'), file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())

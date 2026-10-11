"""Signed-runtime lifecycle exclusion through its inherited operator transport.

Run in a claimed target's interactive Medium session with no desktop operator
running. This uses the existing operator bridge, never a public approval hook.
No installer or update replacement is dispatched.
"""
import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'schema': 'machine-control-runtime-lifecycle-live/v0', 'passed': False, 'checks': []}
    child = subprocess.Popen([str(args.install / 'runtime/machine-control-windows.exe'), 'desktop',
                              '--instance', 'lifecycle-fixture', '--presentation', 'minimal'],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    replies = queue.Queue(maxsize=1)
    def receive():
        while True:
            line = child.stdout.readline(1024 * 1024 + 1)
            replies.put(line)
            if not line:
                return
    threading.Thread(target=receive, daemon=True).start()
    def call(value):
        child.stdin.write(json.dumps(value) + '\n'); child.stdin.flush()
        line = replies.get(timeout=10)
        if not line or len(line) > 1024 * 1024:
            raise RuntimeError('Missing or oversized lifecycle reply')
        return json.loads(line)
    def check(value, label):
        if not value:
            raise AssertionError(label)
        report['checks'].append(label)
        print(label, flush=True)
    try:
        check(call({'method': 'hello', 'processId': os.getpid()})['ok'], 'Inherited operator handshake')
        check(call({'method': 'arm', 'scopes': ['observe'], 'lifetime': 'until_stopped'})['ok'], 'Native operator indefinite consent')
        check(not call({'method': 'prepare_update'})['ok'], 'Active consent excludes replacement')
        check(call({'method': 'stop'})['ok'], 'Native Stop revokes consent')
        check(call({'method': 'prepare_update'})['ok'], 'Access-off enters update exclusion')
        check(not call({'method': 'arm', 'scopes': ['observe'], 'duration': 60})['ok'], 'Update exclusion refuses new consent')
        check(call({'method': 'cancel_update'})['ok'], 'Cancelled replacement releases exclusion')
        check(call({'method': 'arm', 'scopes': ['observe'], 'duration': 60})['ok'], 'Consent works after cancellation')
        check(call({'method': 'prepare_exit'})['ok'], 'Exit revokes volatile authority')
        check(call({'method': 'quit'})['ok'], 'Native quit acknowledged')
        check(child.wait(timeout=10) == 0, 'Resident exits and closes its endpoints')
        report['passed'] = True
    except BaseException as error:
        report['error'] = str(error)
        raise
    finally:
        if child.poll() is None:
            child.kill(); child.wait(timeout=10)
        for stream in (child.stdin, child.stdout, child.stderr):
            stream.close()
        (args.output / 'result.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

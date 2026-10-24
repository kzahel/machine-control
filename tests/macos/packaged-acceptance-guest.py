#!/usr/bin/env python3
"""Private-stage guest half of packaged-acceptance.py; dedicated VirtualMac only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage', required=True, type=Path)
    p.add_argument('--claim', required=True)
    p.add_argument('--repeat', type=int, required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--soak-seconds', type=int, default=0)
    p.add_argument('--faults', action='store_true')
    a = p.parse_args()
    assert subprocess.check_output(['sysctl', '-n', 'hw.model']).decode().startswith('VirtualMac')
    root = a.stage
    installed = Path.home() / 'Applications/Machine Control.app'
    endpoint = Path.home() / 'Library/Application Support/MachineControl/control.sock'
    policy = Path('/Library/Application Support/MachineControl/policy.json')
    agent = Path.home() / 'Library/LaunchAgents/org.machine-control.resident.plist'
    domain = 'gui/' + str(os.getuid())
    label = domain + '/org.machine-control.resident'
    observer_socket = root / 'observer/control.sock'
    backup = root / 'backup'
    backup.mkdir(mode=0o700)
    output = root / 'results'
    output.mkdir(mode=0o700)

    def command(*args, check=True):
        return subprocess.run([str(v) for v in args], check=check, capture_output=True, timeout=90)

    def exchange(path, operation):
        with socket.socket(socket.AF_UNIX) as c:
            c.settimeout(10)
            c.connect(str(path))
            c.sendall(json.dumps(dict(operation=operation, claimId=a.claim)).encode() + b'\n')
            return json.loads(c.makefile('rb').readline(32 * 1024 * 1024))

    def status(path=endpoint):
        try:
            value = exchange(path, 'status')
            return value['data'] if value.get('accepted') else None
        except (OSError, ValueError):
            return None

    def wait(fn, description):
        end = time.monotonic() + 45
        while time.monotonic() < end:
            value = fn()
            if value:
                return value
            time.sleep(.2)
        raise AssertionError(description)

    def stop():
        for operation in ['grant.revoke', 'server.stop']:
            try:
                exchange(endpoint, operation)
            except (OSError, ValueError):
                pass
        command('/bin/launchctl', 'bootout', label, check=False)
        wait(lambda: status() is None, 'Candidate did not release canonical endpoint')
        endpoint.unlink(missing_ok=True)

    def manifest(app):
        result = {}
        for f in sorted(app.rglob('*')):
            mode = stat.S_IMODE(f.lstat().st_mode)
            value = (['link', mode, os.readlink(f)] if f.is_symlink() else
                     ['file', mode, hashlib.sha256(f.read_bytes()).hexdigest()] if f.is_file() else
                     ['directory', mode])
            result[str(f.relative_to(app))] = value
        return result

    def interrupted(*_):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    assert status()['deployment']['policy']['grantMode'] == 'standing'
    original_manifest = manifest(installed)
    command('/usr/bin/ditto', installed, backup / 'Original.app')
    assert manifest(backup / 'Original.app') == original_manifest
    original_agent = agent.read_bytes()
    agent_mode = stat.S_IMODE(agent.stat().st_mode)
    original_policy = policy.read_bytes()
    policy_stat = policy.stat()
    (backup / 'policy.json').write_bytes(original_policy)
    saved = {}
    for name in ['operator-consent.json', 'presentation.json']:
        f = endpoint.parent / name
        saved[name] = (f.read_bytes(), stat.S_IMODE(f.stat().st_mode)) if f.exists() else None
    prefs = command('/usr/bin/defaults', 'export', 'org.machine-control.app', '-', check=False)
    (backup / 'preferences.plist').write_bytes(prefs.stdout)
    observer = None
    mutated = False
    try:
        observer_socket.parent.mkdir(mode=0o700)
        with (output / 'observer.log').open('wb') as log:
            observer = subprocess.Popen([str(backup / 'Original.app/Contents/MacOS/macui'),
                'serve', str(observer_socket)], stdout=log, stderr=log)
        observed = wait(lambda: status(observer_socket), 'Observer unavailable')
        assert observed['deployment']['policy']['grantMode'] == 'standing'
        assert observed['nativeSemanticState'] == 'ready'
        mutated = True
        stop()
        work = root / 'workstation.json'
        work.write_text(json.dumps({'schema': 'machine-control-policy/v0',
                                   'preset': 'workstation', 'protectedOperations': False}))
        command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m', '644', work, policy)
        for name in saved:
            (endpoint.parent / name).unlink(missing_ok=True)
        presentation = endpoint.parent / 'presentation.json'
        presentation.write_text(json.dumps({'schema': 'machine-control-presentation/v1', 'profile': 'minimal'}))
        presentation.chmod(0o600)
        command('/bin/bash', root / 'install-user.sh', '--app', root / 'candidate/Machine Control.app')
        current = wait(status, 'Installed candidate unavailable')
        assert current['deployment']['policy']['grantMode'] == 'approval'
        assert current['nativeSemanticState'] == 'ready', 'Signed candidate needs normal Accessibility consent'
        command('/usr/bin/codesign', '--verify', '--deep', '--strict', installed)
        argv = ['/usr/bin/python3', str(root / 'source/tests/macos/browser-file-dialogs.py'),
                '--source-root', str(root / 'source'), '--claim', a.claim,
                '--repeat', str(a.repeat), '--seed', str(a.seed), '--soak-seconds', str(a.soak_seconds),
                '--expected-policy', 'approval', '--observer-socket', str(observer_socket),
                '--settings-cycle', '--trace', str(output / 'operations.jsonl'),
                '--report', str(output / 'summary.json')]
        if a.faults:
            argv += ['--faults']
        with (output / 'suite.log').open('wb') as log:
            proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                for line in proc.stdout:
                    log.write(line)
                    log.flush()
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
                assert proc.wait(timeout=10) == 0, 'Packaged acceptance failed; inspect private suite.log'
            finally:
                if proc.poll() is None:
                    proc.send_signal(signal.SIGINT)
                    proc.wait(timeout=30)
    finally:
        errors = []
        if mutated:
            try:
                stop()
                command('/usr/bin/sudo', '-n', '/usr/bin/install', '-m',
                        format(stat.S_IMODE(policy_stat.st_mode), 'o'), backup / 'policy.json', policy)
                command('/usr/bin/sudo', '-n', '/usr/sbin/chown',
                        str(policy_stat.st_uid) + ':' + str(policy_stat.st_gid), policy)
                for name, value in saved.items():
                    f = endpoint.parent / name
                    if value is None:
                        f.unlink(missing_ok=True)
                    else:
                        f.write_bytes(value[0])
                        f.chmod(value[1])
                if prefs.returncode == 0:
                    command('/usr/bin/defaults', 'import', 'org.machine-control.app', backup / 'preferences.plist')
                else:
                    command('/usr/bin/defaults', 'delete', 'org.machine-control.app', check=False)
                command('/bin/bash', root / 'install-user.sh', '--app', backup / 'Original.app')
                command('/bin/launchctl', 'bootout', label, check=False)
                agent.write_bytes(original_agent)
                agent.chmod(agent_mode)
                command('/bin/launchctl', 'bootstrap', domain, agent)
                restored = wait(status, 'Original resident did not return')
                assert restored['deployment']['policy']['grantMode'] == 'standing'
                assert restored['nativeSemanticState'] == 'ready'
                assert manifest(installed) == original_manifest
                assert policy.read_bytes() == original_policy and policy.stat().st_uid == policy_stat.st_uid
                assert agent.read_bytes() == original_agent
                for name, value in saved.items():
                    f = endpoint.parent / name
                    assert ((f.read_bytes(), stat.S_IMODE(f.stat().st_mode)) == value
                            if value is not None else not f.exists())
                print('Original app, policy, LaunchAgent and operator state restored', flush=True)
            except BaseException as error:
                errors.append(str(error))
        if observer is not None:
            try:
                exchange(observer_socket, 'server.stop')
            except (OSError, ValueError):
                pass
            try:
                observer.wait(timeout=15)
            except subprocess.TimeoutExpired:
                observer.terminate()
                observer.wait(timeout=10)
        (output / 'cleanup.json').write_text(json.dumps({'restored': not errors, 'errors': errors}) + '\n')
        if errors:
            raise RuntimeError('Restoration incomplete: ' + '; '.join(errors))


if __name__ == '__main__':
    main()

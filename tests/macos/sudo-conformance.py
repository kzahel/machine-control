#!/usr/bin/env python3
"""Real sudo and native dialog acceptance in a claimed dedicated Tart guest.

The caller owns doctor/claim/power. Supply signed helper binaries and the
native Accessibility driver app. A temporary exact-command PASSWD rule
overrides the appliance's usual NOPASSWD rule; cleanup always removes it.
The canonical owner-only VM password streams directly to the fixture driver.
Never run this against a workstation.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import stat
import subprocess
import tarfile
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--claim', required=True)
    parser.add_argument('--helpers', type=Path, required=True)
    parser.add_argument('--driver-app', type=Path, required=True)
    parser.add_argument('--secret-file', type=Path, required=True)
    args = parser.parse_args()
    secret_stat = args.secret_file.lstat()
    assert stat.S_ISREG(secret_stat.st_mode) and stat.S_IMODE(secret_stat.st_mode) == 0o600
    assert secret_stat.st_uid == os.getuid() and secret_stat.st_size > 0
    mc = [str(ROOT / 'bin/machine-control'), '--target', args.target, '--claim', args.claim]

    def run(*argv, input=None, check=True, timeout=60):
        result = subprocess.run(mc + ['os', '--', *argv], input=input,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout)
        if check and result.returncode:
            raise AssertionError(f'guest operation failed ({result.returncode}): '
                                 + result.stderr.decode(errors='replace')[:1200])
        return result

    doctor = json.loads(subprocess.check_output(
        [str(ROOT / 'bin/machine-control'), '--target', args.target, 'target', 'doctor']))
    assert doctor['target']['profile'] == 'macos-aqua-tart', 'dedicated Tart appliance required'
    assert doctor['ready'], 'appliance must be ready before conformance'
    suffix = uuid.uuid4().hex[:12]
    directory = f'/tmp/mc-sudo-conformance-{suffix}'
    rule = f'/etc/sudoers.d/zz-mc-sudo-conformance-{suffix}'
    helper = directory + '/helpers with spaces/mc-sudo'
    askpass = directory + '/helpers with spaces/mc-sudo-askpass'
    driver = directory + '/Sudo Test Driver.app/Contents/MacOS/driver'
    marker = directory + '/root-effect'
    active = []
    observed = []
    rule_installed = False
    try:
        run('/bin/mkdir', '-p', directory)
        with tempfile.TemporaryDirectory(prefix='mc-sudo-archive-') as temporary:
            archive = Path(temporary) / 'fixture.tar'
            with tarfile.open(archive, 'w') as stream:
                for name in ['mc-sudo', 'mc-sudo-askpass']:
                    stream.add(args.helpers / name, arcname='helpers with spaces/' + name)
                stream.add(args.driver_app, arcname='Sudo Test Driver.app')
            run('-i', '/usr/bin/tar', '-xf', '-', '-C', directory, input=archive.read_bytes())
        assert run(driver, 'permission').stdout.strip() == b'trusted', 'driver needs native Accessibility consent'
        script = f'''set -eu
rule={shlex.quote(rule)}
[ ! -e "$rule" ]
printf '%s ALL=(root) PASSWD: /usr/bin/id -u, /usr/bin/touch {marker}\\n' "$(id -un)" | sudo -n tee "$rule" >/dev/null
printf 'Defaults:%s timestamp_type=global\\n' "$(id -un)" | sudo -n tee -a "$rule" >/dev/null
sudo -n chmod 440 "$rule"
sudo -n visudo -cf /etc/sudoers >/dev/null
'''
        rule_installed = True
        run('-i', '/bin/bash', '-s', input=script.encode())
        run('/usr/bin/sudo', '-K')
        assert run('/usr/bin/sudo', '-n', '/usr/bin/id', '-u', check=False).returncode != 0

        direct = run(askpass, check=False)
        assert direct.returncode != 0 and direct.stdout == b''
        observed.append(direct.stdout + direct.stderr)
        print('PASS direct askpass refusal', flush=True)

        # Existing appliance NOPASSWD policy is preserved for other commands.
        literal = run(helper, '--', '/usr/bin/printf', '%s\n', 'argument with spaces',
                      '$(literal shell text)', '--literal')
        assert literal.stdout == b'argument with spaces\n$(literal shell text)\n--literal\n'
        assert run(helper, '--', '/usr/bin/false', check=False).returncode == 1
        observed.append(literal.stdout + literal.stderr)
        print('PASS existing NOPASSWD policy, literal arguments and command exit status', flush=True)

        def launch(command, seconds=120):
            existing = set(run('/usr/bin/pgrep', '-x', 'mc-sudo-askpass', check=False).stdout.split())
            child = subprocess.Popen(mc + ['os', '--', helper, '--timeout', str(seconds), '--', *command],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True)
            active.append(child)
            deadline = time.monotonic() + min(seconds, 40)
            last_error = b''
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    output, errors = child.communicate()
                    raise AssertionError('sudo ended before native dialog: ' + errors.decode(errors='replace'))
                pids = run('/usr/bin/pgrep', '-x', 'mc-sudo-askpass', check=False).stdout.split()
                for pid in pids:
                    if pid in existing:
                        continue
                    inspection = run(driver, 'inspect', pid.decode(), askpass, check=False)
                    if inspection.returncode == 0:
                        return child, int(pid)
                    last_error = inspection.stderr
                time.sleep(0.1)
            raise AssertionError('verified native dialog did not appear: ' + last_error.decode(errors='replace'))

        def finish(child, expected_success=False):
            output, errors = child.communicate(timeout=35)
            observed.append(output + errors)
            assert (child.returncode == 0) == expected_success, errors.decode(errors='replace')
            return output

        child, pid = launch(['/usr/bin/id', '-u'])
        run(driver, 'cancel', str(pid), askpass)
        assert finish(child) == b''
        print('PASS native cancellation', flush=True)

        child, pid = launch(['/usr/bin/id', '-u'])
        run(driver, 'interrupt', str(pid), askpass)
        assert finish(child) == b''
        assert run('/usr/bin/pgrep', '-x', 'mc-sudo-askpass', check=False).returncode != 0
        print('PASS wrapper termination closes authentication helper', flush=True)

        first, first_pid = launch(['/usr/bin/id', '-u'])
        second, second_pid = launch(['/usr/bin/id', '-u'])
        assert first_pid != second_pid
        run(driver, 'cancel', str(first_pid), askpass)
        assert finish(first) == b'' and second.poll() is None
        run(driver, 'cancel', str(second_pid), askpass)
        assert finish(second) == b''
        print('PASS concurrent invocations retain separate prompts', flush=True)

        child, pid = launch(['/usr/bin/id', '-u'])
        run('-i', driver, 'authenticate', str(pid), askpass,
            input=b'mc-sudo-deliberately-invalid-fixture-password\n')
        assert finish(child) == b''
        print('PASS failed authentication without automatic credential retry', flush=True)

        child, pid = launch(['/usr/bin/id', '-u'], seconds=10)
        assert finish(child) == b''
        print('PASS visible dialog timeout', flush=True)

        child, pid = launch(['/usr/bin/id', '-u'])
        # Discovery above and the driver's repeated exact field/code preflight
        # precede reading from the canonical controller-local secret store.
        with args.secret_file.open('rb') as secret:
            result = subprocess.run(mc + ['os', '--', '-i', driver, 'authenticate', str(pid), askpass],
                                    stdin=secret, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        observed.append(result.stdout + result.stderr)
        assert result.returncode == 0, 'secure credential delivery failed'
        assert finish(child, True).strip() == b'0'
        assert run('/usr/bin/sudo', '-n', '/usr/bin/id', '-u', check=False).returncode != 0
        print('PASS real sudo authentication and root UID', flush=True)

        child, pid = launch(['/usr/bin/touch', marker])
        with args.secret_file.open('rb') as secret:
            result = subprocess.run(mc + ['os', '--', '-i', driver, 'authenticate', str(pid), askpass],
                                    stdin=secret, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        observed.append(result.stdout + result.stderr)
        assert result.returncode == 0
        finish(child, True)
        assert run('/usr/bin/stat', '-f', '%u', marker).stdout.strip() == b'0'
        print('PASS independently observed root-owned file effect', flush=True)

        # Scan retained process output locally without printing the secret.
        with args.secret_file.open('rb') as secret:
            password = secret.read().rstrip(b'\r\n')
        assert password and all(password not in value for value in observed), 'secret reached captured output'
        del password
        print('PASS password absent from captured command and driver output', flush=True)
    finally:
        # Stop this fixture's guest wrappers before tearing down transport.
        # Killing only the local CLI can leave its transport descendants
        # holding captured pipes while the guest prompt is still active.
        cleanup = f'''for pid in $(/usr/bin/pgrep -x mc-sudo || true); do
path=$(/bin/ps -p "$pid" -o comm=)
if [ "$path" = {shlex.quote(helper)} ] || [ "$path" = {shlex.quote('/private' + helper)} ]; then
/bin/kill -TERM "$pid"
fi
done
'''
        run('-i', '/bin/bash', '-s', input=cleanup.encode(), check=False)
        for child in active:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.communicate()
        if rule_installed:
            run('/usr/bin/sudo', '-K')
            run('/usr/bin/sudo', '-n', '/bin/rm', '-f', rule)
            run('/usr/bin/sudo', '-n', '/usr/sbin/visudo', '-cf', '/etc/sudoers')
        run('/usr/bin/sudo', '-n', '/bin/rm', '-rf', directory)


if __name__ == '__main__':
    main()

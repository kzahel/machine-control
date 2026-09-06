#!/usr/bin/env python3
"""Finish or resume a dedicated ChromeOS testbed from its SSH controller."""
import argparse
import json
import os
from pathlib import Path
import runpy
import shlex
import subprocess
import sys
import time

SCRIPTS = Path(__file__).resolve().parent
PLATFORM = SCRIPTS.parent
REMOTE = '/mnt/stateful_partition/etc/ssh'
PATH_SETUP = 'export PATH=/bin:/usr/bin:/usr/local/bin:/sbin:/usr/sbin:$PATH; '
NETWORK = runpy.run_path(str(SCRIPTS / 'network-check.py'))


class Setup:
    def __init__(self, host, yes=False, wait_timeout=180):
        self.host = host
        self.yes = yes
        self.wait_timeout = wait_timeout

    def remote(self, command, capture=False, timeout=300, source=None):
        return subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                               '-o', 'ConnectionAttempts=1', self.host, PATH_SETUP + command],
                              input=source, capture_output=capture, text=True, timeout=timeout)

    def read(self, command):
        result = self.remote(command, capture=True, timeout=15)
        return result.stdout.strip() if result.returncode == 0 else ''

    def platform(self, *args, capture=False):
        return subprocess.run(['bash', str(PLATFORM / 'bin/chromeos'), *args],
                              env={**os.environ, 'CHROMEBOOK_HOST': self.host},
                              capture_output=capture, text=True, timeout=600)

    def wait(self, predicate, message):
        print(message, flush=True)
        deadline = time.monotonic() + self.wait_timeout
        while True:
            if predicate():
                return True
            if time.monotonic() >= deadline:
                print('Setup is paused. Resolve the indicated step, then rerun the same chromeos setup command.', flush=True)
                return False
            time.sleep(2)

    def preflight(self):
        result = NETWORK['check'](self.host)
        # SSH itself owns host-key verification. accept-new never replaces a
        # mismatching existing key; unattended --yes explicitly permits TOFU.
        if not result['ok'] and 'Host key verification failed' in result.get('sshError', ''):
            if self.yes:
                subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
                                '-o', 'StrictHostKeyChecking=accept-new', self.host, 'true'],
                               timeout=15, check=False)
            elif sys.stdin.isatty():
                print('Confirm the new device host key through SSH:', flush=True)
                subprocess.run(['ssh', '-o', 'ConnectTimeout=5', self.host, 'true'], check=False)
            result = NETWORK['check'](self.host)
        NETWORK['explain'](result)
        return result['ok']

    def approve(self):
        if self.yes or self.read(f'cat {REMOTE}/setup-approved 2>/dev/null') == 'dedicated-appliance-v1':
            return True
        print('Setup configures root SSH, developer Python, DevTools, always-awake operation,')
        print('and Select-to-speak in the active profile. It can disable rootfs verification,')
        print('reboot for setup, and reboot again to verify automatic SSH. No passwords are collected.')
        if not sys.stdin.isatty():
            print('Run interactively or supply --yes for an already-authorized setup.')
            return False
        return input('Proceed with dedicated-appliance setup? [y/N] ').lower() in ('y', 'yes')

    def execute(self):
        if not self.preflight():
            return 1
        if not self.approve():
            return 1
        # Bootstrap validates ChromeOS/Developer Mode before touching boot state.
        staged = f'{REMOTE}/setup-bootstrap.sh'
        result = subprocess.run(['scp', '-q', str(SCRIPTS / 'bootstrap.sh'), f'{self.host}:{staged}'], timeout=30)
        if result.returncode:
            return result.returncode
        for _ in range(3):  # Pending update, rootfs transition, writable-image installation.
            old_boot = self.read('cat /proc/sys/kernel/random/boot_id')
            if not old_boot:
                return 1
            print('Installing/resuming the saved bootstrap. If it reboots, return to VT2 as root and run:', flush=True)
            print(f'  bash {REMOTE}/start_sshd.sh', flush=True)
            result = self.remote(f'bash {staged} --yes', timeout=600)
            if result.returncode == 0:
                break
            if result.returncode not in (2, 255):
                return result.returncode
            if not self.wait(lambda: bool((boot := self.read('cat /proc/sys/kernel/random/boot_id')) and boot != old_boot),
                             'Waiting for SSH on the new boot. start_sshd.sh restores access; this command will finish setup.'):
                return 2
        else:
            print('Too many image transitions; inspect chromeos post-update before resuming.')
            return 1

        if self.platform('deploy').returncode:
            return 1
        if self.platform('fix-devtools', '-y').returncode:
            return 1
        audit = self.platform('--json', 'post-update', capture=True)
        try:
            proven = audit.returncode == 0 and json.loads(audit.stdout).get('ok') is True
        except (ValueError, TypeError):
            proven = False
        if not proven and self.platform('post-update', '--verify-reboot', '-y').returncode:
            return 1
        if not self.wait(lambda: self.read("mount | grep -q ' /home/chronos/user ' && echo active") == 'active',
                         'Sign in normally on the Chromebook if needed. Setup will continue when the profile is unlocked.'):
            return 2
        client_dir = str(Path(os.environ.get('CHROMEOS_CLIENT_PATH', '/mnt/stateful_partition/c2/client.py')).parent)
        command = f'PYTHONPATH={shlex.quote(client_dir)} LD_LIBRARY_PATH=/usr/local/lib64 python3 -'
        if self.remote(command, source=(SCRIPTS / 'setup-accessibility.py').read_text()).returncode:
            return 1
        if self.platform('doctor').returncode or self.platform('smoke-test').returncode:
            return 1
        if self.remote(f"printf 'complete\\n' > {REMOTE}/setup-state && rm -f {REMOTE}/setup-approved").returncode:
            return 1
        print('SETUP COMPLETE: automatic SSH, runtime, desktop accessibility, capture and input verified.', flush=True)
        return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', '-y', action='store_true', help='Approve setup and accept new SSH host keys (never changed keys)')
    parser.add_argument('--wait-timeout', type=int, default=180, help='Seconds to wait at each physical recovery/sign-in step')
    args = parser.parse_args()
    if args.wait_timeout < 1:
        parser.error('--wait-timeout must be positive')
    host = os.environ.get('CHROMEBOOK_HOST', 'chromeos-testbed')
    if host.startswith('-'):
        parser.error('Invalid SSH host')
    try:
        return Setup(host, args.yes, args.wait_timeout).execute()
    except (OSError, subprocess.TimeoutExpired, EOFError) as exc:
        print(f'Setup stopped: {exc}. Rerun chromeos setup to resume.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

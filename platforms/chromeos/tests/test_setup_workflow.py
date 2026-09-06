import shutil
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
SOURCE = (SCRIPTS / 'bootstrap.sh').read_text()
WORKFLOW = SOURCE.split('# BEGIN setup workflow\n')[1].split('# END setup workflow')[0]
spec = importlib.util.spec_from_file_location('chromeos_setup', SCRIPTS / 'setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class BootstrapTransitionTests(unittest.TestCase):
    def transition(self, device='/dev/mmcblk0p5', update='UPDATE_STATUS_IDLE', repair='no', writable='no', fail=0):
        with tempfile.TemporaryDirectory() as directory:
            script = WORKFLOW.replace('/usr/share/vboot/bin/make_dev_ssd.sh', 'make_dev_fixture') + '''
SSH_DIR="$FIXTURE_DIR"
REPAIR_ONLY="$REPAIR"
ROOTFS_WRITABLE="$WRITABLE"
BOOTSTRAP_REBOOT=no
rootdev() { echo "$DEVICE"; }
update_engine_client() { echo "CURRENT_OP=$UPDATE"; }
make_dev_fixture() { printf '%s\n' "$*" > "$SSH_DIR/kernel-call"; return "$FAIL"; }
prepare_boot_transition
printf 'REBOOT=%s\n' "$BOOTSTRAP_REBOOT"
'''
            env = dict(os.environ, FIXTURE_DIR=directory, DEVICE=device, UPDATE=update,
                       REPAIR=repair, WRITABLE=writable, FAIL=str(fail))
            p = subprocess.run(['bash', '-ec', script], env=env, text=True, capture_output=True)
            state = Path(directory, 'setup-state')
            call = Path(directory, 'kernel-call')
            return p, state.read_text().strip() if state.exists() else '', call.read_text() if call.exists() else ''

    def test_active_image_is_prepared_and_resume_state_saved(self):
        for device, partition in [('/dev/mmcblk0p5', 4), ('/dev/nvme0n1p3', 2), ('/dev/sda3', 2)]:
            with self.subTest(device=device):
                p, state, call = self.transition(device=device)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(call.strip(), f'--remove_rootfs_verification --partitions {partition}')
                self.assertEqual(state, 'awaiting-rootfs-reboot')
                self.assertIn('REBOOT=yes', p.stdout)

    def test_pending_update_reboots_before_modifying_old_kernel(self):
        p, state, call = self.transition(update='UPDATE_STATUS_UPDATED_NEED_REBOOT')
        self.assertEqual(p.returncode, 0)
        self.assertEqual(state, 'awaiting-update-reboot')
        self.assertEqual(call, '')

    def test_unsafe_partition_or_failed_signing_never_requests_reboot(self):
        for kwargs in [{'device': '/dev/dm-0'}, {'device': '/dev/mmcblk0p7'}, {'fail': 1}]:
            with self.subTest(kwargs=kwargs):
                p, state, _ = self.transition(**kwargs)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(state, '')
                self.assertNotIn('REBOOT=yes', p.stdout)

    def test_repair_only_never_changes_boot_state(self):
        p, state, call = self.transition(repair='yes')
        self.assertEqual((p.returncode, state, call), (0, '', ''))
        self.assertIn('REBOOT=no', p.stdout)

    def test_writable_image_proceeds_to_controller(self):
        p, state, call = self.transition(writable='yes')
        self.assertEqual((p.returncode, state, call), (0, 'controller-required', ''))

    def test_declined_approval_does_not_create_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            script = WORKFLOW + '\nSSH_DIR="$FIXTURE_DIR"\napprove_setup\n'
            p = subprocess.run(['bash', '-ec', script], input='n\n', text=True,
                               env=dict(os.environ, FIXTURE_DIR=directory), capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(Path(directory, 'setup-approved').exists())


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class KeyImportTests(unittest.TestCase):
    def test_missing_key_fails_without_network_lookup(self):
        with tempfile.TemporaryDirectory() as directory:
            script = WORKFLOW + '''
SSH_DIR="$FIXTURE_DIR"
AUTH_DIR="$FIXTURE_DIR"
CONTROLLER_PUBKEY=""
curl() { touch "$FIXTURE_DIR/download-called"; }
import_controller_keys
'''
            p = subprocess.run(['bash', '-ec', script], env=dict(os.environ, FIXTURE_DIR=directory), capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(Path(directory, 'download-called').exists())

    def test_multiple_keys_validated_before_any_key_is_added(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(root / 'key')], check=True)
            valid = (root / 'key.pub').read_text().strip()
            script = WORKFLOW + '''
SSH_DIR="$FIXTURE_DIR"
AUTH_DIR="$FIXTURE_DIR"
CONTROLLER_PUBKEY="$KEYS"
import_controller_keys
'''
            env = dict(os.environ, FIXTURE_DIR=directory, KEYS=valid + '\nssh-ed25519 invalid')
            p = subprocess.run(['bash', '-ec', script], env=env, capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse((root / 'authorized_keys').exists())
            env['KEYS'] = valid
            for _ in range(2):
                subprocess.run(['bash', '-ec', script], env=env, capture_output=True, check=True)
            self.assertEqual((root / 'authorized_keys').read_text().splitlines(), [valid])


class FakeSetup(setup.Setup):
    def __init__(self, bootstrap_codes=(0,), locked=False, fail_stage=None):
        super().__init__('fixture-target', yes=True)
        self.calls = []
        self.bootstrap_codes = iter(bootstrap_codes)
        self.locked = locked
        self.fail_stage = fail_stage

    def preflight(self):
        self.calls.append('network')
        return self.fail_stage != 'network'

    def approve(self):
        self.calls.append('approval')
        return True

    def read(self, command):
        return 'boot-fixture'

    def wait(self, predicate, message):
        self.calls.append('wait')
        return not (self.locked and 'Sign in' in message)

    def remote(self, command, **kwargs):
        self.calls.append(command)
        code = next(self.bootstrap_codes) if command.startswith('bash ') else 0
        return subprocess.CompletedProcess([], code, '', '')

    def platform(self, *args, **kwargs):
        self.calls.append(args)
        code = 1 if args[0] == self.fail_stage else 0
        return subprocess.CompletedProcess([], code, '{"ok":true}', '')


class ControllerSetupTests(unittest.TestCase):
    @mock.patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
    def test_completed_flow_and_resumed_boot(self, run):
        for codes in [(0,), (2, 0), (255, 0)]:
            runner = FakeSetup(codes)
            self.assertEqual(runner.execute(), 0)
            self.assertEqual(runner.calls[:2], ['network', 'approval'])
            self.assertIn(('deploy',), runner.calls)
            self.assertIn(('smoke-test',), runner.calls)
            self.assertIn('setup-state', runner.calls[-1])

    @mock.patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
    def test_failed_preflight_never_mutates(self, run):
        runner = FakeSetup(fail_stage='network')
        self.assertEqual(runner.execute(), 1)
        run.assert_not_called()

    @mock.patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
    def test_profile_lock_pauses_without_marking_complete(self, run):
        runner = FakeSetup(locked=True)
        self.assertEqual(runner.execute(), 2)
        self.assertNotIn(('smoke-test',), runner.calls)

    @mock.patch.object(setup.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0))
    def test_failed_smoke_is_not_completion(self, run):
        runner = FakeSetup(fail_stage='smoke-test')
        self.assertEqual(runner.execute(), 1)
        self.assertNotIn('setup-state', str(runner.calls[-1]))


class NetworkTests(unittest.TestCase):
    def test_private_vpn_route_is_identified_without_flagging_public_routes(self):
        identify = setup.NETWORK['vpn_route']
        self.assertTrue(identify('192.168.99.10', 'interface: utun4'))
        self.assertTrue(identify('10.1.2.3', 'dev tailscale0'))
        self.assertFalse(identify('192.168.99.10', 'interface: en0'))
        self.assertFalse(identify('8.8.8.8', 'interface: utun4'))

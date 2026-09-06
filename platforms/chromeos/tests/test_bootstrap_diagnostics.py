import shutil
"""Verify the final report without operating a real ChromeOS host."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "scripts/bootstrap.sh").read_text()
FUNCTION = SOURCE.split('# BEGIN bootstrap diagnostics\n')[1].split('# END bootstrap diagnostics')[0]


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class BootstrapDiagnosticsTests(unittest.TestCase):
    def run_report(self, handshake, setup_status, delivery):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bootstrap.log').write_text('fixture bootstrap failure detail\n')
            (root / 'power-policy.log').write_text('fixture power evidence\n')
            # Functions intercept probes before any host tools can be invoked.
            script = '''
exec 3>&1 4>&2
PORT=2223
SSH_DIR="$REPORT_ROOT"
SSHD_CONFIG="$REPORT_ROOT/missing-config"
BOOTSTRAP_LOG="$REPORT_ROOT/bootstrap.log"
BOOTSTRAP_REPORT="$REPORT_ROOT/report.txt"
ROOTFS_WRITABLE=no
POWER_POLICY_READY=yes
POWER_POLICY_GUARD_READY=no
BOOTSTRAP_FAILED_LINE=none
CHROMEOS_TESTBED_REPORT_URL=http://controller.invalid/report
ip() { echo '2: wlan0 inet 192.0.2.2/24'; }
ss() { echo 'LISTEN 0 128 0.0.0.0:2223 0.0.0.0:*'; }
ssh-keyscan() { if [ "$HANDSHAKE" = yes ]; then echo '[localhost]:2223 ssh-ed25519 fixture'; fi; }
iptables() { echo '-A INPUT -p tcp --dport 2223 -j ACCEPT'; }
rootdev() { echo /dev/mockp5; }
curl() { return "$DELIVERY"; }
''' + FUNCTION + '\nbootstrap_diagnostics "$SETUP_STATUS"\n'
            env = dict(os.environ, REPORT_ROOT=directory, HANDSHAKE=handshake,
                       SETUP_STATUS=str(setup_status), DELIVERY=str(delivery))
            result = subprocess.run(['bash', '-c', script], env=env, text=True, capture_output=True)
            report = (root / 'report.txt').read_text()
            self.assertIn('fixture bootstrap failure detail', report)
            self.assertIn('--- INPUT rules and packet counters ---', report)
            self.assertIn('PERSISTENCE: pending', result.stdout)
            return result

    def test_incomplete_setup_reports_working_local_ssh_and_delivered_report(self):
        result = self.run_report('yes', 1, 0)
        self.assertEqual(result.returncode, 1)
        self.assertIn('SETUP: INCOMPLETE', result.stdout)
        self.assertIn('SSH LOCAL HANDSHAKE: OK', result.stdout)
        self.assertIn('REPORT DELIVERY: OK', result.stdout)

    def test_missing_handshake_fails_even_after_successful_start(self):
        result = self.run_report('no', 0, 1)
        self.assertEqual(result.returncode, 1)
        self.assertIn('SSH LOCAL HANDSHAKE: FAIL', result.stdout)
        self.assertIn('REPORT DELIVERY: FAILED', result.stdout)
        self.assertNotIn('SETUP: completed', result.stdout)


@unittest.skipIf(os.name == "nt" or not shutil.which("bash") or not shutil.which("ssh-keygen"), "Requires POSIX shell and OpenSSH")
class BootstrapPythonTests(unittest.TestCase):
    def test_runtime_provisioning_is_conditional_and_reports_failures(self):
        runtime = SOURCE.split('# --- Target runtime ---\n')[1].split('# --- Dev password ---')[0]
        for initial, install_status, expected, called in [('yes', 0, 'yes', 'no'), ('no', 0, 'yes', 'yes'), ('no', 1, 'no', 'yes')]:
            with self.subTest(initial=initial, install_status=install_status):
                script = '''
ready="$INITIAL"
called=no
python3() { [ "$ready" = yes ]; }
dev_install() {
    called=yes
    [ "$*" = '--only_bootstrap --yes' ] || exit 99
    [ "$INSTALL_STATUS" = 0 ] || return 1
    ready=yes
}
''' + runtime + '\nprintf "RESULT %s %s\\n" "$PYTHON_READY" "$called"\n'
                env = dict(os.environ, INITIAL=initial, INSTALL_STATUS=str(install_status))
                result = subprocess.run(['bash', '-ec', script], env=env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f'RESULT {expected} {called}', result.stdout)

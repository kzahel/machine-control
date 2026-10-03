import json
import os
from pathlib import Path
import stat
import shutil
import subprocess
import tempfile
import textwrap
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
CLI = REPO_DIR / "bin" / "chromeos"
BASH = shutil.which("bash")


@unittest.skipIf(BASH is None, "post-update audit tests require Bash")
@unittest.skipIf(os.name == "nt", "post-update SSH fixture requires POSIX execution")
class PostUpdateAuditTests(unittest.TestCase):
    def run_audit(self, snapshot, ssh_up=True):
        with tempfile.TemporaryDirectory() as directory:
            fake_bin = Path(directory)
            fake_ssh = fake_bin / "ssh"
            fake_ssh.write_text(textwrap.dedent("""\
                #!/bin/sh
                if [ "${FAKE_SSH_UP:-yes}" != yes ]; then
                    exit 255
                fi
                case "$*" in
                    *"echo ok"*) printf 'ok\\n' ;;
                    *) printf '%s\\n' "$FAKE_SNAPSHOT" ;;
                esac
            """))
            fake_ssh.chmod(fake_ssh.stat().st_mode | stat.S_IXUSR)
            env = os.environ.copy()
            env.update({
                "PATH": f"{fake_bin}{os.pathsep}{env['PATH']}",
                "CHROMEBOOK_HOST": "fake-chromebook",
                "FAKE_SSH_UP": "yes" if ssh_up else "no",
                "FAKE_SNAPSHOT": textwrap.dedent(snapshot).strip(),
            })
            return subprocess.run(
                [BASH, str(CLI), "--json", "post-update"],
                cwd=REPO_DIR,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_ready_image_is_reboot_proven(self):
        result = self.run_audit("""
            release\t16700.60.0
            boot_id\tnew-boot
            update_operation\tUPDATE_STATUS_IDLE
            rootfs_writable\tyes
            autostart\trunning
            fallback\tyes
            prepared_release\t16700.60.0
            boot_evidence\tautomatic
            devtools_configured\tyes
            devtools_listening\tyes
            repair_staged\tno
            power_policy_helper\tyes
            power_policy_guard\tyes
            power_policy_configured\tyes
            power_policy_boot_evidence\tapplied
        """)

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["bootReady"])
        self.assertEqual("ready", payload["status"])

    def test_updated_read_only_image_requires_repair(self):
        result = self.run_audit("""
            release\t16700.60.0
            boot_id\tupdated-boot
            update_operation\tUPDATE_STATUS_IDLE
            rootfs_writable\tno
            autostart\tmissing
            fallback\tyes
            prepared_release\tmissing
            boot_evidence\tnone
            devtools_configured\tno
            devtools_listening\tno
            repair_staged\tno
            power_policy_helper\tno
            power_policy_guard\tno
            power_policy_configured\tno
            power_policy_boot_evidence\tnone
        """)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual("repair_required", payload["status"])
        self.assertFalse(payload["bootReady"])
        failed = {item["name"] for item in payload["checks"]
                  if item["status"] == "fail"}
        self.assertIn("SSH autostart job is missing", failed)
        self.assertIn("Rootfs verification is enabled", failed)

    def test_pending_update_is_not_reported_ready(self):
        result = self.run_audit("""
            release\t16700.46.0
            boot_id\told-boot
            update_operation\tUPDATE_STATUS_UPDATED_NEED_REBOOT
            rootfs_writable\tyes
            autostart\trunning
            fallback\tyes
            prepared_release\t16700.46.0
            boot_evidence\tautomatic
            devtools_configured\tyes
            devtools_listening\tyes
            repair_staged\tno
            power_policy_helper\tyes
            power_policy_guard\tyes
            power_policy_configured\tyes
            power_policy_boot_evidence\tapplied
        """)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("update_pending", payload["status"])

    def test_missing_closed_lid_policy_requires_repair(self):
        result = self.run_audit("""
            release\t16700.60.0
            boot_id\tcurrent-boot
            update_operation\tUPDATE_STATUS_IDLE
            rootfs_writable\tyes
            autostart\trunning
            fallback\tyes
            prepared_release\t16700.60.0
            boot_evidence\tautomatic
            devtools_configured\tyes
            devtools_listening\tyes
            repair_staged\tno
            power_policy_helper\tno
            power_policy_guard\tno
            power_policy_configured\tno
            power_policy_boot_evidence\tnone
        """)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("repair_required", payload["status"])
        failed = {
            item["name"] for item in payload["checks"]
            if item["status"] == "fail"
        }
        self.assertIn("Closed-lid power policy helper is missing", failed)
        self.assertIn(
            "Always-awake power policy self-healing guard is missing", failed
        )
        self.assertIn(
            "Closed-lid availability policy is not configured", failed
        )
        self.assertIn(
            "Current boot lacks closed-lid power policy evidence", failed
        )

    def test_unreachable_ssh_has_actionable_json(self):
        result = self.run_audit("", ssh_up=False)

        self.assertEqual(1, result.returncode)
        payload = json.loads(result.stdout)
        self.assertEqual("ssh_unreachable", payload["status"])

    def test_mutating_mode_rejects_structured_output(self):
        result = subprocess.run(
            [BASH, str(CLI), "--json", "post-update", "--repair"],
            cwd=REPO_DIR,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(1, result.returncode)
        self.assertIn("read-only post-update audit", result.stderr)


@unittest.skipIf(BASH is None or os.name == "nt", "Requires POSIX Bash")
class BootProofTests(unittest.TestCase):
    def prove(self, boot_only=True, automatic=True, changed=True, prepared=True):
        source = (REPO_DIR / 'scripts/post-update.sh').read_text()
        ready = source.split('boot_ready() {', 1)[1].split('\nemit_audit()', 1)[0]
        verify = source.split('verify_reboot() {', 1)[1].rsplit('\ncase "$MODE" in', 1)[0]
        script = 'boot_ready() {' + ready + '\nverify_reboot() {' + verify + '''
RELEASE=fixture
UPDATE_OPERATION=UPDATE_STATUS_IDLE
ROOTFS_WRITABLE=yes
AUTOSTART=running
FALLBACK=yes
PREPARED_RELEASE="$PREPARED"
DEVTOOLS_CONFIGURED=yes
DEVTOOLS_LISTENING=no
POWER_POLICY_HELPER=yes
POWER_POLICY_GUARD=yes
POWER_POLICY_CONFIGURED=yes
POWER_POLICY_BOOT_EVIDENCE=applied
BOOT_ID=old
BOOT_EVIDENCE="$EVIDENCE"
STATUS=repair_required
SSH_HOST=fixture
REMOTE_PATH_SETUP=:
require_ssh() { return 0; }
load_snapshot() { return 0; }
evaluate_snapshot() { return 0; }
emit_audit() { echo "FULL_RUNTIME_STATUS=$STATUS"; }
confirm_reboot() { return 0; }
print_vt2_ssh_instructions() { echo 'VT2 fallback'; }
sleep() { SECONDS=$((SECONDS + 100)); }
ssh() {
    case "$*" in
        *reboot*) echo REBOOT_REQUESTED ;;
        *) echo "$NEXT_BOOT" ;;
    esac
}
verify_reboot
'''
        env = dict(os.environ, BOOT_ONLY='true' if boot_only else 'false',
                   EVIDENCE='automatic' if automatic else 'manual',
                   NEXT_BOOT='new' if changed else 'old',
                   PREPARED='fixture' if prepared else 'old-release')
        env.pop('BASH_ENV', None)
        return subprocess.run([BASH, '-c', script], env=env, text=True, capture_output=True, timeout=5)

    def test_explicit_boot_proof_can_succeed_without_claiming_devtools_readiness(self):
        result = self.prove()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('FULL_RUNTIME_STATUS=repair_required', result.stdout)
        self.assertIn('still require separate verification', result.stdout)

    def test_default_proof_still_requires_devtools(self):
        self.assertNotEqual(self.prove(boot_only=False).returncode, 0)

    def test_boot_proof_requires_new_boot_and_automatic_evidence(self):
        for kwargs in [{'automatic': False}, {'changed': False}]:
            with self.subTest(kwargs=kwargs):
                self.assertNotEqual(self.prove(**kwargs).returncode, 0)

    def test_unprepared_image_is_refused_before_reboot(self):
        result = self.prove(prepared=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('REBOOT_REQUESTED', result.stdout)

    def test_boot_only_cannot_be_used_for_an_audit(self):
        result = subprocess.run([BASH, str(CLI), 'post-update', '--boot-only'],
                                text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('requires --verify-reboot', result.stderr)


if __name__ == "__main__":
    unittest.main()

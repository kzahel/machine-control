import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


REPO_DIR = Path(__file__).resolve().parents[1]
CLI = REPO_DIR / "bin" / "chromeos"
COMMON_CLI = REPO_DIR.parents[1] / "bin" / "machine-control"
COMMON_DOCTOR = REPO_DIR / "scripts" / "common-doctor.py"
DOCTOR_SOURCE = REPO_DIR / "tests" / "fixtures" / "common-doctor-source"
POST_UPDATE_SOURCE = (
    REPO_DIR / "tests" / "fixtures" / "common-post-update-source"
)


@unittest.skipIf(
    os.name == "nt",
    "ChromeOS shell-adapter composition requires a POSIX controller",
)
class CommonSurfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary.name)
        self.state = self.directory / "state"
        self.log = self.directory / "mutations"
        self.registry = self.directory / "targets.json"
        self.registry.write_text(
            json.dumps({
                "schema": "machine-control-targets/v0",
                "includeDefaults": True,
                "targets": {},
            }),
            encoding="utf-8",
        )
        self.state.write_text("ready", encoding="utf-8")
        for path in (DOCTOR_SOURCE, POST_UPDATE_SOURCE, COMMON_DOCTOR):
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.temporary.cleanup()

    def environment(self, *, session="locked"):
        value = os.environ.copy()
        value.update({
            "CHROMEOS_COMMON_DOCTOR_LEGACY": str(DOCTOR_SOURCE),
            "CHROMEOS_COMMON_DOCTOR_POST_UPDATE": str(POST_UPDATE_SOURCE),
            "CHROMEOS_MAINTENANCE_POST_UPDATE": str(POST_UPDATE_SOURCE),
            "CHROMEOS_MAINTENANCE_DOCTOR": str(COMMON_DOCTOR),
            "FAKE_CHROMEOS_STATE": str(self.state),
            "FAKE_CHROMEOS_MUTATION_LOG": str(self.log),
            "FAKE_CHROMEOS_SESSION": session,
            "MACHINE_CONTROL_TARGETS_FILE": str(self.registry),
        })
        return value

    def run_cli(self, *arguments, session="locked"):
        result = subprocess.run(
            [str(CLI), *arguments],
            cwd=REPO_DIR,
            env=self.environment(session=session),
            text=True,
            capture_output=True,
            check=False,
        )
        value = json.loads(result.stdout) if result.stdout.strip() else None
        return result, value

    def assert_minimized(self, result):
        for private in (
            "private-device", "private-release", "private-boot-id",
            "private/python", "private/client", "private partition",
        ):
            self.assertNotIn(private, result.stdout)

    def test_common_doctor_reports_unlocked_ready_state(self):
        result, value = self.run_cli("common-doctor", session="unlocked")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(value["ready"])
        self.assertEqual(value["states"]["boot"], "ready")
        self.assertEqual(value["states"]["desktop"], "unlocked")
        self.assertEqual(value["extensions"]["rootfsVerification"], "disabled")
        self.assertEqual(
            next(
                check for check in value["checks"]
                if check["id"] == "rootfs_verification"
            )["status"],
            "pass",
        )
        self.assertEqual(value["lifecycleOperations"], [])
        self.assertFalse(self.log.exists())
        self.assert_minimized(result)

    def test_common_doctor_separates_locked_profile_from_boot_health(self):
        result, value = self.run_cli("common-doctor")

        self.assertEqual(result.returncode, 1)
        self.assertFalse(value["ready"])
        self.assertEqual(value["states"]["boot"], "ready")
        self.assertEqual(value["states"]["desktop"], "locked")
        self.assertEqual(value["states"]["semantic"], "unavailable")
        self.assertFalse(self.log.exists())
        self.assert_minimized(result)

    def test_common_doctor_reports_unreachable_without_claiming_power_off(self):
        self.state.write_text("ssh_unreachable", encoding="utf-8")
        result, value = self.run_cli("common-doctor")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["states"]["power"], "unknown")
        self.assertEqual(value["states"]["connection"], "unavailable")
        self.assertEqual(value["extensions"]["rootfsVerification"], "unknown")
        self.assertFalse(self.log.exists())
        self.assert_minimized(result)

    def test_common_doctor_reports_enabled_rootfs_verification(self):
        self.state.write_text("repair_required_rootfs", encoding="utf-8")
        result, value = self.run_cli("common-doctor")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(value["states"]["boot"], "degraded")
        self.assertEqual(value["extensions"]["rootfsVerification"], "enabled")
        check = next(
            check for check in value["checks"]
            if check["id"] == "rootfs_verification"
        )
        self.assertEqual(check["status"], "fail")
        self.assertFalse(self.log.exists())
        self.assert_minimized(result)

    def test_audit_is_healthy_while_profile_is_locked(self):
        result, value = self.run_cli(
            "maintenance", "audit", "--profile", "runtime", "--json"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(value["healthy"])
        self.assertFalse(value["doctor"]["ready"])
        self.assertEqual(value["doctor"]["states"]["boot"], "ready")
        self.assertFalse(self.log.exists())
        self.assert_minimized(result)

    def test_ready_repair_is_nonmutating_without_reboot(self):
        result, value = self.run_cli(
            "maintenance", "repair", "--profile", "runtime", "--json"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(value["healthy"])
        self.assertEqual(
            value["post_update"]["repairs"],
            [{"id": "active_image", "status": "not_needed"}],
        )
        self.assertFalse(self.log.exists())

    def test_guided_recovery_states_refuse_before_mutation(self):
        for state in ("update_pending", "repair_required_rootfs"):
            with self.subTest(state=state):
                self.state.write_text(state, encoding="utf-8")
                if self.log.exists():
                    self.log.unlink()
                result, value = self.run_cli(
                    "maintenance", "repair", "--profile", "runtime",
                    "--reboot", "--json",
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(value["failure"], "guided_recovery_required")
                self.assertFalse(value["reboot"]["observed"])
                self.assertFalse(self.log.exists())
                self.assertEqual(self.state.read_text(encoding="utf-8"), state)
                self.assert_minimized(result)

    def test_explicit_reboot_uses_only_existing_boot_proof(self):
        result, value = self.run_cli(
            "maintenance", "repair", "--profile", "runtime",
            "--reboot", "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(value["healthy"])
        self.assertTrue(value["reboot"]["requested"])
        self.assertTrue(value["reboot"]["observed"])
        self.assertEqual(
            self.log.read_text(encoding="utf-8").splitlines(),
            ["verify-reboot"],
        )
        self.assertFalse(value["doctor"]["ready"])

    def test_safe_active_image_repair_can_be_followed_by_proof_reboot(self):
        self.state.write_text("repair_required_safe", encoding="utf-8")
        result, value = self.run_cli(
            "maintenance", "repair", "--profile", "runtime",
            "--reboot", "--json",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(value["healthy"])
        self.assertEqual(
            self.log.read_text(encoding="utf-8").splitlines(),
            ["repair", "verify-reboot"],
        )
        self.assertEqual(self.state.read_text(encoding="utf-8"), "ready")

    def test_repository_entry_composes_actual_chromeos_adapter(self):
        doctor = subprocess.run(
            [
                str(COMMON_CLI), "--target", "chromeos",
                "target", "doctor",
            ],
            cwd=REPO_DIR.parents[1],
            env=self.environment(session="unlocked"),
            text=True,
            capture_output=True,
            check=False,
        )
        doctor_value = json.loads(doctor.stdout)
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertEqual(doctor_value["schema"], "machine-control-doctor/v0")
        self.assertEqual(doctor_value["target"]["logicalTarget"], "chromeos")

        audit = subprocess.run(
            [
                str(COMMON_CLI), "--target", "chromeos",
                "maintenance", "audit",
            ],
            cwd=REPO_DIR.parents[1],
            env=self.environment(session="locked"),
            text=True,
            capture_output=True,
            check=False,
        )
        audit_value = json.loads(audit.stdout)
        self.assertEqual(audit.returncode, 0, audit.stderr)
        self.assertTrue(audit_value["data"]["healthy"])
        self.assertFalse(audit_value["data"]["readiness"]["ready"])
        self.assert_minimized(audit)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ios_device


def fake_device(
    name: str = "iPhone",
    *,
    identifier: str = "PRIVATE-DEVICE-ID",
    reality: str = "physical",
) -> dict[str, object]:
    return {
        "identifier": identifier,
        "deviceProperties": {
            "name": name,
            "osVersionNumber": "26.6",
            "developerModeStatus": "enabled",
        },
        "connectionProperties": {
            "pairingState": "paired",
            "transportType": "wired",
            "tunnelState": "connected",
        },
        "hardwareProperties": {
            "udid": identifier,
            "reality": reality,
            "platform": "iOS",
            "marketingName": "iPhone SE (3rd generation)",
        },
    }


class DeviceSelectionTests(unittest.TestCase):
    def test_selects_only_connected_physical_candidate(self) -> None:
        selected = ios_device.select_device([fake_device()])
        self.assertEqual(
            ios_device.nested_string(selected, "deviceProperties", "name"),
            "iPhone",
        )

    def test_requires_selector_for_multiple_devices(self) -> None:
        with self.assertRaisesRegex(ios_device.TestbedError, "multiple physical"):
            ios_device.select_device([fake_device("One"), fake_device("Two")])

    def test_selects_explicit_unique_name(self) -> None:
        selected = ios_device.select_device(
            [fake_device("One"), fake_device("Two")], "Two"
        )
        self.assertEqual(
            ios_device.nested_string(selected, "deviceProperties", "name"),
            "Two",
        )

    def test_rejects_ambiguous_name(self) -> None:
        with self.assertRaisesRegex(ios_device.TestbedError, "ambiguous"):
            ios_device.select_device(
                [fake_device("iPhone", identifier="ONE"), fake_device("iPhone", identifier="TWO")],
                "iPhone",
            )

    def test_excludes_nonphysical_target(self) -> None:
        with self.assertRaisesRegex(ios_device.TestbedError, "no physical"):
            ios_device.select_device([fake_device(reality="simulator")])

    def test_summary_does_not_contain_identifier(self) -> None:
        summary = json.dumps(ios_device.device_summary(fake_device()))
        self.assertNotIn("PRIVATE-DEVICE-ID", summary)


class CommandTests(unittest.TestCase):
    def config(self, root: Path) -> ios_device.Config:
        return ios_device.Config(
            device_selector="iPhone",
            team_id="TEAM123",
            runner_bundle_id="com.example.runner",
            state_dir=root / "state",
            agent_device=root / "agent-device",
            signing_identity="Apple Development",
        )

    @mock.patch("ios_device.selected_device_name", return_value="iPhone")
    def test_agent_argv_adds_explicit_physical_target(
        self, _selected: mock.Mock
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            argv = ios_device.agent_argv(config, ["snapshot", "-i"])
        self.assertEqual(argv[-4:], ["--platform", "ios", "--device", "iPhone"])

    @mock.patch("ios_device.selected_device_name", return_value="iPhone")
    def test_agent_argv_preserves_explicit_target(self, _selected: mock.Mock) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            argv = ios_device.agent_argv(
                config,
                ["snapshot", "--platform", "ios", "--device", "iPhone"],
            )
        self.assertEqual(argv.count("--platform"), 1)
        self.assertEqual(argv.count("--device"), 1)

    def test_redacts_coredevice_identifiers(self) -> None:
        text = "device A1B2C3D4-E5F6-7890-ABCD-EF1234567890 failed"
        self.assertEqual(ios_device.redact(text), "device <identifier> failed")

    def test_assert_alias_uses_agent_device_is_command(self) -> None:
        self.assertEqual(ios_device.FORWARDED_COMMANDS["assert"], "is")

    @mock.patch("ios_device.forward", return_value=0)
    def test_main_forwards_upstream_flags_without_separator(
        self, forwarded: mock.Mock
    ) -> None:
        result = ios_device.main(["snapshot", "-i", "--level", "digest"])
        self.assertEqual(result, 0)
        forwarded.assert_called_once()
        self.assertEqual(
            forwarded.call_args.args[1:],
            ("snapshot", ["-i", "--level", "digest"]),
        )

    def test_daemon_recovery_environment_does_not_require_signing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = ios_device.Config(
                device_selector="",
                team_id="",
                runner_bundle_id="",
                state_dir=root / "state",
                agent_device=root / "agent-device",
                signing_identity="",
            )
            with mock.patch.dict(os.environ, {}, clear=True):
                env = ios_device.daemon_environment(config)
        self.assertEqual(
            env["AGENT_DEVICE_STATE_DIR"], str(root / "state" / "agent-device")
        )
        self.assertNotIn("AGENT_DEVICE_IOS_TEAM_ID", env)

    @mock.patch("ios_device.runner_cache_available", return_value=True)
    @mock.patch(
        "ios_device.lock_state",
        return_value={"passcodeRequired": False, "unlockedSinceBoot": True},
    )
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    def test_common_doctor_is_device_shaped_and_minimized(
        self,
        _device: mock.Mock,
        _lock: mock.Mock,
        _cache: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            checks = [ios_device.Check("device", "ok", "private device detail")]
            document = ios_device.common_doctor_document(config, checks)
        self.assertEqual(document["target"]["kind"], "device")
        self.assertEqual(document["states"]["connection"], "ready")
        self.assertNotIn("private device detail", json.dumps(document))
        self.assertNotIn("PRIVATE-DEVICE-ID", json.dumps(document))

    @mock.patch("ios_device.release_lease")
    @mock.patch("ios_device.acquire_lease")
    @mock.patch("ios_device.stop_daemon")
    @mock.patch("ios_device.devicectl_json", return_value={"result": {}})
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    @mock.patch("ios_device.selected_device_name", return_value="iPhone")
    def test_reboot_waits_for_physical_device_reconnect(
        self,
        _name: mock.Mock,
        _device: mock.Mock,
        devicectl: mock.Mock,
        _stop: mock.Mock,
        acquire: mock.Mock,
        _release: mock.Mock,
    ) -> None:
        acquire.return_value = ios_device.Lease(
            "token", 1, "controller", "command", "session", "now"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = ios_device.reboot_device(self.config(Path(directory)), 90)
        self.assertEqual(result, 0)
        self.assertIn("--wait-for-device", devicectl.call_args.args[0])
        self.assertIn("90", devicectl.call_args.args[0])

    def test_runner_cache_matches_version_team_and_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.config(root)
            product = (
                root
                / ".agent-device"
                / "apple-runner"
                / "derived"
                / "ios-device"
                / "cache-test"
                / "Build"
                / "Products"
                / "Runner.xctestrun"
            )
            product.parent.mkdir(parents=True)
            product.touch()
            manifest = product.parents[2] / ".agent-device-runner-cache.json"
            manifest.write_text(
                json.dumps(
                    {
                        "packageVersion": ios_device.PINNED_AGENT_DEVICE_VERSION,
                        "runnerBundleBuildSettings": [
                            "AGENT_DEVICE_IOS_RUNNER_APP_BUNDLE_ID=com.example.runner",
                            "AGENT_DEVICE_IOS_RUNNER_TEST_BUNDLE_ID=com.example.runner.uitests",
                        ],
                        "runnerSigningBuildSettings": [
                            "CODE_SIGN_STYLE=Automatic",
                            "DEVELOPMENT_TEAM=TEAM123",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(ios_device.Path, "home", return_value=root):
                self.assertTrue(ios_device.runner_cache_available(config))

                wrong_team = ios_device.Config(
                    **{**config.__dict__, "team_id": "OTHERTEAM"}
                )
                self.assertFalse(ios_device.runner_cache_available(wrong_team))


class LeaseTests(unittest.TestCase):
    def config(self, root: Path) -> ios_device.Config:
        return ios_device.Config(
            device_selector="iPhone",
            team_id="TEAM123",
            runner_bundle_id="com.example.runner",
            state_dir=root,
            agent_device=root / "agent-device",
            signing_identity="Apple Development",
        )

    def test_lease_is_private_and_released_by_token_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            lease = ios_device.acquire_lease(config, mode="test")
            mode = stat.S_IMODE(config.lease_path.stat().st_mode)
            if os.name != "nt":
                self.assertEqual(mode, 0o600)
            ios_device.release_lease(config, lease)
            self.assertFalse(config.lease_path.exists())

    def test_live_lease_is_not_stolen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            lease = ios_device.acquire_lease(config, mode="first")
            self.addCleanup(ios_device.release_lease, config, lease)
            with self.assertRaisesRegex(ios_device.TestbedError, "leased by"):
                ios_device.acquire_lease(config, mode="second", alive=lambda _pid: True)

    def test_stale_same_controller_lease_is_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            first = ios_device.acquire_lease(config, mode="first")
            cleaned: list[bool] = []
            second = ios_device.acquire_lease(
                config,
                mode="second",
                alive=lambda _pid: False,
                stale_cleanup=lambda: cleaned.append(True),
            )
            self.assertNotEqual(first.token, second.token)
            self.assertEqual(cleaned, [True])
            ios_device.release_lease(config, second)

    def test_nested_token_must_match_journal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            lease = ios_device.acquire_lease(config, mode="test")
            self.addCleanup(ios_device.release_lease, config, lease)
            with mock.patch.dict(
                os.environ, {"IOS_DEVICE_TESTBED_LEASE_TOKEN": "wrong"}
            ), self.assertRaisesRegex(ios_device.TestbedError, "does not match"):
                ios_device.active_nested_lease(config)


if __name__ == "__main__":
    unittest.main()

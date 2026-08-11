from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import ios_device


def fake_device(
    name: str = "iPhone",
    *,
    identifier: str = "PRIVATE-DEVICE-ID",
    reality: str = "physical",
    pairing: str = "paired",
    transport: str = "wired",
    tunnel: str = "connected",
) -> dict[str, object]:
    return {
        "identifier": identifier,
        "deviceProperties": {
            "name": name,
            "osVersionNumber": "26.6",
            "developerModeStatus": "enabled",
        },
        "connectionProperties": {
            "pairingState": pairing,
            "transportType": transport,
            "tunnelState": tunnel,
        },
        "hardwareProperties": {
            "udid": identifier,
            "reality": reality,
            "platform": "iOS",
            "marketingName": "iPhone SE (3rd generation)",
        },
    }


class DeviceSelectionTests(unittest.TestCase):
    @mock.patch("ios_device.run_capture")
    def test_parses_only_identifier_rows_from_developer_mode_inventory(
        self, capture: mock.Mock
    ) -> None:
        capture.return_value = mock.Mock(
            returncode=0,
            stdout=(
                "UDID Developer Mode Status\n"
                "00000000-0000000000000000 enabled\n"
                "not-an-identifier disabled\n"
            ),
        )
        self.assertEqual(
            ios_device.developer_mode_device_identifiers(),
            ["00000000-0000000000000000"],
        )

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

    @mock.patch("ios_device.device_details", return_value=fake_device())
    @mock.patch(
        "ios_device.developer_mode_device_identifiers",
        return_value=["PRIVATE-DEVICE-ID"],
    )
    @mock.patch(
        "ios_device.devicectl_json", return_value={"result": {"devices": []}}
    )
    def test_discovery_merges_developer_mode_fallback(
        self,
        _list: mock.Mock,
        _identifiers: mock.Mock,
        _details: mock.Mock,
    ) -> None:
        devices = ios_device.discoverable_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(ios_device.device_identifier(devices[0]), "PRIVATE-DEVICE-ID")

    @mock.patch("ios_device.device_details")
    @mock.patch(
        "ios_device.developer_mode_device_identifiers",
        return_value=["PRIVATE-DEVICE-ID"],
    )
    @mock.patch("ios_device.devicectl_json")
    def test_discovery_deduplicates_coredevice_and_hardware_identifiers(
        self,
        devicectl: mock.Mock,
        _identifiers: mock.Mock,
        details: mock.Mock,
    ) -> None:
        listed = fake_device(identifier="PRIVATE-DEVICE-ID")
        listed["identifier"] = "PRIVATE-COREDEVICE-ID"
        devicectl.return_value = {"result": {"devices": [listed]}}
        details.return_value = fake_device(identifier="PRIVATE-DEVICE-ID")
        devices = ios_device.discoverable_devices()
        self.assertEqual(len(devices), 1)
        details.assert_not_called()

    @mock.patch("ios_device.device_details", return_value=fake_device())
    @mock.patch(
        "ios_device.developer_mode_device_identifiers",
        return_value=["PRIVATE-DEVICE-ID"],
    )
    @mock.patch("ios_device.devicectl_json")
    def test_discovery_replaces_stale_list_entry_with_direct_details(
        self,
        devicectl: mock.Mock,
        _identifiers: mock.Mock,
        details: mock.Mock,
    ) -> None:
        stale = fake_device(
            pairing="unpaired",
            transport="wired",
            tunnel="disconnected",
        )
        devicectl.return_value = {"result": {"devices": [stale]}}
        devices = ios_device.discoverable_devices()
        self.assertTrue(ios_device.device_summary(devices[0])["available"])
        details.assert_called_once_with("PRIVATE-DEVICE-ID")


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

    @mock.patch("ios_device.runner_cache_available", return_value=True)
    @mock.patch(
        "ios_device.lock_state",
        return_value={"passcodeRequired": True, "unlockedSinceBoot": False},
    )
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    def test_common_doctor_reports_passcoded_first_unlock_gate(
        self,
        _device: mock.Mock,
        _lock: mock.Mock,
        _cache: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self.config(Path(directory))
            document = ios_device.common_doctor_document(config, [])
        self.assertFalse(document["ready"])
        self.assertEqual(document["states"]["connection"], "ready")
        self.assertEqual(document["states"]["interaction"], "protected")
        self.assertEqual(document["states"]["runner"], "unavailable")
        self.assertEqual(
            document["extensions"]["interactionGate"],
            "manual_first_unlock_required",
        )

    @mock.patch("ios_device.runner_cache_available", return_value=True)
    @mock.patch("ios_device.lock_state", side_effect=ios_device.TestbedError("busy"))
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    def test_common_doctor_preserves_connection_when_lock_state_is_unavailable(
        self,
        _device: mock.Mock,
        _lock: mock.Mock,
        _cache: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = ios_device.common_doctor_document(
                self.config(Path(directory)), []
            )
        self.assertFalse(document["ready"])
        self.assertEqual(document["states"]["connection"], "ready")
        self.assertEqual(document["states"]["interaction"], "unknown")
        self.assertEqual(
            document["extensions"]["interactionGate"], "unverified"
        )
        self.assertFalse(document["extensions"]["lockState"]["observed"])

    @mock.patch("ios_device.release_lease")
    @mock.patch("ios_device.acquire_lease")
    @mock.patch("ios_device.stop_daemon")
    @mock.patch("ios_device.devicectl_json", return_value={"result": {}})
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    @mock.patch(
        "ios_device.wait_for_reboot_effect",
        return_value=(
            fake_device(),
            {"passcodeRequired": False, "unlockedSinceBoot": True},
        ),
    )
    def test_reboot_observes_disconnect_and_reconnect_without_builtin_wait(
        self,
        wait: mock.Mock,
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
            with redirect_stdout(io.StringIO()):
                result = ios_device.reboot_device(self.config(Path(directory)), 90)
        self.assertEqual(result, 0)
        self.assertNotIn("--wait-for-device", devicectl.call_args.args[0])
        self.assertIn("90", devicectl.call_args.args[0])
        wait.assert_called_once()

    @mock.patch("ios_device.release_lease")
    @mock.patch("ios_device.acquire_lease")
    @mock.patch("ios_device.stop_daemon")
    @mock.patch("ios_device.devicectl_json", return_value={"result": {}})
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    @mock.patch(
        "ios_device.wait_for_reboot_effect",
        return_value=(
            fake_device(),
            {"passcodeRequired": True, "unlockedSinceBoot": False},
        ),
    )
    def test_reboot_succeeds_with_passcoded_manual_first_unlock(
        self,
        _wait: mock.Mock,
        _device: mock.Mock,
        _devicectl: mock.Mock,
        _stop: mock.Mock,
        acquire: mock.Mock,
        _release: mock.Mock,
    ) -> None:
        acquire.return_value = ios_device.Lease(
            "token", 1, "controller", "command", "session", "now"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with redirect_stdout(output):
                result = ios_device.reboot_device(
                    self.config(Path(directory)), 90
                )
        self.assertEqual(result, 0)
        self.assertIn("manual first unlock required", output.getvalue())

    @mock.patch(
        "ios_device.lock_state",
        return_value={"passcodeRequired": True, "unlockedSinceBoot": False},
    )
    @mock.patch("ios_device.discover_selected_device", return_value=fake_device())
    @mock.patch("ios_device.discover_listed_device")
    def test_reboot_effect_accepts_passcoded_manual_unlock_gate(
        self,
        listed: mock.Mock,
        _device: mock.Mock,
        _lock: mock.Mock,
    ) -> None:
        listed.side_effect = [ios_device.TestbedError("gone")]
        tick = iter((0.0, 0.1, 0.2))
        with tempfile.TemporaryDirectory() as directory:
            device, locked = ios_device.wait_for_reboot_effect(
                self.config(Path(directory)),
                "PRIVATE-DEVICE-ID",
                10,
                clock=lambda: next(tick),
                sleeper=lambda _seconds: None,
            )
        self.assertEqual(ios_device.device_identifier(device), "PRIVATE-DEVICE-ID")
        self.assertTrue(locked["passcodeRequired"])

    @mock.patch("ios_device.wait_for_pairing", return_value=fake_device())
    @mock.patch("ios_device.devicectl_json", return_value={"result": {}})
    @mock.patch(
        "ios_device.discoverable_devices",
        return_value=[
            fake_device(pairing="unpaired", transport="wired", tunnel="disconnected")
        ],
    )
    def test_pair_supports_unpaired_exact_device(
        self,
        _devices: mock.Mock,
        devicectl: mock.Mock,
        wait: mock.Mock,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stdout(io.StringIO()):
                result = ios_device.pair_device(self.config(Path(directory)), 30)
        self.assertEqual(result, 0)
        self.assertEqual(devicectl.call_args.args[0][:2], ["manage", "pair"])
        wait.assert_called_once_with("PRIVATE-DEVICE-ID", 30)

    def test_pair_requires_explicit_device_selector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = ios_device.Config(
                **{
                    **self.config(Path(directory)).__dict__,
                    "device_selector": "",
                }
            )
            with self.assertRaisesRegex(ios_device.TestbedError, "exact phone"):
                ios_device.pair_device(config, 30)

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

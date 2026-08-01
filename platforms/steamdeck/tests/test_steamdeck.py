from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import steamdeck


class ManifestTests(unittest.TestCase):
    def write_manifest(self, root: Path, **overrides: object) -> Path:
        payload = root / "build" / "linux"
        payload.mkdir(parents=True)
        data: dict[str, object] = {
            "schema": steamdeck.MANIFEST_SCHEMA,
            "game_id": "example_game",
            "payload": "build/linux",
            "argv": ["./ExampleGame", "--windowed"],
            "env": {"EXAMPLE": "1"},
            "runtime": None,
            "force_appid": "",
        }
        data.update(overrides)
        path = root / "steamdeck.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_relative_payload_is_resolved_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = steamdeck.load_manifest(str(self.write_manifest(root)))
            self.assertEqual(manifest.payload, (root / "build" / "linux").resolve())
            self.assertEqual(manifest.game_id, "example_game")

    def test_manifest_rejects_project_specific_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_manifest(root, asset_pack="assets.zip")
            with self.assertRaisesRegex(steamdeck.TestbedError, "asset_pack"):
                steamdeck.load_manifest(str(path))

    def test_manifest_requires_safe_relative_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_manifest(root, argv=["../outside"])
            with self.assertRaisesRegex(steamdeck.TestbedError, "payload-relative"):
                steamdeck.load_manifest(str(path))

    def test_registration_omits_compat_tool_for_native_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = steamdeck.load_manifest(str(self.write_manifest(root)))
            registration = manifest.registration("/home/deck/devkit-game/example_game")
            self.assertEqual(registration["settings"], {"steam_play": "0"})

    def test_registration_selects_explicit_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self.write_manifest(root, runtime="SteamLinuxRuntime_4")
            manifest = steamdeck.load_manifest(str(path))
            registration = manifest.registration("/home/deck/devkit-game/example_game")
            self.assertEqual(
                registration["settings"]["compat_tool"], "SteamLinuxRuntime_4"
            )


class UploadValidationTests(unittest.TestCase):
    def test_accepts_managed_game_directory(self) -> None:
        result = steamdeck.validate_upload_directory(
            {"user": "deck", "directory": "/home/deck/devkit-game/example_game"},
            "example_game",
            "deck",
        )
        self.assertEqual(result, "/home/deck/devkit-game/example_game")

    def test_rejects_directory_outside_account_home(self) -> None:
        with self.assertRaisesRegex(steamdeck.TestbedError, "outside"):
            steamdeck.validate_upload_directory(
                {"user": "deck", "directory": "/tmp/example_game"},
                "example_game",
                "deck",
            )

    def test_rejects_different_game_directory(self) -> None:
        with self.assertRaisesRegex(steamdeck.TestbedError, "unexpected"):
            steamdeck.validate_upload_directory(
                {"user": "deck", "directory": "/home/deck/devkit-game/other"},
                "example_game",
                "deck",
            )


class ConfigurationTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {}, clear=True)
    def test_defaults_to_private_ssh_alias(self) -> None:
        deck = steamdeck.SteamDeck()
        self.assertEqual(deck.target, "steamdeck")
        self.assertEqual(deck.remote_user, "deck")
        self.assertIn("StrictHostKeyChecking=yes", deck.ssh_options)


class RegistrationResponseTests(unittest.TestCase):
    @mock.patch.dict(
        os.environ,
        {"STEAMDECK_HOST": "example.invalid", "STEAMDECK_USER": "deck"},
        clear=True,
    )
    @mock.patch("steamdeck.subprocess.run")
    def test_empty_success_payload_is_accepted(self, run: mock.Mock) -> None:
        run.return_value = mock.Mock(returncode=0, stdout='{"success": ""}\n')
        deck = steamdeck.SteamDeck()
        manifest = steamdeck.GameManifest(
            path=Path("generated.json"),
            game_id="example_game",
            payload=Path("payload"),
            argv=["./ExampleGame"],
            env={},
            runtime=None,
            force_appid="",
        )
        deck.register(manifest, "/home/deck/devkit-game/example_game")


if __name__ == "__main__":
    unittest.main()

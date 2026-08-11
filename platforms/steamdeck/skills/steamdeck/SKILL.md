---
name: steamdeck
description: Diagnose and control a physical Steam Deck through Valve's SteamOS Devkit SSH path, including status and doctor checks, power and panel control, staged Linux game upload, Devkit registration and launch, file transfer, and explicit remote commands. Use when Codex is asked to deploy, test, inspect, recover, or operate Steam Deck or SteamOS hardware from a development project.
---

# Steam Deck Testbed

Use the public testbed CLI for device transport and lifecycle. Keep compiling,
assets, game-specific launch policy, persistence, and acceptance assertions in
the consuming project.

Tool path: `~/code/machine-control/platforms/steamdeck/bin/steamdeck`

## Start safely

1. Run `steamdeck doctor` before mutating the device.
2. Use `steamdeck status` or `power-status` to distinguish connectivity,
   Steam/Gamescope session, and panel state.
3. Do not relax host-key checking, enable unrestricted SSH, unlock the SteamOS
   root filesystem, change passwords, or use root access.
4. Do not build the project inside this repository. Build a Linux x86_64 game
   in its owner and pass the staged directory through a manifest.

## Deploy a game

Read the consuming project's instructions first. Find or create a project-owned
manifest with this contract:

```json
{
  "schema": "steamdeck-testbed.game.v1",
  "game_id": "example_game",
  "payload": "build/linux-x86_64",
  "argv": ["./ExampleGame"],
  "env": {},
  "runtime": null,
  "force_appid": ""
}
```

Resolve `payload` relative to the manifest. Choose `runtime` in the project;
use `null` for the Deck's native userspace or an explicit compatibility tool
such as `SteamLinuxRuntime_4` when the build requires it.

```bash
steamdeck install path/to/steamdeck.json
steamdeck launch example_game
```

Use `register MANIFEST` to change launch settings without uploading. Do not
invent a process-name kill. If the game owns a safe stop command, invoke that
explicitly with `steamdeck exec -- ...`.

## Operate the hardware

```bash
steamdeck probe
steamdeck status --json
steamdeck power-status
steamdeck screen-on
steamdeck screen-off
steamdeck screen-shortcut install
steamdeck push LOCAL REMOTE
steamdeck pull REMOTE [LOCAL]
steamdeck shell
```

Turn the internal panel on before interactive play, compositor screenshots, or
presentation measurements. `screen-off` leaves SteamOS and SSH running and
arms the next mapped Deck button to restore the panel. `screen-on` over SSH is
the fallback recovery path.

## Diagnose failures

Run `steamdeck doctor --json` and preserve its distinctions:

- SSH failure: confirm Wi-Fi/address and private SSH configuration.
- Missing Devkit utilities: pair the host with SteamOS Devkit Client again.
- Non-Gamescope session: return the Deck to Gaming Mode before launch or panel
  control.
- Disabled panel: use `steamdeck screen-on`; do not suspend or reboot merely to
  restore the display.

Read `README.md` only when changing setup, manifest details, environment
overrides, or the public command contract.

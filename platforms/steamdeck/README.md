# Steam Deck Testbed

`steamdeck-testbed` is a small, project-neutral CLI for diagnosing and driving
a physical Steam Deck over Valve's SteamOS Devkit SSH path. It can deploy an
already-built Linux game from macOS or Linux, register it as a Devkit Game,
launch it in Gaming Mode, inspect power/session state, and control the built-in
panel without modifying SteamOS's read-only system image.

This directory is the canonical public source. The former
`steamdeck-testbed` repository is retained only as legacy history and a
possible future generated distribution.

The consuming project owns its build. A Unity project can stage a Linux x86_64
player, a Rust project can stage a Steam Runtime build, and both use the same
deployment manifest and device transport.

Building the Linux player on macOS is a supported Unity workflow: install the
matching Linux Build Support module for the Editor, select Linux x86_64 in the
project's Build Profile, and point this testbed at the resulting player
directory. Unity's Linux IL2CPP cross-compiler also supports producing Linux
players from the other standalone Editor platforms. See Unity's
[Linux IL2CPP cross-compiler documentation](https://docs.unity3d.com/6000.0/Documentation/Manual/linux-il2cpp-crosscompiler.html).

## Prerequisites

1. Enable Developer Mode on the Deck.
2. Use **Settings > Developer > Pair new host** with Valve's SteamOS Devkit
   Client once.
3. Authorize the development machine's SSH public key for the `deck` user.
4. Configure an SSH host named `steamdeck` with strict host-key checking.
5. Install Python 3.10+, OpenSSH, and `rsync` on the development machine.

Example private SSH configuration:

```sshconfig
Host steamdeck
    HostName <current-device-address>
    User deck
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Do not commit the address, private key, or local overrides here.

## Quick start

```bash
~/code/machine-control/platforms/steamdeck/bin/steamdeck doctor
~/code/machine-control/platforms/steamdeck/bin/steamdeck status
~/code/machine-control/platforms/steamdeck/bin/steamdeck power-status
```

Override the SSH alias without changing the repository:

```bash
STEAMDECK_HOST=192.0.2.10 \
STEAMDECK_USER=deck \
STEAMDECK_KEY=~/.ssh/id_ed25519 \
  bin/steamdeck doctor
```

## Deploy a game

Create a tracked manifest in the consuming project. Paths are resolved
relative to the manifest:

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

Then install and launch it:

```bash
bin/steamdeck install path/to/steamdeck.json
bin/steamdeck launch example_game
```

`install` asks the Devkit utilities for the managed upload directory,
validates that it belongs to the `deck` account and requested game ID, performs
an incremental clean upload, and registers the command, environment, and
compatibility runtime. Set `runtime` to a Devkit compatibility tool such as
`SteamLinuxRuntime_4` only when the project chooses that runtime.

Use `register MANIFEST` to update launch settings without uploading again.
The CLI deliberately has no generic process-name kill command. Projects that
need iterative stop semantics should ship an ownership-aware stop command and
invoke it through `steamdeck exec -- ...`.

## Device commands

```text
probe                         Print one stable session state for inventories
status [--json]               Query SteamOS and the active session
doctor [--json]               Check local tools, SSH, Devkit, Steam, and panel
power-status                  Report AC, suspend timers, Gamescope, and panel
screen-off | screen-on        Sleep or wake only the built-in panel
screen-shortcut install       Register a Gaming Mode screen-off shortcut
prepare-upload GAME_ID        Print the validated managed upload directory
install MANIFEST              Upload and register a staged Linux game
register MANIFEST             Update registration without uploading
launch GAME_ID                Launch an installed Devkit Game
exec -- COMMAND [ARG...]      Run an explicit command on the Deck
push LOCAL REMOTE             Copy a file or directory to the Deck
pull REMOTE [LOCAL]           Copy a file or directory from the Deck
shell                         Open an interactive Deck SSH session
```

`screen-off` installs a one-shot, non-grabbing controller watcher before
forcing the internal connector to sleep. The next mapped Deck button restores
the panel. `screen-on` over SSH remains the recovery path. These commands do
not suspend the Deck and do not affect a docked external display.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `STEAMDECK_HOST` | `steamdeck` | SSH alias, hostname, or address |
| `STEAMDECK_USER` | SSH config | Optional explicit SSH user |
| `STEAMDECK_REMOTE_USER` | `deck` | Expected Devkit upload account |
| `STEAMDECK_KEY` | SSH config | Optional explicit private-key path |
| `STEAMDECK_CONNECT_TIMEOUT` | `10` | SSH connection timeout in seconds |
| `STEAMDECK_SSH_OPTIONS` | empty | Additional SSH options parsed like a shell |

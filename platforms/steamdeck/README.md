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

From the machine-control checkout root:

```bash
platforms/steamdeck/bin/steamdeck doctor
platforms/steamdeck/bin/steamdeck status
platforms/steamdeck/bin/steamdeck power-status
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
screensaver install           Install the native Steam Quiet Ball screensaver
screensaver configure         Change black/ball mode, diameter, gray level, speed
screensaver status            Inspect installed files and configuration
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

## Automatic OLED screensaver

Quiet Ball uses Steam's custom-screensaver support, introduced in the
[October 13, 2026 client update](https://www.steamdeck.com/en/news).
Steam owns inactivity detection, presentation, and dismissal on input. No
separate game, input grab, root change, or background idle daemon is required.

```bash
bin/machine-control --target steamdeck testbed -- screensaver install
bin/machine-control --target steamdeck testbed -- screensaver configure \
  --mode ball --size 32 --brightness 10 --speed 40
bin/machine-control --target steamdeck testbed -- screensaver configure --mode black
bin/machine-control --target steamdeck testbed -- screensaver status
```

Install writes only the owned `quiet-ball` folder under Steam's
`config/uioverrides/screensavers/`. Reinstall preserves existing configuration.
Select **quiet-ball (User Created)** under **Settings > Customization**, and
set **Start screensaver after** in Steam's power settings separately for AC
and battery operation.
Keep **Sleep after** disabled on AC if indefinite remote reachability is needed.
Installation/status reports file presence, not proof of selection or activation.
The installer does not edit Steam's live configuration or restart Steam.

The background is pure black. Ball mode draws one circle with no text, logo,
glow, or trails; black mode draws nothing and schedules no animation frames.
Invalid or unavailable configuration fails to black. Changes apply on the next
screensaver page load; dismiss and reactivate an already-running screensaver.

| Option | Default | Range and meaning |
| --- | --- | --- |
| `--mode` | `ball` | `ball` or `black` |
| `--size` | `32` | Diameter in CSS pixels, 1–512; capped at half the viewport's shorter side |
| `--brightness` | `10` | Gray channel as a percentage of full white, 0–100; zero is entirely black |
| `--speed` | `40` | Horizontal motion in CSS pixels per second, 1–200 |

Brightness changes the ball's RGB value, not panel brightness or calibrated
luminance. This screensaver keeps the display enabled and is distinct from
`screen-off`, which physically sleeps the internal panel. It is an OLED-friendly
presentation, not a guarantee against panel wear. Steam's video idle inhibitors
and its **Show screensavers when playing a game** setting still apply.

For a local interactive preview, serve `platforms/steamdeck/screensaver/` with
`python3 -m http.server --bind 127.0.0.1` and open `/preview.html`. Its sliders
affect only the preview and show the command for applying settings to the Deck.
No third-party scripts, fonts, images, or network services are used.

Validation:

```bash
cd platforms/steamdeck
python3 -m unittest discover -s tests -v
python3 -m compileall -q steamdeck.py scripts/screensaver-files.py tests
# With Playwright installed and its separate Chromium downloaded:
node tests/screensaver-browser.cjs
```

`PLAYWRIGHT_MODULE` may name an installed Playwright module. Browser checks
verify exact black output, bounded dim-ball pixels, motion, edge reflections,
resize behavior, configuration-failure fallback, and preview controls. The
browser process is closed in cleanup. Native Steam selection, preview rendering,
movement, automatic AC idle activation, and target-local keyboard dismissal
were also observed on physical SteamOS hardware. The compositor
capture contained only black and the moving gray circle; Steam scales CSS pixels
with its UI scale. Physical controller dismissal, restart persistence, and
behavior across client updates remain separate acceptance work.

## Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `STEAMDECK_HOST` | `steamdeck` | SSH alias, hostname, or address |
| `STEAMDECK_USER` | SSH config | Optional explicit SSH user |
| `STEAMDECK_REMOTE_USER` | `deck` | Expected Devkit upload account |
| `STEAMDECK_KEY` | SSH config | Optional explicit private-key path |
| `STEAMDECK_CONNECT_TIMEOUT` | `10` | SSH connection timeout in seconds |
| `STEAMDECK_SSH_OPTIONS` | empty | Additional SSH options parsed like a shell |

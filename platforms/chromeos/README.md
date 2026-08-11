# ChromeOS Testbed

This directory is the canonical public source. The former
`chromeos-testbed` repository is retained only as legacy history and a
possible future generated distribution.

## Why this exists

ChromeOS has no automation story. Android has ADB and UIAutomator. Desktop Linux has xdotool and AT-SPI2. macOS has AppleScript. ChromeOS has nothing — no public automation API, no accessibility bus, no scriptable input layer. And the OS actively fights you: every reboot returns to the profile sign-in screen, while updates can re-lock the root filesystem and reset your devtools config.

This project fills that gap. It's the missing **"ADB for the ChromeOS desktop"** — screenshots, input injection, accessibility-tree-driven UI automation, browser control, extension deployment, and APK installation, all from a single CLI over SSH. There is no SDK or build system: the development machine needs Bash, OpenSSH, and Python 3, while the Chromebook uses its built-in Python and system libraries without pip packages.

**Who it's for:**
- Developers building and testing on ChromeOS who need programmatic device control
- AI agents (like [Claude Code](https://docs.anthropic.com/en/docs/claude-code)) that need to see and interact with a Chromebook — the included [skill definition](skills/SKILL.md) lets an agent take screenshots, read UI elements, click buttons, type text, and deploy code
- Anyone tired of manually recovering their dev setup after every ChromeOS reboot and update

**How it works:** A bash CLI on your dev machine sends JSON commands over SSH to a Python client on the Chromebook. The client injects touch and keyboard events via evdev, provides an experimental virtual mouse via uinput, takes screenshots via DRM/EGL, and drives system UI automation by piggybacking on ChromeOS's built-in accessibility extensions through the Chrome DevTools Protocol — a workaround for the absent AT-SPI2 bus that makes system-level UI interaction possible at all.

---

## Initial Setup

### 1. Enable developer mode

Follow the [official instructions](https://www.chromium.org/chromium-os/developer-library/guides/device/developer-mode/) for your device. This wipes the Chromebook.

### 2. (Maybe) Set a developer password

After developer mode is enabled and you've gone through ChromeOS setup, you may need to set a password so you can log in on VT2 after reboots:

```
chromeos-setdevpasswd
```

> **Unconfirmed:** It's unclear whether this is strictly required or if chronos has a default password in developer mode. Setting it ensures you can log in on VT2.

### 3. Bootstrap SSH from VT2

Switch to VT2: **Ctrl+Alt+F2** (F2 is the right-arrow key on the top row).

Log in as `chronos` (using the dev password if you set one), then:

```bash
sudo -i
export CHROMEOS_TESTBED_CONTROLLER_PUBKEY="$(cat /path/to/id_ed25519.pub)"
curl -fsSL https://kzahel.github.io/chromeos-testbed/bootstrap.sh | bash
```

This sets up SSH on port 2223 with key auth, opens the firewall, configures
remote debugging, and—when rootfs is writable—installs an Upstart job that
starts SSH automatically after reboot. The boot timing follows ChromeOS's own
network event through the `openssh-server` job. A stateful manual start script
is retained as a fallback because ChromeOS updates may replace files under
`/etc/init`.

The controller public key is deployment inventory and is supplied explicitly;
the public bootstrap does not embed one. A post-update reinstall preserves an
existing nonempty authorized-keys file when the variable is omitted.

Switch back to the GUI: **Ctrl+Alt+F1**.

### 4. Configure SSH on your dev machine

The bootstrap output shows the Chromebook's IP. Add to `~/.ssh/config`:

```
Host chromeos-testbed
    HostName <chromebook-ip>
    Port 2223
    User root
```

### 5. Verify

```bash
bin/chromeos doctor
```

## After a Reboot

With the current bootstrap and writable rootfs, SSH and its firewall rule are
restored automatically. ChromeOS itself still waits at the profile sign-in
screen after reboot: browser automation, extensions, and Crostini are not
usable until the profile is unlocked.

```bash
bin/chromeos doctor  # Warns when no user session is active
bin/chromeos login   # Hidden prompt; logs in the selected/last-used profile
bin/chromeos doctor  # Browser checks now exercise the user session
```

For non-interactive automation, pipe the PIN from an approved secret source:

```bash
password-manager-read-command | bin/chromeos login --pin-stdin
```

Do not place the PIN in a positional argument, shell history, source file, or
agent log. The CLI intentionally rejects positional PINs. It submits one
attempt, verifies that the user vault mounted, and never retries a failed PIN.

If automatic SSH itself fails, use VT2 and the stateful fallback:

```bash
sudo -i
/mnt/stateful_partition/etc/ssh/start_sshd.sh
```

An OS update can replace the Upstart job under `/etc`; re-run bootstrap after
restoring SSH if that happens.

If `start_sshd.sh` doesn't exist, the device needs re-bootstrapping (see
Initial Setup step 3). ChromeOS documents automatic SSH as a developer feature
once rootfs verification has been removed; see its
[`openssh-server.conf.README`](https://chromium.googlesource.com/chromiumos/overlays/chromiumos-overlay/+/master/chromeos-base/chromeos-sshd-init/files/openssh-server.conf.README).

## After a ChromeOS Update

Updates replace the active root image. They can remove SSH autostart, re-enable
rootfs verification, and reset `/etc/chrome_dev.conf`. The stateful fallback,
keys, configuration, client, and post-update repair staging survive.

1. If SSH did not return, start the stateful fallback from VT2 as described
   above.
2. Run the focused, read-only audit:

   ```bash
   bin/chromeos post-update
   ```

3. Run the guided repair. It stages the checkout's current bootstrap before
   changing boot state:

   ```bash
   bin/chromeos post-update --repair
   ```

   If rootfs verification is enabled, the command asks before disabling it and
   rebooting. It stages the current bootstrap on the update-persistent stateful
   partition first. Run that staged bootstrap from VT2 after the reboot, then
   run `post-update --repair` again to activate and audit DevTools.

4. Prove the repair with a second, explicit reboot:

   ```bash
   bin/chromeos post-update --verify-reboot
   ```

   Success requires a new boot ID and a current-boot `shill-connected` entry in
   the stateful SSH startup log. This distinguishes real boot persistence from
   a listener that was only started manually.

Ordinary `doctor` also warns when ChromeOS reports an update waiting for
reboot, so physical VT2 access can be planned before the root image changes.

## Usage

```bash
bin/chromeos doctor              # Check everything
bin/chromeos post-update         # Audit/repair/prove state after an OS update
bin/chromeos smoke-test          # Exercise input, screenshots, and desktop UI
bin/chromeos diagnostics         # Collect a read-only diagnostic bundle
bin/chromeos fix-ssh             # Repair/restart the root SSH service
bin/chromeos fix-devtools        # Fix remote debugging after update
bin/chromeos screenshot          # Take screenshot
bin/chromeos tap 1746 984        # Tap center of screen
bin/chromeos type "hello"        # Type text
bin/chromeos login               # Securely prompt for and submit profile PIN
bin/chromeos shortcut ctrl t     # Keyboard shortcut
bin/chromeos shortcut enter      # Named keys also work (tab, arrows, escape, ...)
bin/chromeos vt2                 # Switch to the VT2 developer console
bin/chromeos gui                 # Return to the ChromeOS UI
bin/chromeos info                # Device info
bin/chromeos power-status        # Current idle/lid behavior
bin/chromeos shell               # SSH into device
```

### Structured output

Put `--json` before a command to receive machine-readable output:

```bash
bin/chromeos --json doctor
bin/chromeos --json targets
bin/chromeos --json desktop-find '^Settings$' --role button
bin/chromeos --json adb-status
```

Client-level commands such as `info`, `tap`, and `shortcut` already return JSON.
Administrative recovery commands remain primarily human-oriented.

### Functional verification and diagnostics

`doctor` checks infrastructure without changing the visible UI. `smoke-test`
is the stronger post-reboot verification: it captures a baseline, opens Quick
Settings with the keyboard, opens Settings with a calibrated touchscreen tap,
closes it, asserts that the initial UI was restored, and saves all evidence to
a timestamped directory under `/tmp`.

```bash
bin/chromeos doctor
bin/chromeos smoke-test
bin/chromeos smoke-test --no-ui       # Infrastructure-only variant
bin/chromeos diagnostics              # Read-only support bundle
bin/chromeos diagnostics /tmp/my-run  # Explicit output directory
```

### Reliable UI synchronization

Wait for state instead of inserting fixed sleeps:

```bash
bin/chromeos desktop-wait '^Allow$' --role button --timeout 10
bin/chromeos desktop-wait '^Settings$' --role window --absent
bin/chromeos assert-visible '^Google Chrome$' --role button
bin/chromeos target-wait 'PhysBox'
```

Use `desktop-tap` when a real touch event is important. It maps logical
`chrome.automation` coordinates to the raw touchscreen range using the
built-in display bounds, so display scaling does not need to be guessed:

```bash
bin/chromeos desktop-tap '^Settings$' --role button
```

The `mouse-*` commands use a relative virtual uinput device and cannot observe
ChromeOS pointer acceleration or the existing cursor position. They are
explicitly experimental; prefer accessibility actions, `desktop-tap`, or raw
`tap` for reliable automation.

### Android/ADB

ARCVM exposes ADB through the Chromebook-local proxy at
`127.0.0.1:5555`. The connection is not necessarily restored after a reboot,
even when the proxy is listening.

```bash
bin/chromeos adb-status
bin/chromeos adb-connect
bin/chromeos adb-authorize            # Approve the visible ChromeOS prompt
bin/chromeos install-apk app.apk
bin/chromeos install-apk app.apk --authorize
```

`install-apk` now connects and verifies the device before installing. It stops
with an actionable message when authorization is required instead of passing a
misleading failure through from `adb install`.

### Idle and closed-lid operation

Inspect the effective powerd overrides and its most recently logged policy:

```bash
bin/chromeos power-status
```

For a long-running testbed, idle suspend can be disabled independently:

```bash
bin/chromeos keep-awake
```

To keep the Chromebook running even while its lid is closed:

```bash
bin/chromeos keep-awake --lid-closed
```

This writes ChromeOS powerd's documented stateful developer overrides,
forces the embedded controller's lid state open, and restarts powerd. It
persists across ordinary reboots. Keep a closed machine ventilated and
preferably connected to AC power: the normal lid power safeguard is
intentionally disabled.

Restore stock behavior with:

```bash
bin/chromeos restore-power
```

These commands implement the procedure in the official
[ChromeOS Power Management FAQ](https://chromium.googlesource.com/chromiumos/platform2/+/main/power_manager/docs/faq.md).

## Using as a Claude Code skill

Other projects can reference the skill for ChromeOS device management. Add to your project's `CLAUDE.md`:

```
For ChromeOS device management, see
`~/code/machine-control/platforms/chromeos/skills/SKILL.md`.
```

## File structure

```
bin/chromeos               Main CLI (subcommand dispatcher)
client.py                  evdev input driver (deployed to Chromebook)
scripts/
  bootstrap.sh             One-time SSH + devtools setup (curl from VT2)
  common.sh                Shared variables and helpers
  diagnostics.sh           Read-only diagnostic bundle
  doctor.sh                Health check
  post-update.sh           Post-update audit, guided repair, and reboot proof
  fix-ssh.sh               Restart sshd after reboot
  fix-devtools.sh          Fix remote debugging after update
  deploy-client.sh         Deploy client.py to device
  smoke-test.sh            Restoring end-to-end verification
skills/SKILL.md            Claude Code skill definition
```

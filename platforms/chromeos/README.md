# ChromeOS Testbed

## Why this exists

ChromeOS has no automation story. Android has ADB and UIAutomator. Desktop Linux has xdotool and AT-SPI2. macOS has AppleScript. ChromeOS has nothing — no public automation API, no accessibility bus, no scriptable input layer. And the OS actively fights you: every reboot kills SSH, every update re-locks the root filesystem and resets your devtools config.

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
curl -fsSL https://kzahel.github.io/chromeos-testbed/bootstrap.sh | bash
```

This sets up SSH on port 2223 with key auth, opens the firewall, configures remote debugging (if rootfs is writable), and creates a persistent start script for reboots.

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

Rebooting kills sshd and resets the firewall. SSH must be restarted manually from the Chromebook:

1. Switch to VT2: **Ctrl+Alt+F2**
2. Log in as `chronos` (with your dev password)
3. Become root and start sshd:
   ```bash
   sudo -i
   cd /mnt/stateful_partition/etc/ssh && bash start_sshd.sh
   ```
4. Switch back to GUI: **Ctrl+Alt+F1**

If `start_sshd.sh` doesn't exist, the device needs re-bootstrapping (see Initial Setup step 3).
Re-bootstrap as well if the script reports that `/etc/ssh/sshd_config` is
inaccessible; current versions use a self-contained configuration on the
stateful partition.

> `bin/chromeos fix-ssh` will attempt to restart sshd over SSH, but since SSH is down after a reboot, it just prints the instructions above.

## After a ChromeOS Update

Updates re-enable rootfs verification and reset `/etc/chrome_dev.conf`, which breaks remote debugging.

1. Fix SSH first (see "After a Reboot" above)
2. Run the automated fix:
   ```bash
   bin/chromeos fix-devtools
   ```
   If rootfs is read-only, it will remove rootfs verification over SSH, reboot the device, and prompt you to restart SSH from VT2 before re-running `fix-devtools`.

## Usage

```bash
bin/chromeos doctor              # Check everything
bin/chromeos smoke-test          # Exercise input, screenshots, and desktop UI
bin/chromeos diagnostics         # Collect a read-only diagnostic bundle
bin/chromeos fix-ssh             # Fix SSH after reboot
bin/chromeos fix-devtools        # Fix remote debugging after update
bin/chromeos screenshot          # Take screenshot
bin/chromeos tap 1746 984        # Tap center of screen
bin/chromeos type "hello"        # Type text
bin/chromeos shortcut ctrl t     # Keyboard shortcut
bin/chromeos shortcut enter      # Named keys also work (tab, arrows, escape, ...)
bin/chromeos vt2                 # Switch to the VT2 developer console
bin/chromeos gui                 # Return to the ChromeOS UI
bin/chromeos info                # Device info
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

## Using as a Claude Code skill

Other projects can reference the skill for ChromeOS device management. Add to your project's `CLAUDE.md`:

```
For ChromeOS device management, see ~/code/chromeos-testbed/skills/SKILL.md
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
  fix-ssh.sh               Restart sshd after reboot
  fix-devtools.sh          Fix remote debugging after update
  deploy-client.sh         Deploy client.py to device
  smoke-test.sh            Restoring end-to-end verification
skills/SKILL.md            Claude Code skill definition
```

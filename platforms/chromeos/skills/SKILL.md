---
name: chromeos
description: Manage a ChromeOS development device — health checks, fix SSH/devtools, screenshots, desktop automation via accessibility tree
---

# ChromeOS Device Management

CLI tools for bootstrapping, troubleshooting, and controlling a ChromeOS Chromebook in developer mode.

**Tool path:** `~/code/chromeos-testbed/bin/chromeos`

## Quick Reference

```bash
chromeos doctor              # Health check — shows what's working/broken
chromeos smoke-test          # End-to-end test; saves screenshots and restores UI
chromeos diagnostics         # Collect a non-mutating support bundle
chromeos fix-ssh             # Restart sshd after reboot
chromeos fix-devtools        # Re-enable remote debugging after ChromeOS update
chromeos deploy              # Deploy/update input client on Chromebook
chromeos screenshot [file]   # Take screenshot, save locally
chromeos type "text"         # Type text
chromeos login [--pin-stdin] # Log in selected profile; hidden prompt by default
chromeos shortcut ctrl t     # Keyboard shortcut (handles modifier remapping)
chromeos info                # Device info (touch_max, keyboard layout)
chromeos deploy-ext <dir> [--name NAME] [--reload [EXT_ID]]  # Deploy extension
chromeos install-apk <file.apk> [--keep]                     # Install Android APK
chromeos adb-status          # Check ARCVM proxy and authorization state
chromeos adb-connect         # Connect to 127.0.0.1:5555 and wait for readiness
chromeos power-status        # Show effective idle/lid policy
chromeos keep-awake [--lid-closed]  # Persistently disable idle/lid suspend
chromeos restore-power       # Restore ChromeOS power defaults
chromeos shell               # Interactive SSH session
```

## Troubleshooting Decision Tree

**Start here when something isn't working:**

1. Run `chromeos doctor` — it checks everything and tells you what to fix.

2. **Can't SSH?** Current bootstrap installs an Upstart job, so SSH should
   return automatically after ordinary reboots. ChromeOS updates can remove
   that rootfs job. Use the stateful fallback from VT2:
   1. On the Chromebook, press Ctrl+Alt+F2
   2. Log in as chronos
   3. `sudo -i`
   4. `cd /mnt/stateful_partition/etc/ssh && bash start_sshd.sh`
   5. Ctrl+Alt+F1 to return to GUI
   - If start_sshd.sh doesn't exist: Device needs bootstrapping (see Setup below)

3. **DevTools port 9222 not available?**
   - `chromeos fix-devtools` — adds the flag and restarts Chrome
   - If rootfs is read-only: `fix-devtools` will offer to remove rootfs
     verification and reboot. An OS update may also have replaced the
     automatic SSH Upstart job, so physical VT2 access must be available as a
     fallback. Always confirm with the user before proceeding. Pass `-y` to
     skip the interactive prompt: `chromeos fix-devtools -y`

4. **SSH tunnel for DevTools:**
   ```bash
   ssh -NL 9222:127.0.0.1:9222 chromeos-testbed
   ```

## Common Workflows

### Post-Reboot Login

The bootstrap-installed Upstart job normally restores SSH and its firewall
rule automatically. ChromeOS remains at the profile sign-in screen until the
selected user profile is unlocked. A driver needs the profile PIN before
browser, extension, or Crostini automation can resume.

```bash
chromeos doctor            # Warns that the user session is not active
chromeos login             # Hidden interactive PIN prompt
chromeos doctor            # Verify post-login services
```

For an automation driver, pipe the PIN from an approved secret source without
printing it:

```bash
password-manager-read-command | chromeos login --pin-stdin
```

Never pass the PIN as a command argument or include it in an agent/tool log.
`chromeos login` intentionally has no positional PIN form. It acts on the
already-selected (normally last-used) profile, clears partial input, submits
only once, and verifies success by checking whether the user vault mounted.

If SSH is unreachable, use the VT2 fallback above, then re-run bootstrap to
restore future automatic startup.

### Post-Update Recovery

ChromeOS updates re-enable rootfs verification and reset chrome_dev.conf.

```bash
chromeos doctor            # See what broke
chromeos fix-devtools      # Will tell you if rootfs verification needs removal
# If rootfs is read-only, follow the manual VT2 instructions it prints
```

### Taking Screenshots

```bash
chromeos screenshot                        # Saves to /tmp/chromebook-screenshot.png
chromeos screenshot ~/Desktop/screen.png   # Custom output path
```

Use the default capture method or explicit `--method egl` for routine
screenshots. Capture wakes the display with modifier-only input before reading
the framebuffer, so callers do not need a separate key press. GBM is acceptable
only as a fallback when EGL is unavailable; it can produce severe visual
artifacts on tiled framebuffers even when capture succeeds. Visually inspect any
GBM capture before relying on it, and prefer `--method keyboard` when a native
ChromeOS screenshot is suitable.

### Deploying Extensions

```bash
# Build your extension first (project-specific), then deploy the output directory
chromeos deploy-ext dist/ --name myapp-extension

# Deploy and reload via CDP (requires SSH tunnel: ssh -NL 9222:127.0.0.1:9222 chromeos-testbed)
chromeos deploy-ext dist/ --name myapp-extension --reload abcdefghijklmnopabcdefghijklmnop

# First time: load unpacked extension at chrome://extensions from ~/Downloads/myapp-extension/
```

### Installing Android APKs

```bash
# Build your APK first, then install
chromeos install-apk app/build/outputs/apk/debug/app-debug.apk

# Keep APK in Downloads after install (default: cleaned up)
chromeos install-apk app-debug.apk --keep
```

`install-apk` automatically connects to ARCVM ADB at `127.0.0.1:5555`.
If the connection is unauthorized, approve the visible ChromeOS prompt or run:

```bash
chromeos adb-authorize
# Or explicitly permit install-apk to approve the prompt:
chromeos install-apk app-debug.apk --authorize
```

### Desktop Automation (Accessibility Tree)

**Prefer the accessibility tree over coordinate guessing.** The `desktop-find` and `desktop-action` commands let you interact with system UI elements by name/role — no fragile coordinate math needed.

```bash
# Find elements by name (regex, case-insensitive)
chromeos desktop-find "Volume"                    # All elements with "Volume" in name
chromeos desktop-find "^Volume$" --role slider    # Exact match, specific role

# Perform actions on elements
chromeos desktop-action "Toggle Volume" doDefault            # Click/activate
chromeos desktop-action "^Volume$" focus --role slider --nth 2  # Focus 2nd match
chromeos desktop-action "Settings" doDefault --role button
chromeos desktop-wait "^Settings$" --role window --timeout 10
chromeos assert-visible "^Google Chrome$" --role button

# Available actions: doDefault, focus, increment, decrement, setValue,
#   showContextMenu, scrollForward, scrollBackward, longClick

# Inspect the full desktop tree
chromeos desktop-tree --depth 4
```

**Slider pattern** (e.g. system volume): `doDefault`/`increment` don't work reliably on system UI sliders. Instead, focus the slider via the a11y tree, then use keyboard arrows:

```bash
chromeos desktop-action "^Volume$" focus --role slider --nth 2
# Then send arrow keys: Up=103, Down=108, Right=106, Left=105
chromeos shortcut up
```

**When `--nth` is needed:** Multiple elements can share the same name (e.g. a YouTube volume slider and the system volume slider). Use `desktop-find` to list matches, identify which index you need, then pass `--nth N` to `desktop-action`.

### Web Content Accessibility

For elements inside web pages (not system UI), use the per-tab commands:

```bash
chromeos targets                                   # List open tabs
chromeos axtree 0                                  # Accessibility tree for tab 0
chromeos find "Login" --role button --target 0     # Find web element
chromeos click "Login" --role button --target 0    # Click web element
```

### Keyboard and Text Input

```bash
chromeos type "hello world"
chromeos shortcut ctrl t     # New tab
chromeos shortcut ctrl w     # Close tab
chromeos shortcut alt shift s  # Open/close Quick Settings
chromeos shortcut enter      # Named keys: tab, arrows, escape, backspace, etc.
chromeos vt2                 # Physical Ctrl+Alt+F2; bypasses modifier remapping
chromeos gui                 # Physical Ctrl+Alt+F1; returns to ChromeOS UI
```

### Tap (Last Resort)

Coordinate-based tap is fragile — only use when the accessibility tree doesn't expose the target element. Prefer `desktop-action`/`desktop-click` or `click` (web content) instead.

```bash
chromeos info  # → {"touch_max": [3492, 1968], ...}
# Convert: touch_x = X% * max_x / 100, touch_y = Y% * max_y / 100
chromeos tap 2619 1673
```

For a real touch event on an accessible system element, use calibrated
`desktop-tap`. It converts the logical built-in-display coordinates to the
touchscreen's raw evdev range:

```bash
chromeos desktop-tap "^Settings$" --role button
```

The virtual `mouse-*` commands are best-effort only. The one-shot client cannot
observe ChromeOS's current cursor position or pointer acceleration. Prefer
accessibility actions or calibrated touch.

### Structured output and evidence

Use a leading `--json` for machine-readable read/query commands:

```bash
chromeos --json doctor
chromeos --json targets
chromeos --json desktop-find "Allow" --role button
```

`chromeos diagnostics` collects health, OS/device details, ADB state,
accessibility data, targets, and a screenshot without changing UI state.
`chromeos smoke-test` performs a restoring UI exercise and stores every result
and screenshot in a timestamped artifact directory.

### Power and closed-lid operation

```bash
chromeos power-status
chromeos keep-awake                 # Disable inactivity suspend
chromeos keep-awake --lid-closed    # Also ignore the lid switch
chromeos restore-power              # Undo both overrides
```

Closed-lid mode uses the stateful ChromeOS powerd developer preference and EC
override documented by ChromiumOS. It survives normal reboots. Warn the user
to keep the laptop ventilated and preferably on AC power; do not enable it
merely to inspect status.

### Extending the CLI

If a feature doesn't work or is missing (e.g. a chrome.automation action that's not supported, or a new command you need), **edit the source files directly** rather than working around limitations:

- `cdp.py` — Chrome DevTools Protocol client, desktop automation via chrome.automation
- `client.py` — On-device command handler (JSON in, JSON out over stdin/stdout)
- `bin/chromeos` — Bash CLI wrapper, argument parsing, output formatting

Changes to these files are auto-deployed to the Chromebook on next command run. The architecture is simple: `bin/chromeos` sends JSON to `client.py` over SSH, which calls `cdp.py` for accessibility/browser operations.

## Setup (First-Time)

### On the Chromebook

1. Enter developer mode ([instructions](https://chromium.googlesource.com/chromiumos/docs/+/main/developer_mode.md))
2. Switch to VT2: **Ctrl+Alt+F2**
3. Log in as `chronos`, then:
   ```
   sudo -i
   curl -fsSL https://kzahel.github.io/chromeos-testbed/bootstrap.sh | bash
   ```
4. Note the IP address and SSH port shown

### On Your Dev Machine

Add to `~/.ssh/config`:
```
Host chromeos-testbed
    HostName <chromebook-ip>
    Port 2223
    User root
```

Then verify: `chromeos doctor`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CHROMEBOOK_HOST` | `chromeos-testbed` | SSH host for the Chromebook |
| `CHROMEOS_CLIENT_PATH` | `/mnt/stateful_partition/c2/client.py` | Path to input client on device |

## What Breaks and When

| Event | What breaks | Fix |
|-------|-------------|-----|
| Reboot | User session is signed out; browser/extensions/Crostini unavailable | Wait for automatic SSH, then `chromeos login` |
| ChromeOS update | SSH boot job and chrome_dev.conf may reset; rootfs may become read-only | VT2: start stateful SSH, re-bootstrap, then `chromeos fix-devtools` |
| IP change | SSH config stale | Update `~/.ssh/config` HostName |

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
chromeos fix-ssh             # Restart sshd after reboot
chromeos fix-devtools        # Re-enable remote debugging after ChromeOS update
chromeos deploy              # Deploy/update input client on Chromebook
chromeos screenshot [file]   # Take screenshot, save locally
chromeos type "text"         # Type text
chromeos shortcut ctrl t     # Keyboard shortcut (handles modifier remapping)
chromeos info                # Device info (touch_max, keyboard layout)
chromeos deploy-ext <dir> [--name NAME] [--reload [EXT_ID]]  # Deploy extension
chromeos install-apk <file.apk> [--keep]                     # Install Android APK
chromeos shell               # Interactive SSH session
```

## Troubleshooting Decision Tree

**Start here when something isn't working:**

1. Run `chromeos doctor` — it checks everything and tells you what to fix.

2. **Can't SSH?** SSH must be restarted manually from VT2 after every reboot:
   1. On the Chromebook, press Ctrl+Alt+F2
   2. Log in as chronos
   3. `sudo -i`
   4. `cd /mnt/stateful_partition/etc/ssh && bash start_sshd.sh`
   5. Ctrl+Alt+F1 to return to GUI
   - If start_sshd.sh doesn't exist: Device needs bootstrapping (see Setup below)

3. **DevTools port 9222 not available?**
   - `chromeos fix-devtools` — adds the flag and restarts Chrome
   - If rootfs is read-only: `fix-devtools` will offer to remove rootfs verification and reboot. **This requires a reboot, which kills SSH. The user must have physical access to the Chromebook to restart SSH from VT2 afterward.** Always confirm with the user before proceeding. Pass `-y` to skip the interactive prompt: `chromeos fix-devtools -y`

4. **SSH tunnel for DevTools:**
   ```bash
   ssh -NL 9222:127.0.0.1:9222 chromeos-testbed
   ```

## Common Workflows

### Post-Reboot Recovery

ChromeOS reboots reset firewall rules and stop sshd.

```bash
chromeos fix-ssh           # Restarts sshd remotely
chromeos doctor            # Verify everything else is OK
```

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
| Reboot | sshd stops, firewall resets | `chromeos fix-ssh` |
| ChromeOS update | Rootfs goes read-only, chrome_dev.conf reset | VT2: remove rootfs verification, reboot, then `chromeos fix-devtools` |
| IP change | SSH config stale | Update `~/.ssh/config` HostName |

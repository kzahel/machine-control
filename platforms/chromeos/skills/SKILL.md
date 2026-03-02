---
name: chromeos
description: Manage a ChromeOS development device — health checks, fix SSH/devtools after reboots, screenshots, touchscreen input
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
chromeos tap X Y             # Tap at raw touchscreen coordinates
chromeos type "text"         # Type text
chromeos shortcut ctrl t     # Keyboard shortcut (handles modifier remapping)
chromeos info                # Device info (touch_max, keyboard layout)
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
   - If rootfs is read-only: `fix-devtools` will remove rootfs verification and reboot (then SSH must be restarted from VT2 before running `fix-devtools` again)

4. **SSH tunnel for DevTools:**
   ```bash
   ssh -L 9222:127.0.0.1:9222 chromeos-testbed
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

### Input Injection

```bash
# Get device info first (touch coordinate range)
chromeos info
# Example output: {"touch_max": [3492, 1968], ...}

# Tap using visual estimation:
# 1. Take a screenshot
# 2. Estimate target position as percentage (X%, Y%)
# 3. Convert: touch_x = X% * max_x / 100, touch_y = Y% * max_y / 100
chromeos tap 2619 1673     # ~75% across, ~85% down on 3492x1968 screen

chromeos type "hello world"
chromeos shortcut ctrl t   # New tab
chromeos shortcut ctrl w   # Close tab
```

## Setup (First-Time)

### On the Chromebook

1. Enter developer mode ([instructions](https://chromium.googlesource.com/chromiumos/docs/+/main/developer_mode.md))
2. Switch to VT2: **Ctrl+Alt+F2**
3. Log in as `chronos`, then:
   ```
   sudo -i
   curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash
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

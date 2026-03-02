# ChromeOS Testbed

CLI tools for bootstrapping and managing ChromeOS devices in developer mode. Handles SSH setup, Chrome DevTools remote debugging, screenshots, and input injection — and fixes things that break after ChromeOS updates and reboots.

## Quick Start

### 1. Bootstrap the Chromebook

Put the Chromebook in [developer mode](https://chromium.googlesource.com/chromiumos/docs/+/main/developer_mode.md), then on VT2 (Ctrl+Alt+F2):

```bash
sudo bash
curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash
```

### 2. Configure SSH on your dev machine

Add to `~/.ssh/config`:

```
Host chromeos-testbed
    HostName <chromebook-ip>
    Port 2223
    User root
```

### 3. Verify

```bash
bin/chromeos doctor
```

## Usage

```bash
bin/chromeos doctor              # Check everything
bin/chromeos fix-ssh             # Fix SSH after reboot
bin/chromeos fix-devtools        # Fix remote debugging after update
bin/chromeos screenshot          # Take screenshot
bin/chromeos tap 1746 984        # Tap center of screen
bin/chromeos type "hello"        # Type text
bin/chromeos shortcut ctrl t     # Keyboard shortcut
bin/chromeos info                # Device info
bin/chromeos shell               # SSH into device
```

## What breaks and when

| Event | What breaks | Fix |
|-------|-------------|-----|
| **Reboot** | sshd stops, firewall resets | `chromeos fix-ssh` |
| **ChromeOS update** | Rootfs goes read-only, chrome_dev.conf reset | Disable rootfs verification from VT2, reboot, then `chromeos fix-devtools` |
| **IP change** | SSH config stale | Update HostName in `~/.ssh/config` |

## Using as a Claude Code skill

Other projects can reference the skill for ChromeOS device management. Add to your project's `CLAUDE.md`:

```
For ChromeOS device management, see ~/code/chromeos-testbed/skills/chromeos/SKILL.md
```

## File structure

```
bin/chromeos               Main CLI (subcommand dispatcher)
client.py                  evdev input driver (deployed to Chromebook)
scripts/
  bootstrap.sh             One-time SSH + devtools setup (curl from VT2)
  doctor.sh                Health check
  fix-ssh.sh               Restart sshd after reboot
  fix-devtools.sh          Fix remote debugging after update
  deploy-client.sh         Deploy client.py to device
skills/chromeos/SKILL.md   Claude Code skill definition
```

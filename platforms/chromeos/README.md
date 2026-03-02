# ChromeOS Testbed

CLI tools for bootstrapping and managing ChromeOS devices in developer mode. Handles SSH setup, Chrome DevTools remote debugging, screenshots, and input injection — and fixes things that break after ChromeOS updates and reboots.

## Initial Setup

### 1. Enable developer mode

Follow the [official instructions](https://chromium.googlesource.com/chromiumos/docs/+/main/developer_mode.md) for your device. This wipes the Chromebook.

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
curl -sL kyle.graehl.org/chromeos-testbed/bootstrap.sh | bash
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

Rebooting kills sshd and resets the firewall. From your dev machine, try:

```bash
bin/chromeos fix-ssh
```

If that fails (SSH isn't up yet), fix it manually from the Chromebook:

1. Switch to VT2: **Ctrl+Alt+F2**
2. Log in as `chronos` (with your dev password)
3. Become root and start sshd:
   ```bash
   sudo -i
   cd /mnt/stateful_partition/etc/ssh
   bash start_sshd.sh
   ```
4. Switch back to GUI: **Ctrl+Alt+F1**

If `start_sshd.sh` doesn't exist, the device needs re-bootstrapping (see Initial Setup step 3).

## After a ChromeOS Update

Updates re-enable rootfs verification and reset `/etc/chrome_dev.conf`, which breaks remote debugging. SSH should still work after running `fix-ssh`.

1. Fix SSH first (see "After a Reboot" above)
2. Try the automated fix:
   ```bash
   bin/chromeos fix-devtools
   ```
3. If that fails because rootfs is read-only, fix manually from VT2:
   ```bash
   sudo -i
   /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification --partitions 4
   reboot
   ```
4. After reboot, start sshd again (see "After a Reboot"), then:
   ```bash
   bin/chromeos fix-devtools
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
  doctor.sh                Health check
  fix-ssh.sh               Restart sshd after reboot
  fix-devtools.sh          Fix remote debugging after update
  deploy-client.sh         Deploy client.py to device
skills/SKILL.md            Claude Code skill definition
```

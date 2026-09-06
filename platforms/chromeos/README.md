# ChromeOS Testbed

This directory is the canonical public source. The former
`chromeos-testbed` repository is retained only as legacy history and a
possible future generated distribution.

## Why this exists

ChromeOS has no automation story. Android has ADB and UIAutomator. Desktop Linux has xdotool and AT-SPI2. macOS has AppleScript. ChromeOS has nothing — no public automation API, no accessibility bus, no scriptable input layer. And the OS actively fights you: every reboot returns to the profile sign-in screen, while updates can re-lock the root filesystem and reset your devtools config.

This project fills that gap. It's the missing **"ADB for the ChromeOS desktop"** — screenshots, input injection, accessibility-tree-driven UI automation, browser control, extension deployment, and APK installation, all from a single CLI over SSH. There is no SDK or build system: the development machine needs Bash, OpenSSH, and Python 3, while the Chromebook uses Python from ChromeOS developer packages and system libraries without pip packages.

**Who it's for:**
- Developers building and testing on ChromeOS who need programmatic device control
- AI agents (like [Claude Code](https://docs.anthropic.com/en/docs/claude-code)) that need to see and interact with a Chromebook — the included [skill definition](skills/SKILL.md) lets an agent take screenshots, read UI elements, click buttons, type text, and deploy code
- Anyone tired of manually recovering their dev setup after every ChromeOS reboot and update

**How it works:** A bash CLI on your dev machine sends JSON commands over SSH to a Python client on the Chromebook. The client injects touch and keyboard events via evdev, provides an experimental virtual mouse via uinput, takes screenshots via DRM/EGL, and drives system UI automation by piggybacking on ChromeOS's built-in accessibility extensions through the Chrome DevTools Protocol — a workaround for the absent AT-SPI2 bus that makes system-level UI interaction possible at all.

---

## Initial setup on a new Chromebook

Use a dedicated test device with Developer Mode already enabled. Enabling
Developer Mode erases local user data; follow the device's
[official instructions](https://www.chromium.org/chromium-os/developer-library/guides/device/developer-mode/)
before starting here. Connect the Chromebook to Wi-Fi and power. The controller
needs this repository, Bash, OpenSSH, and Python 3.10 or later.

### 1. Download and run from VT2

Press **Ctrl+Alt+Forward (F2)**, log in as `chronos`, and run `sudo -i`.
If console login requires a developer password, use the password configured
on that device; the bootstrap does not change console passwords.

From the root shell, these commands work verbatim:

```bash
curl -fSL https://raw.githubusercontent.com/kzahel/machine-control/main/platforms/chromeos/scripts/bootstrap.sh -o /mnt/stateful_partition/bootstrap.sh
bash /mnt/stateful_partition/bootstrap.sh
```

Only run the second command after a successful download. GitHub hosts only
this script; setup never looks up your account or downloads SSH keys.
Existing SSH authorized keys on the Chromebook are preserved and reused.

For a brand-new device, an SSH public key from your laptop must first be
supplied through `CHROMEOS_TESTBED_CONTROLLER_PUBKEY`, or packaged locally
with `scripts/prepare-bootstrap.py` (see the local development workflow below).
The plain GitHub download does not contain your laptop's key and stops with
a clear message if none is installed. Never supply or upload a private key.

The script prompts for approval of the dedicated-appliance configuration.
For an already-authorized unattended installation with a key installed, use
`bash /mnt/stateful_partition/bootstrap.sh --yes`.
GitHub's `main` URL follows the latest source; replace `main` with a reviewed
commit SHA to pin a version.

The approved setup installs key-only root SSH on port 2223, Python developer
bootstrap packages, DevTools configuration, and persistent idle/lid-suspend
inhibition. It also authorizes the controller to enable Select-to-speak for
desktop accessibility and verify automatic SSH with a reboot.

When the rootfs is read-only, setup validates the active A/B partition,
disables its rootfs verification, saves progress on the stateful partition,
and reboots. A pending OS update is booted first. It never enables Developer
Mode or powerwashes the device. The final result block reports the current
phase and next step; a required reboot is a resumable phase, not a completed
installation.

### 2. Restore SSH after the preparation reboot, if needed

Return to VT2, log in as `chronos`, run `sudo -i`, then use the familiar command:

```bash
bash /mnt/stateful_partition/etc/ssh/start_sshd.sh
```

This restores the connection. It does not have to finish installation itself.
The controller resumes the saved setup in the next step. You can also rerun
`bash /mnt/stateful_partition/bootstrap.sh`; both paths are supported.
Ordinary reboots after completed setup require neither command.

### 3. Finish from the controller

Use the Chromebook IP shown in the result block to add a distinct SSH alias
to the controller's `~/.ssh/config`:

```sshconfig
Host my-chromebook
    HostName <chromebook-ip>
    Port 2223
    User root
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

Select that alias and run the setup command from the repository root:

```bash
export CHROMEBOOK_HOST=my-chromebook
./platforms/chromeos/bin/chromeos setup
```

Setup first checks the controller route and authenticated SSH. SSH may ask you
to trust the new device's host key. Approval recorded by the VT2 setup is reused
until installation completes, so a reboot or interrupted connection does not
require approving the same setup again. For unattended controllers,
`setup --yes` approves setup and accepts previously unknown host keys; changed
host keys are still refused.

This command stages the current bootstrap, resumes image preparation if
necessary, deploys the client, waits for DevTools, proves automatic SSH startup,
enables and verifies desktop accessibility, and runs doctor plus the UI smoke
test. Sign in normally on the Chromebook when asked. It waits up to 180 seconds
at each physical recovery/sign-in step; use `--wait-timeout SECONDS` to change
that. On timeout it exits with status 2 and a resume instruction. Rerun the
same `chromeos setup` command after completing the requested physical step.
Passwords and PINs are never collected by setup.

`SETUP COMPLETE` means the final checks passed. Status is saved in
`/mnt/stateful_partition/etc/ssh/setup-state`; the approval receipt is removed
on completion. Device identity and SSH aliases belong in your private inventory.
For registered targets, the equivalent common entry is
`machine-control --target YOUR_TARGET testbed -- setup`.

### Controller routing and VPNs

Both endpoints need a working route to the other for controller-hosted
bootstrap development: Chromebook → controller HTTP, and controller → Chromebook
SSH. A successful curl download or diagnostic POST proves only the first
connection. The standard GitHub URL needs internet access and no LAN HTTP server;
SSH still needs a route to the Chromebook.

If SSH times out, run the read-only preflight before changing the target:

```bash
./platforms/chromeos/bin/chromeos network-check
```

It resolves the SSH alias, reports the controller route, and attempts an
actual authenticated SSH connection. For a Chromebook on your current LAN,
check that a VPN is not taking that local subnet. Tailscale exit-node mode
with local LAN access disabled can cause exactly this symptom. Enable local
LAN access in the exit-node settings or temporarily disconnect the VPN, then
rerun the preflight. A VPN route may be intentional for a remote target;
the tool reports it and never changes VPN settings or firewall rules.

### Diagnostics and development downloads

Bootstrap ends with a compact `BOOTSTRAP RESULT` block: local SSH handshake,
listener, first INPUT rule, Python, power/rootfs state, and setup phase. Local
success is separate from controller reachability. Detailed output is saved
with private permissions in `/mnt/stateful_partition/etc/ssh/bootstrap.log`
and `bootstrap-report.txt`. Photograph the final result block if needed.

Local HTTP serving is only for testing unpublished bootstrap changes.
`scripts/prepare-bootstrap.py PUBLIC_KEY OUTPUT` packages the local script and
one controller public key. Serve only its temporary directory on a trusted
LAN, verify the controller's current LAN address, and stop the server afterward.
The optional `--report-url URL` sends private device/network diagnostics to
an explicit controller-owned HTTP(S) POST endpoint. A normal
`python3 -m http.server` does not accept that POST. No report upload occurs by
default; never put generated bundles, reports, or private endpoints in Git.

`bootstrap.sh --repair-only` is for the existing maintenance workflow. It
installs what the active image permits and never disables verification or
reboots. First-time users should use the default guided setup instead.

## After a Reboot

With the current bootstrap and writable rootfs, SSH, its firewall rule, and the
required closed-lid power policy are restored automatically. ChromeOS itself
still waits at the profile sign-in screen after reboot: browser automation,
extensions, and Crostini are not usable until the profile is unlocked.

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
bash /mnt/stateful_partition/etc/ssh/start_sshd.sh
```

An OS update can replace the Upstart job under `/etc`; re-run bootstrap after
restoring SSH if that happens.

If `start_sshd.sh` doesn't exist, the device needs re-bootstrapping (see
Initial setup step 1). ChromeOS documents automatic SSH as a developer feature
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

### Common readiness and maintenance

From the repository root, use the common entry for portable observation and
bounded maintenance:

```bash
bin/machine-control --target chromeos target status
bin/machine-control --target chromeos target doctor
bin/machine-control --target chromeos target capabilities
bin/machine-control --target chromeos maintenance capabilities
bin/machine-control --target chromeos maintenance audit --profile runtime
bin/machine-control --target chromeos maintenance repair --profile runtime
```

The common doctor distinguishes SSH reachability, active-image rootfs
verification, automatic startup evidence from the current boot, required
closed-lid availability, profile lock, and target-native
semantics/capture/input. The minimized
`rootfs_verification` check and `rootfsVerification` extension report
`disabled`, `enabled`, or `unknown` without exposing a device or partition.
After a reboot, maintenance can be healthy while ordinary desktop readiness is
false because ChromeOS is waiting at profile sign-in.

`maintenance repair --reboot` is the explicit proof-reboot composition. It is
accepted only on an already safe active image and succeeds only after SSH
returns on a changed boot with automatic current-boot evidence. If an update is
waiting or rootfs verification is enabled, common repair returns
`guided_recovery_required` without changing boot state. Use the existing
`post-update --repair` VT2 workflow for that boundary.

This evidence starts after ChromeOS boots. A laptop that fully loses power may
remain physically off; software SSH autostart cannot make a powered-off device
turn itself on. Closed-lid operation deliberately removes the normal thermal
and battery safeguard, so keep the appliance ventilated and preferably on AC.

## Usage

```bash
bin/chromeos doctor              # Check routine health without probing ADB
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
The root `machine-control` entry always emits its common structured contracts.

### Functional verification and diagnostics

`doctor` checks routine infrastructure without changing the visible UI or
executing ADB. `diagnostics` likewise records only passive ADB command, server,
and proxy availability. `smoke-test` is the stronger post-reboot verification:
it captures a baseline, opens Quick Settings with the keyboard, opens Settings
with a calibrated touchscreen tap, closes it, asserts that the initial UI was
restored, and saves all evidence to a timestamped directory under `/tmp`.

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
`chrome.automation` coordinates to the touchscreen range using the built-in
display bounds, then injects through an isolated virtual direct-input device.
Display scaling does not need to be guessed, and physical contacts cannot join
the injected gesture:

```bash
bin/chromeos desktop-tap '^Settings$' --role button
```

Raw `tap` and `swipe` commands use the same isolated route. The physical panel
supplies their coordinate range but receives no injected touch events.

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

`adb-status` is an explicit probe: invoking the ADB client can start its server
and display the ChromeOS authorization prompt. Routine doctor and diagnostics
do not execute it. ChromeOS may place the client host key in volatile runtime
storage, so approval remembered for one key need not survive a reboot or ARC
restart that creates a new key.

`install-apk` now connects and verifies the device before installing. It stops
with an actionable message when authorization is required instead of passing a
misleading failure through from `adb install`.

### Idle and closed-lid operation

Inspect the effective powerd overrides and its most recently logged policy:

```bash
bin/chromeos power-status
```

Closed-lid availability is a required invariant of this dedicated test
appliance. Bootstrap and post-update repair install it automatically, the SSH
boot path reapplies it, and both routine doctor and maintenance audit fail
closed when it is missing. Doctor remains read-only.

To reapply only the idle-suspend override manually:

```bash
bin/chromeos keep-awake
```

To reapply the complete required policy manually:

```bash
bin/chromeos keep-awake --lid-closed
```

This writes ChromeOS powerd's documented stateful developer overrides, forces
the embedded controller's lid state open, and restarts powerd. The stateful
preferences persist across ordinary reboots, while the bootstrap-installed
helper records and reapplies the controller override on every SSH boot path.
Keep a closed machine ventilated and preferably connected to AC power: the
normal lid power safeguard is intentionally disabled.

Always-awake is the baseline for this dedicated appliance, not temporary test
state. Do not restore stock power behavior as routine cleanup. If the user
explicitly requests a sleep-capable machine for exceptional troubleshooting,
the guarded opt-out is:

```bash
bin/chromeos restore-power --confirm-make-unavailable
```

The verbose acknowledgement is required because this intentionally makes the
dedicated appliance unready. The powerd-start self-healing guard normally
repairs preference or embedded-controller resets during the current boot; the
next bootstrap or post-update repair also restores the required policy.

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

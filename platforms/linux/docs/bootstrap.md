# Existing Ubuntu Guest Bootstrap And Recovery

This runbook records the bring-up of the existing UTM `Linux` VM on August 1,
2026. It starts from a running Ubuntu desktop with auto-login but no working
QEMU guest-agent channel. It also describes repeatable recovery for another
existing image. A future unattended installation is intentionally separate.

## Observed Baseline

The original VM was:

- UTM 4.7.5 using the QEMU backend on Apple silicon;
- Ubuntu 24.04.4 LTS ARM64 with GNOME Wayland;
- 4 GB RAM, shared networking, VirtIO GPU, and a 1280×800 desktop;
- auto-logged in as the configured testbed user;
- configured for a five-minute idle blank followed by immediate lock;
- missing `qemu-guest-agent` and therefore unable to provide `exec`, files, or
  IP discovery; and
- already carrying OpenSSH Server, but with `ssh.service` inactive.

No SSH service or credential was needed or enabled during bring-up.

## 1 — Verify The Visible Provider Layer

Start UTM and the VM, then from this repository run:

```bash
bin/linuxvm status
bin/linuxvm screenshot
bin/linuxvm permissions
```

If macOS denies capture or event posting, grant Screen Recording and
Accessibility to the invoking terminal or agent host in System Settings.

Before SPICE is installed, the guest pointer may remain captured and absolute
coordinate clicks may be unreliable. Keyboard recovery still works:

```bash
bin/linuxvm key ctrl-alt-t
```

That opens GNOME Terminal without depending on mouse integration.

## 2 — Establish The Guest-Agent Channel

Print the exact one-line command:

```bash
bin/linuxvm bootstrap-command
```

In the focused guest terminal, enter:

```bash
sudo apt-get update && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y qemu-guest-agent spice-vdagent python3-gi gir1.2-atspi-2.0 jq && sudo systemctl start qemu-guest-agent
```

The original image had passwordless `sudo`. If another image requests a
password, the user enters it directly in the VM; do not add a password argument
or store it in configuration.

Ubuntu's `qemu-guest-agent.service` is a static device-activated unit. Running
`systemctl enable qemu-guest-agent` prints that the unit has no installation
configuration. That is not a reason to replace the unit. Start it, and let the
VirtIO device activate it on future boots.

Verify from the host:

```bash
bin/linuxvm ip
bin/linuxvm exec -- id
```

The expected command identity is root. The exact original address was dynamic
and is not part of the configuration contract.

After the agent works, use the candidate-only host bootstrap rather than
retyping or manually staging the complete guest script:

```bash
bin/linuxvm bootstrap --profile development --json
```

The `development` profile installs the runtime control packages plus Git,
`build-essential`, and `python3-venv`, then deploys the checked-in resident and
post-update support and requires a healthy audit and doctor. Use `runtime`
explicitly for a control-only appliance. The underlying idempotent guest
script remains at `guests/ubuntu/bootstrap/bootstrap-guest.sh`.

## 3 — Deploy Semantic Wayland Automation

Keep the GNOME desktop logged in:

```bash
bin/linuxvm deploy-ui
bin/linuxvm ui health
bin/linuxvm doctor
```

The deployer installs the Python helper under `/usr/local/libexec` and invokes
it as the active non-root desktop user with that user's session D-Bus address.
Unlike macOS Accessibility, AT-SPI needs no per-helper approval entry.

If health reports zero or missing applications:

1. Confirm the desktop is logged in rather than showing GDM or the lock screen.
2. Run `bin/linuxvm desktop-user`.
3. Confirm `/run/user/UID/bus` exists.
4. Confirm `gir1.2-atspi-2.0` and `python3-gi` are installed.

## 4 — Disable Idle Lock For A Dedicated Testbed

Auto-login does not disable GNOME's independent idle lock. The original guest
used `idle-delay=300`, `lock-enabled=true`, and `lock-delay=0`, so it locked
after five idle minutes.

For a dedicated testbed, disable automatic blanking and locking as the desktop
user while retaining the manual Lock action:

```bash
bin/linuxvm user-exec -- gsettings set org.gnome.desktop.session idle-delay 0
bin/linuxvm user-exec -- gsettings set org.gnome.desktop.screensaver lock-enabled false
```

Do not disable GDM authentication or store an auto-unlock credential. A user
may still lock the session manually; use the outer visible path to recover.

## 5 — Apply A Full Ubuntu Upgrade

Inspect removals before changing the system:

```bash
bin/linuxvm exec -- apt-get update
bin/linuxvm exec -- env DEBIAN_FRONTEND=noninteractive apt-get -s full-upgrade
```

The original upgrade proposed 379 upgrades, 8 additions, and zero removals,
including a new HWE kernel. It was applied with:

```bash
LINUXVM_EXEC_TIMEOUT=1800 bin/linuxvm exec -- \
  bash -lc 'DEBIAN_FRONTEND=noninteractive apt-get -y full-upgrade > /var/tmp/linuxvm-full-upgrade.log 2>&1'
```

Inspect the log and reboot requirement:

```bash
bin/linuxvm exec -- tail -n 80 /var/tmp/linuxvm-full-upgrade.log
bin/linuxvm exec -- test -e /var/run/reboot-required
```

When required, use the reboot command, which waits for the guest boot ID to
change and for the guest agent to return:

```bash
bin/linuxvm reboot
```

Then use the post-update surface rather than inferring health from service
manager state:

```bash
bin/linuxvm post-update audit --profile development --json
bin/linuxvm post-update repair --profile development --reboot --json
```

Audit never starts a stopped target and never changes it. Repair is restricted
to the exact candidate and only restores installed QEMU/SPICE, input-broker,
and active-user resident startup invariants. It does not install packages,
clear `/var/run/reboot-required`, change update or login policy, or use outer
input. `--reboot` is opt-in and succeeds only after the provider observes a
changed boot ID and both the final audit and common doctor are healthy.

If no reboot is required, omit `--reboot`; a healthy idempotent repair should
report every enumerated invariant as already satisfied. Confirm auto-login,
Wayland, SPICE, AT-SPI, the expected kernel, and the idle-lock settings.

## Display Geometry

The original desktop's current and preferred mode was 1280×800. Keep
`LINUXVM_DISPLAY_WIDTH` and `LINUXVM_DISPLAY_HEIGHT` aligned with GNOME's
logical mode. If dynamic resolution changes it, update `config.local` or set
the guest back to a stable mode before relying on coordinates.

## Recovery Order

1. `bin/linuxvm doctor`
2. Root commands through the QEMU guest agent
3. `bin/linuxvm user-exec` and AT-SPI
4. Normalized screenshot plus `type`, `key`, `scan`, `click`, and `drag`
5. The smallest necessary user action for passwords or authentication

### Guest agent missing after reboot

`post-update repair` cannot repair the QEMU guest-agent transport through that
same missing transport. This is an explicit recovery boundary.

Open Terminal with `key ctrl-alt-t`, then run:

```bash
sudo systemctl start qemu-guest-agent
```

If the binary is missing, repeat the package-install command from step 2.

### Absolute pointer integration missing

Confirm both processes:

```bash
bin/linuxvm exec -- systemctl is-active qemu-guest-agent
bin/linuxvm exec -- pgrep -a spice-vdagent
```

`spice-vdagentd` is system-side; `spice-vdagent` belongs to the interactive
desktop and may require logout/login after first installation.

### Session is locked

AT-SPI belongs to the logged-in desktop and does not control GDM or a distinct
lock-screen session. Use the normalized screenshot and virtual input. The user
enters any authentication secret directly.

## Native x86_64 libvirt image factory

**Current implementation:** A Linux controller can now create a fresh native
x86_64 appliance from an explicit official Ubuntu 24.04 amd64 QCOW2 cloud
image. The host-side factory validates QCOW2 input, copies and expands it to a
128-GiB volume in the configured dedicated libvirt pool, defines a Q35 UEFI
KVM domain with CPU host passthrough and VirtIO devices, and refuses any
existing destination. The configured pool path must resolve exactly to
libvirt's pool target and be writable by the controller account. The factory
converts into that local pool directly, atomically publishes the destination,
refreshes libvirt, and verifies the registered path and QCOW2 geometry. It
does not depend on a long-running libvirt volume-upload stream.

Render the ignored NoCloud seed from a controller public key:

```bash
scripts/image-factory.sh validate-cloud-image PRIVATE_UBUNTU_CLOUD_IMAGE
scripts/image-factory.sh render-seed APPLIANCE_USER CONTROLLER_PUBLIC_KEY
bin/linuxvm factory-create PRIVATE_NAME PRIVATE_UBUNTU_CLOUD_IMAGE \
  .factory.local/linuxvm-seed.iso
bin/linuxvm target-id
```

The seed contains no password or private key. It creates a locked, key-only
dedicated-appliance user with passwordless sudo, starts QEMU guest-agent,
installs the Ubuntu desktop and development package profile, enables GNOME
Wayland auto-login, and reboots after cloud-init completes. Exact UUID pinning,
common doctor, and a target-use claim are required before operating the new
domain. After cloud-init and the normal resident bootstrap pass, stop the
candidate and use `factory-detach-media` under the same claim to remove its
NoCloud seed.

## Earlier unattended-install direction

The original ARM64/UTM plan called for autoinstall or cloud-init with:

- a non-secret account/bootstrap policy chosen by the maintainer;
- UTM guest and SPICE packages installed during provisioning;
- GNOME auto-login and testbed idle policy made explicit;
- a fixed logical display mode;
- the semantic helper deployed from the checked-out repository; and
- a post-install doctor run before the image becomes a clone source.

Do not bake personal credentials, SSH private keys, or machine-specific IDs
into that image.

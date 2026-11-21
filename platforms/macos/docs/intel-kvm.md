# Intel macOS on Linux/KVM

This appliance profile uses a native x86_64 Linux/KVM host, OpenCore, and an
installed Intel macOS guest. Quickemu can run the retained guest. Libvirt
can run an independent copy and derive disposable workspaces. The signed
Machine Control app runs its ordinary resident in the guest's Aqua session.
An outside client uses the same desktop commands over pinned SSH. QMP and
loopback VNC provide bootstrap and recovery without taking over the Linux
desktop.

## Prepare or recover the guest

Use host hardware and installation media authorized for the intended macOS
deployment. Begin a [private provisioning journal](../../../docs/provisioning-journals.md)
before preflight. Keep the Quickemu release, OpenCore build and its private SMBIOS
configuration, OVMF code and writable vars, launcher, and all image files in
an owner-controlled directory. Follow the
[Quickemu macOS installation instructions](https://github.com/quickemu-project/quickemu/wiki/03-Create-macOS-virtual-machines)
for Tahoe recovery media and initial installation. Use KVM with the Q35
machine and compatible x86_64 CPU, storage, network and tablet devices. Retain
the configuration that booted the candidate and record its revisions
privately. The VM's OS disk and OpenCore disk remain separate QCOW2 files.

During installation, use the recovery image and select the intended APFS
volume in the guest installer. Complete Setup Assistant with the dedicated
guest account. Preserve the login secret in the controller's owner-only
credential file and verify it through the normal guest login. If Setup
Assistant stalls on its final screen, wait for installation activity to settle
and request a graceful shutdown. The observed Tahoe installation completed
after one such shutdown and cold boot. For normal boots, detach the recovery
image and configure OpenCore to select the installed system automatically.
Keep the original recovery media available privately. Boot the retained
profile with its original NVRAM and both original disk files.

Declare a loopback-only SSH port forward and a loopback VNC display. The
owner-only VM directory contains the `qmp.sock` Unix listener. Start the
installed guest once with the known private launcher and verify through
QMP that KVM is enabled and both disks appear as `BootLoader` and
`SystemDisk`. Keep a powered-off backup of the disks and writable firmware
state when changing the installer, bootloader or hypervisor definition.

## Register the target and bootstrap SSH

Configure a private target registry or inventory entry using
`platforms/macos/bin/macvm-qemu`, platform `macos`, profile
`macos-intel-qemu-kvm`, controller platform `linux`, and required claims.
Set the following environment entries in private inventory.

| Setting | Value |
| --- | --- |
| `MACVM_QEMU_DIRECTORY` | Absolute owner-only VM directory containing `qmp.sock` |
| `MACVM_QEMU_OPENCORE_DISK`, `MACVM_QEMU_SYSTEM_DISK` | Absolute paths to the two files inside that directory |
| `MACVM_QEMU_OPENCORE_DISK_ID`, `MACVM_QEMU_SYSTEM_DISK_ID` | Each file's device and inode from Linux `stat -c '%d:%i' -- FILE` |
| `MACVM_QEMU_LAUNCHER` | Absolute private launcher for the exact existing VM, which returns after QEMU starts |
| `MACVM_QEMU_SSH_PORT`, `MACVM_QEMU_SSH_USER` | Loopback forward port and dedicated guest account |
| `MACVM_QEMU_SSH_KEY`, `MACVM_QEMU_KNOWN_HOSTS` | Absolute owner-controlled SSH identity and known-hosts file |
| `MACVM_QEMU_GUEST_PYTHON` | Bundled interpreter at `Contents/Resources/mc-cli/python/bin/python3` in the installed app |
| `MACVM_QEMU_RESIDENT_ADAPTER` | Bundled adapter at `Contents/Resources/mc-cli/platforms/macos/host/machost.py` in that app |
| `MACVM_QEMU_SESSION_PROBE` | Optional override for the bundled `Contents/Resources/mc-session-probe` |
| `MACVM_QEMU_LOGIN_SECRET_FILE` | Inventory locator for the stored guest login password |
| `MACVM_QEMU_FORBID_OUTER_UI` | Set to `true` when QMP recovery capture and input should be disabled |

The launcher must keep QEMU alive after the invoking shell and agent runner
exit. A Linux user service with `ExitType=cgroup` can supervise a Quickemu
launcher that returns before its QEMU child exits. Keep the launched service
identity private and use the guest's graceful shutdown for normal power-off.

Run `machine-control inventory credentials TESTBED` and
`machine-control --target TARGET target doctor`. Doctor can confirm exact
identity before guest SSH or the resident is ready. Acquire a disruptive
claim for initial QMP observation and VNC recovery. With that claim and
the VM at its visible console, install the controller's public SSH key in
the guest account and enable Remote Login in **System Settings → General →
Sharing**. The dedicated appliance can also enable Apple's `ssh.plist` with
`sudo launchctl load -w /System/Library/LaunchDaemons/ssh.plist` at its
interactive Terminal. Compare the host key obtained through the loopback
forward with the fingerprint read at the exact guest console before pinning
it. Use key authentication for ordinary SSH. Use the canonical file through a
secret-safe input route for console login or an observed authorization prompt.

Recovery capture uses `testbed -- screenshot ABSOLUTE_NEW_PNG` and requires
an owner-only output directory. Inspect fresh output before
`testbed -- click X Y`, which uses the QEMU absolute tablet and guest display
pixels. Both operations require a disruptive claim. They report dispatch.
Verify the visible result independently. The same disruptive claim covers
`testbed -- key wake` over loopback VNC. For an observed, focused password
field, capture a fresh QMP screenshot and call
`testbed -- type-secret --observed-password-field SCREENSHOT`. This requires
an independently observed locked or signed-out console via pinned SSH and
the bundled probe. It compares the fresh private screenshot with the live
frame before opening the owner-only credential file, then enters and submits
the password once. A blinking caret can produce two different frames. Inspect
both while the same password field is focused and pass a second
`--observed-password-field SCREENSHOT` so the live frame can match either
observation exactly. If the frame changed before delivery, inspect a new one.
After a delivered attempt, verify the native session state before deciding
next steps. Use the dedicated loopback VNC viewer for initial bootstrap
before SSH and the session probe are available. An ordinary claim covers
SSH, resident operations and lifecycle.

Doctor uses the packaged session probe independently over SSH when resident
status is unavailable. It can show a locked console alongside an unavailable
resident. The probe does not change power, wake the display, or authorize
access.

## Install and qualify the package

Download the Intel DMG from the [published downloads](https://machinecontrol.dev/downloads/).
Record its version and SHA-256. Under the exact claim, run
`testbed -- install-package DMG SHA256`. The command verifies the digest on
both sides of pinned SSH, mounts the DMG read-only, checks the x86_64
executable and Developer ID signature, and runs Gatekeeper assessment.
It installs into `/Applications` when the app is absent. When the app is
already installed, the command verifies the signed code hash and reports
the matching version. A different installed build needs the normal update
workflow.

Open the installed app in the logged-in Aqua session. Use its Permissions
view to grant Accessibility and Screen
Recording in System Settings. If Screen & System Audio Recording has no
Machine Control entry, use its plus button and select the installed app.
Follow the native prompt to quit and reopen it. Enable Desktop access through
the app for the bounded test.

Under the claimed target, inspect `testbed -- bootstrap-stages --json`,
`target doctor`, and `desktop status`. Use `desktop capture --scope display`
and `desktop artifact` to retrieve a native JPEG or PNG as returned by the
resident. Inspect a known application and press a named Accessibility control
in one [retained Desktop session](../../../client/control_session.py) so the
reference stays valid across both operations. Verify the effect independently,
for example by reading the test fixture's result file over SSH. Use private
evidence paths and record the guest build, CPU architecture, and actual
security posture.

Record the guest boot time, request a graceful shutdown and verify that
QEMU exits before starting with `target up`. Use the normal guest shutdown
if QMP's ACPI request has no observed effect. Recheck the guest boot time and
SSH host key, sign in through the recovery console if necessary, and repeat
resident readiness, capture, and the Accessibility effect. Enable Desktop
access again if prompted. Shut it off at the end of testing and release the
claim. Existing test authorization and GUI login may require an operator or
authorized recovery at each cold boot.

## Libvirt base and workspaces

To move a previously qualified libvirt guest to another Linux controller,
recover the inactive domain definition, both QCOW2 disks, read-only OVMF
code, and writable NVRAM from a cleanly stopped source or a verified backup.
Mount any reconstructed backup read-only. Verify the disk and firmware
copies before defining the local domain. Keep the working CPU, chipset,
disk roles and firmware settings. Assign the local domain a new libvirt
UUID, bind its files to the local pool and network, and keep its recovery
display on loopback. For owner-only firmware files, grant the libvirt QEMU
account read access to the firmware code and read/write access to NVRAM.
Recover the guest-specific SSH identity, pinned host
key and login password through the controller's private inventory and
owner-only secret store.

Run common doctor and acquire an exact claim on the new domain. Verify
pinned SSH and the native resident after a disk-only boot. A backup that
contains a previously qualified guest still needs a local boot and readiness
check. Use the ordinary unsealed profile when this is the retained
development VM. Enable workspace derivation only after the stopped base
qualifies through the workflow below.

1. Hold the original appliance's claim, shut it down cleanly, and copy the
   OpenCore and system QCOW2 payloads, firmware code and writable NVRAM
   into private libvirt storage. Verify the disk copies with
   `qemu-img compare` and verify the firmware copies byte-for-byte. Restart
   the original when the independent copies are in place.
2. Define a dedicated Q35/KVM domain over those copies in `qemu:///system`.
   Use `sda` over SATA with boot order 1 for OpenCore and `vda` over VirtIO
   for the system disk. Configure read-only pflash code, separate writable
   NVRAM, one libvirt-managed VirtIO network, an absolute USB tablet, and
   loopback-only VNC. Preserve the working setup's virtual CPU and chipset
   flags. In the qualified copy, Apple EFI progressed after carrying over
   the Quickemu Haswell-v2 CPU arguments and chipset properties together.
   The [libvirt validator](../../../providers/libvirt-linux/libvirt_provider.py)
   permits those explicit extra settings and the private SMC configuration.
3. In the private target entry, set `MACVM_QEMU_PROVIDER=libvirt`, profile
   `macos-intel-libvirt-kvm`, and set `MC_LIBVIRT_DOMAIN_NAME`,
   `MC_LIBVIRT_EXPECTED_UUID`, `MC_LIBVIRT_NETWORK`, and `MC_LIBVIRT_POOL`.
   The active storage pool must expose both copied disks as volumes.
   Use the existing SSH and resident settings with the guest SSH port.
   Set `MACVM_LIBVIRT_SSH_HOST_KEY_ALIAS` to the pinned name in the
   known-hosts file. The adapter selects the domain's current IPv4 lease.
   Boot the independent copy once, verify pending console login over SSH,
   then sign in and verify the resident.
4. Gracefully stop the verified copy. Set
   `MACVM_LIBVIRT_READY_BASE_PROVEN=true`,
   `MACVM_LIBVIRT_WORKSPACE_STORAGE_PATH` to the active pool directory, and
   `MACVM_LIBVIRT_NVRAM_DIRECTORY` to the libvirt-managed NVRAM directory.
   Direct start of the sealed base is refused. The isolated workspace
   receives two UUID-owned QCOW2 overlays and its own writable copy of the
   stopped base's NVRAM. It inherits the lab base's verified login and SSH
   host key.

Use `workspace acquire --intent isolated --reason REASON` and carry both
the returned `--workspace` handle and `--claim` on guest operations.
For console recovery, release the workspace's ordinary claim and acquire a
disruptive claim on that same handle. Release the workspace itself with
`--claim CLAIM workspace release HANDLE`. Release verifies the receipt,
both overlay backing relationships, and the separate NVRAM before removing
the stopped workspace.

Libvirt requests ACPI shutdown. On a dedicated appliance whose ACPI request
has no observed effect, inventory may explicitly enable
`MACVM_LIBVIRT_ALLOW_SSH_SHUTDOWN=true`. After verifying pinned SSH, the
adapter submits the stored credential once to the fixed guest sudo shutdown
command and waits for actual power-off. The provision journal records the
observed lifecycle. See the [qualification record](../../../docs/tactical/164-intel-macos-recovery-and-workspaces.md).

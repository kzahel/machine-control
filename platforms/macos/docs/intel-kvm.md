# Intel macOS on Linux/KVM

This appliance profile uses a native x86_64 Linux/KVM host, Quickemu with
OpenCore, and an installed Intel macOS guest. Linux owns VM lifecycle and
recovery. The signed Machine Control app runs its ordinary resident in the
guest's Aqua session. An outside client uses the same desktop commands over
pinned SSH. QMP and loopback VNC provide bootstrap and recovery without taking
over the Linux desktop.

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
Verify the visible result independently. Use a dedicated loopback VNC
connection for bootstrap keyboard input while holding that same disruptive
claim. Close the recovery connection when the inner route is ready. An
ordinary claim covers SSH, resident operations and lifecycle.

## Install and qualify the package

Download the Intel DMG from the [published downloads](https://machinecontrol.dev/downloads/).
Record its version and SHA-256, carry it over pinned SSH, and verify the
transfer before mounting it read-only. Check the app with
`codesign --verify --deep --strict` and
`spctl --assess --type execute --verbose=2` before installing. Check the
main executable with `file`, then open the installed app in the logged-in
Aqua session. Use its Permissions view to grant Accessibility and Screen
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

## Libvirt migration

The [Linux libvirt provider](../../../providers/libvirt-linux/libvirt_provider.py)
already owns native Q35/KVM validation, UUID identity, guarded lifecycle and
QMP recovery for Windows and Linux. Its existing profile requires one VirtIO
QCOW2 disk and a QEMU guest-agent channel. Its workspace code assumes one
writable primary disk. An Intel macOS profile would validate separate
OpenCore and system disks against their private roles, preserve firmware and
device topology, and use pinned SSH for readiness. Libvirt should first boot
and stop a disposable copy with independent NVRAM and boot/system disks, with
the original offline and its identity preserved. This recipe uses the
existing Quickemu launcher. Libvirt import, workspace derivation, unattended
console login, and a stock-security macOS profile are outside its coverage.

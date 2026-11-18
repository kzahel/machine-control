# Tactical 163 — Intel macOS on Linux/KVM

Status: complete for the bounded Quickemu/KVM appliance.

Topics: [macOS resident control](../../topics/macos-resident-control.md),
[target lifecycle and readiness](../../topics/target-lifecycle-and-readiness.md),
and [VM workspaces and storage policy](../../topics/vm-workspaces-and-storage-policy.md).

## Objective and completion conditions

Adopt the target-native path for an installed Quickemu/OpenCore Intel Tahoe
appliance. Establish an exact target claim, verify the published Intel app
inside the guest, prove native capture and an Accessibility action with an
independent application effect, then repeat after a verified cold boot.

Keep the same bootloader and system disks throughout. The initial scope is a
retained existing appliance and a reproducible bootstrap and recovery recipe.
Libvirt conversion, installer automation, protected desktop control, physical
Intel Macs, workspace derivation, and updates each need their own evidence.

## Ordered work

### 1 — Bind the existing guest

Confirm x86_64 QEMU with KVM and the two attached disk roles. Pin each disk
privately and bind the common claim to the system disk. The QMP peer must hold
both pinned files and report the same roles. Keep credentials and endpoints
in private inventory and the controller-local secret store.

### 2 — Establish native guest access

Use a disruptive claim for console recovery. Enable macOS Remote Login and
pin the host key after comparison with the visible guest console. Verify the
installed Intel DMG and make Accessibility and Screen Recording choices
through visible System Settings. Work through the existing packaged resident
over SSH for ordinary actions.

### 3 — Prove native capture and Accessibility

Acquire an ordinary claim. Confirm outer capture is refused with that claim.
Retrieve the resident's capture and verify its file format and display
geometry. Inspect a named native button and press it in a single retained
Desktop control session. Independently read the fixture's result file over
guest SSH.

### 4 — Repeat after a cold boot

Request graceful shutdown, observe QEMU exit, and start the same installed
VM. Compare guest boot times and continue using the pinned SSH key. Repeat
native readiness, capture and the Accessibility action after guest sign-in
and explicit Desktop consent. Return Desktop access to Off and release the
final claim.

## Validation and findings

The earlier Tahoe Setup Assistant stalled on its final screen. The owner
observed that a graceful shutdown and one cold boot completed setup. The
retained image reports macOS 26.7.3 build 25G342, x86_64, and a custom SIP
configuration. The provision and usage journals retain the host-local
details and evidence paths.

The public Intel 0.7.2 DMG matched between controller and guest
(SHA-256 `64499edac1920186d9569062dcbebbb903b6e562829f61d8adba6d7cf724a940`).
The guest verified the app's Developer ID signature, nested code, and
notarization. Its main executable is x86_64. The installed resident reported
native readiness after visible Accessibility and Screen Recording consent
and the system-requested relaunch.

Both ordinary-claim runs fetched a native Quartz 1920×1080 PNG over SSH.
Native AX snapshot and press succeeded together in a retained Desktop
session. The test applet independently wrote its expected marker file each
time. The ordinary claims refused QMP capture.

QMP ACPI powerdown reached Off. The initial cold start returned pinned SSH
with a changed boot epoch, then QEMU exited with the command runner. A private
systemd user service kept the exact Quickemu guest running across command
boundaries on the next cold start. Pinned SSH came back before console
login. After login the packaged resident started automatically, the privacy
grants persisted, and Desktop access remained Off until enabled for the
second test. The same pinned disks and installed app remained in use.

The guest remained running under the private service. Desktop and Browser
were Off, fixture staging was removed, and the final target claim was released.
The portable validation suite passed, including the new identity guards and
the existing libvirt provider tests.

The [platform guide](../../platforms/macos/docs/intel-kvm.md) owns installation
and recovery. The current libvirt validator's single VirtIO disk and QEMU
guest-agent requirements and the workspace builder's single overlay make
direct reuse incompatible with this guest. Its KVM validation, UUID-based
identity, and QMP recovery primitives remain appropriate to reuse in a
future profile after proof on a disposable copy.

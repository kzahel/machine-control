# Tactical 164 — Intel macOS recovery and workspaces

Status: complete for the retained Quickemu guest and isolated libvirt workspaces.

Topics: [macOS resident control](../../topics/macos-resident-control.md),
[target lifecycle and readiness](../../topics/target-lifecycle-and-readiness.md),
and [VM workspaces and storage policy](../../topics/vm-workspaces-and-storage-policy.md).

## Objective and boundaries

Repeat Intel Tahoe lock recovery with maintained tools, make packaged
bootstrap repeatable, and validate disposable libvirt workspaces. Use pinned
SSH and the existing target-native resident for ordinary operations.
Experiment with independent storage and firmware so the original Quickemu
appliance remains recoverable.

## Ordered work and acceptance

1. Diagnose the locked resident timeout using the packaged native session
   probe and the guest-local socket. Verify readiness after recovery and
   distinguish a status failure from the console state.
2. Exercise claimed keyboard recovery and one-shot confirmed console login.
   Keep normal macOS membership, privacy consent and Desktop access decisions
   in their existing operator UI.
3. Prepare an independent libvirt base from a stopped copy. Verify exact
   identity, pinned SSH and the native resident. Derive an isolated workspace
   with distinct boot and system overlays and writable NVRAM. Verify a
   guest write is isolated and receipt-bound release removes the workspace.

## Recovery findings

On the idle-displayed appliance, the operating-system probe confirmed the
locked console while the resident socket accepted connections and timed
out on status. Waking the display and authenticating restored native
readiness. An awake, explicitly locked repeat still answered resident status.
The checked-in VNC keyboard and stored-password command restored readiness
without changing the resident PID. This qualifies recovery. The reason
for the idle status timeout remains open.

## Package bootstrap

The adapter's package command verified the public 0.7.2 DMG digest on both
sides of SSH, mounted it read-only, and verified the signed Intel app and
Gatekeeper acceptance. The already-installed app matched the signed code
hash. The original qualification exercised the actual install into
`/Applications`. The package command leaves macOS privacy grants and
Desktop access decisions in their visible operator flows.

## Libvirt qualification

The source Quickemu VM reached a clean shutdown before the two independent
QCOW2 and firmware copies were made. Both disk payloads passed
`qemu-img compare`. The firmware files matched byte-for-byte, and the
original guest restarted on its own disks.

The first libvirt definition was refused because libvirt did not recognize
the Quickemu virtual CPU frequency property as an XML CPU feature. A simpler
definition stalled at the Apple EFI ExitBootServices handoff. Restoring the
measured Haswell-v2 CPU and chipset options together booted the copied guest.
The evidence does not isolate one flag as the cause.

The copy and a derived workspace reached pinned SSH before sign-in. Claimed
QMP and VNC recovery signed in to the expected guest user, and the packaged
resident reached native readiness. The imported base was stopped and sealed.
The cleanup workflow gives each derived VM separate OpenCore and system
overlays and a writable NVRAM copy, and binds all three to its receipt.
On a live copy where ACPI had no observed effect, the explicit SSH shutdown
option reached a graceful power-off through the guest's shutdown command.

Two successive isolated workspaces reached pinned SSH. The first wrote a
marker to its guest home directory. The second had no such file. Both
disposals succeeded, no derived domain or workspace receipt remained, and
both base disk hashes and both firmware hashes still matched the sealed
baseline. The original Quickemu VM remained on its original disks.

Fresh media installation and initial macOS privacy grants remain documented
operator flows. The libvirt evidence covers the measured virtual hardware
profile, a custom guest SIP configuration, and the published Intel 0.7.2
package. Protected desktop and broader hardware coverage remain open.

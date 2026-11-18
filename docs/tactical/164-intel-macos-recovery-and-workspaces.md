# Tactical 164 — Intel macOS recovery and workspaces

Status: recovery verified on the Quickemu appliance. Libvirt qualification open.

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

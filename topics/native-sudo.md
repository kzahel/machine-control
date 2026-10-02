# Native sudo

Topic: `native-sudo`

Status: implemented; signed ARM64 helpers pass dedicated Mac appliance
conformance. Signed/notarized ARM64 and Intel helpers ship in public desktop
0.5.3; physical-host acceptance remains open.

## Current

**Current:** [mc-sudo](../platforms/macos/sudo/README.md) is a Rust CLI plus
Swift/AppKit askpass bridge bundled and signed with the Mac desktop app. It
uses [system sudo](../research/providers/sudo.md) for authentication and root
execution. Separate arguments, directory and kernel-observed process ancestry
appear in the local native secure-field dialog. Secrets stay in the native
askpass pipe. YA advertises it only for explicitly configured, verified,
local unrestricted launches. No default behavior changes.

## Decision

**Decision:** first ship per-invocation native password authentication. No
root daemon or persistent sudoers grant is required. Existing desktop arming
controls do not confer administrator authority; sudo policy and the local
password dialog do. The authentication timeout is bounded and cancellation or
failure is terminal. Authenticated command descendants can retain full root
authority, and their changes survive command exit.

**Decision:** process ancestry is useful attribution, not same-user containment.
YA owns session instructions and environment; Machine Control owns native
helper packaging and authentication. A remote YA browser is not an approver
for a prompt on another Mac.

## Open

**Open:** session/process leases, Touch ID, remote out-of-band approval, other
OS implementations and automatic interception of ordinary sudo. These require
separate authority design and evidence. Physical workstation acceptance remains
separate from the signed/notarized public packages recorded in
[Tactical 063](../docs/tactical/063-six-platform-desktop-release.md).

[Tactical 061](../docs/tactical/061-native-sudo.md) owns validation and final
implementation results.

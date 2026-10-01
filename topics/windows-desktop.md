# Windows Desktop

Topic: `windows-desktop`

Status: active implementation; native grants pass an x64 VM prototype and
portable contracts. Shared operator packaging and signed installed acceptance
remain in progress.

## Product and boundaries

**Decision:** Package the existing ordinary-user .NET resident with the shared
Tauri settings and tray application. Preserve the providers and named-pipe
contract. Supervise a self-contained companion; require neither a separately
installed .NET runtime nor the privileged appliance service.

**Decision:** The desktop resident starts with access off. Enforce scope,
bounded duration, approval narrowing, prompt-time input pause, Stop, expiry,
session/desktop transitions, and stale-reference invalidation in resident
dispatch. Approval uses a private operator channel, never the agent endpoint.
Preview grants apply to callers of the same user; this does not contain an
agent with an unrestricted same-user shell.

**Decision:** Preserve the explicitly selected YA workstation component and
protected appliance profiles. The desktop app owns a distinct instance and
endpoint. It never installs or arms the protected service. Elevated apps, UAC,
lock/login, and other users remain outside its ordinary profile.

**Decision:** Reuse the concise Access, Permissions, Activity, and Settings UX.
Windows permissions report session/integrity availability rather than macOS
consent controls. Initially expose supported desktop scopes; browser integration
has a separate acceptance gate.

**Decision:** Signed ARM64/x64 candidates use the existing publisher signing
infrastructure and desktop updater key. Every publication requires meaningful
checked-in versioned notes. Exact signed installed acceptance precedes any
Windows support claim.

## Execution and remaining gates

**Current:** A distinct desktop resident enforces off-by-default grants before
provider dispatch. It has an inherited private operator channel, a native Stop
shortcut, desktop/session monitoring, update arming exclusion, bounded activity,
and generation invalidation. Portable contracts and native x64 source probes
passed approval narrowing, prompt pause, Stop, stale generation, fixture effect,
PNG/hash verification, and update gating. This is source-prototype evidence,
not signed installed Tauri acceptance.

[Tactical 053](../docs/tactical/053-windows-desktop.md) owns implementation and
acceptance. Existing engine/package evidence is in
[Tactical 036](../docs/tactical/036-windows-workstation-distribution.md);
[native distribution](native-distribution.md) owns shared release decisions.

**Open:** Native grants/lifecycle, signed installer/updater verification,
ARM64/x64 execution, and production Windows feed publication. Physical hardware
acceptance remains separate from VM acceptance.

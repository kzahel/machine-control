# Windows Resident Control

Topic: `windows-resident-control`

Status: active design and implementation-planning concern; the first tactical
is proposed and implementation has not started.

## Scope

This topic owns the current Windows proving-ground decisions, unresolved
resident component boundaries, and the direction that must survive across
implementation slices. The bounded execution plan lives in
[`Tactical 000`](../docs/tactical/000-windows-resident-control-vertical-slice.md).

## Settled direction

- Desktop control is implemented at the target and is directly reachable by
  authorized local or remote callers through the same conceptual interface.
- A Windows YA worker is useful for local build/debug context or a provider
  available only in the target, but it is not a control prerequisite.
- WinVM retains lifecycle, bootstrap, recovery, and target-specific safety
  ownership.
- Ordinary callers receive Windows administration and resident semantic,
  visual, and input control, not host/hypervisor input.
- System-wide control includes Start, taskbar, notification area, shell
  flyouts, Settings, dialogs, and ordinary window management; an app-scoped
  test alone is insufficient.
- Outer control is startup, bootstrap, independent observation, and recovery.
- Current Cua Driver is the leading resident desktop-plane candidate to
  validate; WinApp remains the existing comparison route. Neither owns the
  project contract, lifecycle, protected authority, or recovery boundary.
- Computer Use is an optional provider and ergonomic benchmark, not the only
  remotely usable surface.
- ChromeOS is the current quality and architecture reference for rich outside
  access to target-native administration, semantics, capture, and input.
- The Windows slice validates local and remote facades before the project
  freezes a universal wire protocol.

## Resident component boundary

The smallest repeatable Windows target appliance needs to provide:

- a stable installed service identity and authenticated local/remote sessions;
- a companion in the interactive user session for UIA, capture, and input;
- administration adapters and health visible to the outer testbed;
- optional, narrowly typed protected operations under an explicit deployment
  profile or lease; and
- recovery after reboot, logout, lock, user switching, or provider crash.

The first implementation should compare current Cua Driver with WinApp and may
compose either with PowerShell, SSH, or other existing pieces behind the
facade. The product boundary is the target controller, not any one adapter. The
source-reviewed shortlist and shared acceptance lessons live in
[`provider-landscape.md`](provider-landscape.md).

## System-shell acceptance contract

Windows UI Automation should observe from the desktop root rather than only an
application root. Start, taskbar, notification area, Settings, shell flyouts,
dialogs, and ordinary windows are first-class control targets. Transient shell
surfaces must use generation-scoped references and event-aware waits because
focus or shell recreation can invalidate them.

The resident fallback order is:

1. UIA semantic action.
2. Native Shell or Win32 operation.
3. Guest-local keyboard or pointer input with fresh visual evidence.
4. An explicitly authorized protected route when the desktop boundary requires
   it.

Missing semantics must never silently route input through the host VM window.
Administration and UI testing remain distinct intents: a direct Settings URI
or OS API is efficient for configuration, while the Windows-shell acceptance
track deliberately drives and verifies the visible Settings experience.

The facade should allow compact semantic/visual scopes for Start, taskbar,
notification area, a shell flyout, and a Settings window so agents do not pay
for the entire desktop tree on every action.

## Open decisions

### Inner-first enforcement

The preferred initial enforcement is tool grants at the YA coordination and
testbed-adapter boundary. Still decide:

- whether read-only outer screenshots are ordinarily visible;
- what constitutes an active recovery context or lease;
- whether host activity automatically denies focus/pointer/keyboard routes;
- how a caller emits and a controller resolves a recovery request; and
- where route and host-interference audit records live.

### Optional YA placement

After direct resident control works, decide the smallest repeatable YA worker
appliance: server lifecycle, provider credentials, checkout discovery, relay
identity and pairing, and readiness. This question must not block direct
outside control.

### Adapter boundary

Determine how a small adapter projects target/capability inventory, independent
state dimensions, route and host-interference metadata, structured results,
recovery requests, and artifact references without forcing every testbed to
rename or reimplement its CLI.

### Outer recovery authority

Choose between the controller session, a narrow deterministic YA service, or an
explicit recovery worker on the controller host. The Windows target must not
hold the only authority capable of repairing its resident provider.

### Protected broker and personal-machine authority

Begin with an explicit dedicated-test-appliance profile. Add a SYSTEM broker
only for concrete operations the user-session companion cannot perform, with
separate arming, authenticated peers, request/target/generation binding,
expiry, revocation, and conformance tests.

For personal/shared machines, same-user tool policy is not containment when an
agent also has a shell. Decide which OS identity, sandbox, or external
authorization host can issue protected leases without being writable by the
agent itself.

### Artifact exchange

Decide when an outside caller receives screenshot/log/trace/build content, a
redacted summary, a bounded downloadable handle, or only target-local
provenance.

## Later questions

- Whether the proven facade should become a common machine-control SDK.
- Whether current Cua Driver becomes the primary Windows desktop adapter,
  remains a comparison provider, or supplies parts of a smaller resident core.
- How multiple displays, RDP/console sessions, fast-user switching, and nested
  VMs are represented.
- Which physical Windows machines warrant BMC, power, or hardware-KVM support.

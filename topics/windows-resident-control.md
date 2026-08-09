# Windows Resident Control

Topic: `windows-resident-control`

Status: active implementation concern. Cua source/live evaluation and the
Windows system-shell acceptance run are complete. Full target-native Windows
implementation is active in
[`Tactical 002`](../docs/tactical/002-windows-full-target-native-control.md).

**Current:** The implementation under [`src/`](../src) provides the first
Windows service/session vertical slice. VM and physical x64 evidence covers the
ordinary Medium plane, native system-shell control, local/remote parity,
genuine UAC secure-desktop approve/cancel, High-integrity fixture control,
lock, logout, stock PIN/password login, and restartable helpers. Physical
recovery also proved that the dual-boot lifecycle must reselect Windows after
one-shot EFI `BootNext`; once selected, SSH, the automatic service, a new
generation, and the Medium helper returned. Tactical 002 remains active until
remaining provider-composition gaps are resolved.

## Scope

This topic owns the current Windows proving-ground decisions, unresolved
resident component boundaries, and the direction that must survive across
implementation slices. Candidate comparison and investigation depth live in
the [Windows research report](../research/platforms/windows.md). The bounded
execution plan lives in
[`Tactical 000`](../docs/tactical/000-windows-resident-control-vertical-slice.md).
Its completed shell-acceptance slice lives in
[`Tactical 001`](../docs/tactical/001-windows-system-shell-acceptance.md).

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
- The recent Cua spike passed with conditions and establishes Cua as the
  provisional common normal-user runtime. Real shell acceptance proves that a
  Cua-only stack is insufficient: WinApp/native Windows adapters are required
  for taskbar operations, packaged-window inner/outer resolution, selected
  window-state actions, and capture of HWNDs absent from Cua's registry.
  Neither provider owns the project contract, lifecycle, protected authority,
  or recovery boundary.
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

The first implementation should use the completed Cua and system-shell
evidence rather than repeat it. Build an owned facade/session proxy that routes
each operation through Cua or the measured WinApp/native shell adapter and
reports the actual route, fidelity, foreground consequence, delivery, and
independent effect. PowerShell, SSH, and narrower native components may remain
adapters behind the facade. The product boundary is the target controller, not
any one adapter.

The cross-platform ownership boundary, hybrid-first rationale, correctness
oracles, and criteria for eventually forking or replacing Cua are recorded in
the
[provisional provider composition](architecture.md#provisional-provider-composition).

## Research and option status

**Current:** The [Windows research report](../research/platforms/windows.md)
is the single entry point for the candidate matrix and completed
investigations. It records:

- Cua source review and live normal/elevated/UAC/lock/session experiments;
- the adopted WinVM/WinApp relay and observed UIA/WebView/effect limits;
- Open Computer Use as a source-reviewed compact cross-platform comparison;
- Cua-plus-native, WinApp-centered, and owned-native architecture options; and
- source-reviewed and search-triage alternatives that have not earned a live
  experiment.

**Decision:** The leading architecture is a small owned Windows facade/session
proxy with a Cua common-runtime adapter, an operation-level WinApp/Win32/Shell
adapter for measured gaps, and a separately installed protected Windows
provider. Tactical 002 now requires a full protected-desktop capability on a
dedicated test appliance; the interface and arming remain narrow even though
the authorized desktop control is not.

The provider-first view and common contract lessons live in
[`provider-landscape.md`](provider-landscape.md). Exact pins, commands, and
target evidence remain in `machine-control-spike` and `winvm-testbed`.

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

**Current:**
[`Tactical 001`](../docs/tactical/001-windows-system-shell-acceptance.md)
completed this track. The minimized
[`shell findings`](../../machine-control-spike/docs/windows-shell-findings.md)
show that provider choice must occur per operation. Cua remains strong for
ordinary-window semantics, compact state, background UIA, capture, evidence,
and frame placement. The Windows adapter must cover Cua-invisible shell HWNDs,
pattern-aware taskbar/title-bar actions, Settings outer/inner resolution, and
alternate exact-window capture.

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

Define the smallest facade that projects target/capability inventory,
generation-scoped window and element identity, compact observation, capture
extent, route and host-interference metadata, structured delivery/effect
results, recovery requests, and artifact references. Its provider arbiter must
select Cua or the Windows shell adapter per operation without forcing every
testbed to rename or reimplement its CLI.

### Outer recovery authority

Choose between the controller session, a narrow deterministic YA service, or an
explicit recovery worker on the controller host. The Windows target must not
hold the only authority capable of repairing its resident provider.

### Protected broker and personal-machine authority

Begin with an explicit dedicated-test-appliance profile. Its installed Windows
service may authorize complete protected-desktop semantics, capture, keyboard,
pointer input, and guarded stock Credential Provider selection across elevated,
UAC, lock/login, and session transitions.
Keep protected operations typed and separate from arbitrary SYSTEM command
execution, with authenticated peers, request/target/generation binding,
expiry, revocation, and conformance tests. “Narrow” describes the authority and
API boundary, not an intentional inability to control Windows.

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
- Whether long-term Cua maintenance stays wrapper/upstream based or eventually
  warrants replacing portions of the common runtime behind the same facade.
- How multiple displays, RDP/console sessions, fast-user switching, and nested
  VMs are represented.
- Which physical Windows machines warrant BMC, power, or hardware-KVM support.

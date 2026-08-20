# Windows Resident Control

Topic: `windows-resident-control`

Status: first complete Windows appliance milestone. Full target-native control,
provider composition, and reproducible appliance acceptance are complete in
[`Tactical 002`](../docs/tactical/002-windows-full-target-native-control.md)
and
[`Tactical 004`](../docs/tactical/004-windows-provider-composition-and-agent-ergonomics.md),
with clean-appliance acceptance in
[`Tactical 005`](../docs/tactical/005-windows-clean-appliance-and-real-application-acceptance.md).
Target safety, native activation/window lifecycle, efficient repeated
observation, expanded real-app acceptance, and generalized-image export are
complete in
[`Tactical 006`](../docs/tactical/006-windows-safety-launch-efficiency-and-image-factory.md).
The public-ISO-to-new-base boundary is complete in
[`Tactical 007`](../docs/tactical/007-windows-iso-factory-acceptance.md).

**Current:**
[`Tactical 020`](../docs/tactical/020-windows-post-update-and-appliance-certification.md)
completed minimized post-update audit and bounded candidate-only repair, a
reproducible Python 3/.NET 8 development bootstrap profile, and explicit
on-demand appliance certification. Live acceptance passed a healthy repair,
changed-epoch reboot, exact-archive portable/native guest checks, staging
removal, and clean shutdown on the retained appliance. The guest contract
checks actual resident and Medium-helper readiness in addition to automatic
services. Its UTM guest-agent fallback requires a fresh nonce-bound report and
subsequent SSH and full-doctor readiness because guest execution status alone
has produced false success.

**Current:**
[`Tactical 025`](../docs/tactical/025-windows-non-pty-administration-readiness.md)
removed the retained ARM64 appliance's non-PTY administration stall. Fresh
bootstrap and post-update repair install and preserve a digest-pinned native
PowerShell 7 shell, encoded scripts no longer start a nested legacy shell, and
Windows doctor obtains its guest readiness dimensions in one explicitly
bounded SSH session. Live repair-and-reboot acceptance observed a changed boot
epoch and returned the full resident surface without PTY or outer recovery.

**Current:** [`Tactical 018`](../docs/tactical/018-appliance-readiness-and-promotion.md)
reused one retained stateful candidate rather than creating another large VM.
It restored key-only SSH, automatic guest-agent/SSH services, and the complete
resident surface; a changed Windows boot epoch returned administration,
interactive desktop, semantics, capture, and input with a new generation. The
exact committed source matched inside Windows and passed portable plus native
.NET 8 checks. A fresh ready observation and clean stopped identity assertion
promoted that same private target to development/ready-base duty, and a
disposable marker proved discard-on-release.

**Current:** The implementation under [`src/`](../src) provides the first
Windows service/session vertical slice. It composes pinned Cua at Medium
integrity with owned native UIA/Win32 ordinary and protected routes behind one
facade. VM and physical x64 evidence covers compact system-shell control,
local/remote parity, genuine UAC secure-desktop approve/cancel, High-integrity
fixture control, lock, logout, stock PIN/password login, provider
failure/recovery, and restartable helpers. Physical recovery also proved that
the dual-boot lifecycle must reselect Windows after one-shot EFI `BootNext`;
once selected, SSH, the automatic service, a new generation, and the Medium
helper returned.

The clean-appliance slice adds architecture-detected transactional bootstrap,
installed runtime/provider digest checks, required WPF native companions,
semantic UIA value mutation, sustained Calculator and Notepad effects through
both placements, clean shutdown, a stopped retained seal, and a successful
disposable verification boot. Its source-target selection deviation is
recorded in Tactical 005 and does not weaken the explicit-target requirement.

**Current:** The next slice closed the gaps exposed by that milestone. The
testbed now fails mutation closed against a provider UUID and target role, and
MachineControl bootstrap validates that assertion. The facade activates
registered applications through `IApplicationActivationManager`, controls
window lifecycle through UIA `WindowPattern` with independent readback, and
supports full, compact, and digest-matched unchanged observations.

Calculator, Settings, Character Map, and Notepad pass from
authenticated-remote and target-local placements with independent app,
semantic, window, file, capture, and cleanup effects. The latest clean-ISO
candidate exposed separate packaged-app content and frame HWNDs; activation
now reports both rather than pretending either one is the complete surface.
Native UIA uses the content HWND while full capture and lifecycle use the
associated frame when present. Calculator compact/unchanged ratios were
70.2%/6.0% remotely and 69.4%/5.3% locally; Settings measured 77.3%/25.6% in
both placements.

The authoritative testbed also generalized a live ARM64 candidate after
explicit BitLocker and per-user AppX preparation, observed Sysprep shutdown,
exported a stopped private UTM bundle and manifest, and reached Windows OOBE in
a non-persistent boot. A later blank ARM64 candidate completed the unattended
path from Microsoft's public multi-edition ISO through Windows 11 Pro build
26200, left unactivated in notification state. The public installation-only
Pro setup key selected the edition; no customer activation key was used.
Setup, injected drivers, staged media removal, first-login guest tools and SSH,
target-attested MachineControl installation, UAC, local/remote applications,
pre-login resident control, stock password login, disk-only reboot, and exact
cleanup all have live evidence in Tactical 007 and the testbed
[image-factory runbook](../platforms/windows/docs/image-factory.md).

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
- Cua is the installed ordinary-session adapter for bounded semantics,
  snapshot-scoped action, and exact capture. The owned native provider covers
  taskbar and shell projections, window lifecycle/state, fallback capture and
  input, session truth, and protected desktops. A live WinApp differential did
  not demonstrate an operation-level advantage over this composition, so
  WinApp remains an external testbed comparison rather than an installed
  runtime dependency. No provider owns the project contract, lifecycle,
  protected authority, or recovery boundary.
- Registered/package activation and application-frame association use owned
  Windows Shell APIs. The activation result identifies a settled primary
  content HWND by preferring the process returned by Windows and separately
  reports an associated `ApplicationFrameWindow` when present. This preserves
  the exact UIA content root while giving capture and lifecycle operations the
  complete frame surface. Native UIA `WindowPattern` is the primary
  window-state route because live
  packaged-window acceptance showed intermittent Win32 `ShowWindowAsync`
  no-effects; Win32 remains a disclosed fallback.
- Repeated observations may request an explicit compact projection and provide
  a prior content digest. Matching unchanged state suppresses elements only
  when the digest scope matches; full fidelity remains caller-selectable.
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

The current implementation uses the completed Cua and system-shell evidence
rather than repeating it. Its owned facade/session proxy routes each operation
through Cua or the measured native shell/protected adapter and reports the
actual route, fidelity, foreground consequence, delivery, and independent
effect. PowerShell, SSH, WinApp, and narrower native components may remain
transports, differential routes, or adapters behind the facade. The product
boundary is the target controller, not any one adapter.

The cross-platform ownership boundary, hybrid-first rationale, correctness
oracles, and criteria for eventually forking or replacing Cua are recorded in
the
[provisional provider composition](architecture.md#provisional-provider-composition).

## Research and option status

**Current:** The [Windows research report](../research/platforms/windows.md)
is the single entry point for the candidate matrix and completed
investigations. It records:

- Cua source review and live normal/elevated/UAC/lock/session experiments;
- the WinVM/WinApp relay, its UIA/WebView/effect limits, and the Tactical 004
  differential that kept it outside the installed runtime;
- Open Computer Use as a source-reviewed compact cross-platform comparison;
- Cua-plus-native, WinApp-centered, and owned-native architecture options; and
- source-reviewed and search-triage alternatives that have not earned a live
  experiment.

**Decision:** The implemented architecture is a small owned Windows
facade/session proxy with a Cua common-runtime adapter, an owned native
UIA/Win32/Shell adapter for measured gaps, and a separate protected Windows
plane. WinApp remains replaceable differential evidence. The protected
interface and arming remain narrow even though the authorized desktop control
on a dedicated appliance is complete.

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
and frame placement. Tactical 004 connected it behind the facade, while the
installed native adapter covers Cua-invisible shell surfaces, bounded
taskbar/Settings projections, pattern-aware state effects, session/protected
boundaries, and alternate exact-window capture.

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

### Contract evolution

**Current:** The executable `machine-control/v0` facade now projects
machine-readable provider inventory and routing, generation-scoped provider
references, compact observation, capture extent, actual route, delivery,
effect, uncertainty, retries, and fallback. The arbiter selects Cua or the
Windows provider per operation without exposing their request vocabularies.

**Open:** Evolve this exercised vocabulary toward a common multi-platform SDK
without freezing Windows-specific implementation details as universal wire
semantics. Artifact transfer and controller-level recovery requests remain
separate decisions.

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

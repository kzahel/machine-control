# Tactical 002: Windows Full Target-Native Control

Status: complete; started and completed 2026-08-09.

Topics: `windows-resident-control`, `architecture`, and
`capabilities-and-results`.

Parent tactical:
[`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md).

Precursor:
[`001-windows-system-shell-acceptance.md`](001-windows-system-shell-acceptance.md).

## Objective

Turn the Windows investigation into a complete target-resident control stack
that works on a VM or physical Windows computer without a hypervisor/KVM route.
An authorized local caller and an agent elsewhere must use the same compact
facade to control the ordinary user desktop, elevated applications, the UAC
consent desktop, and session/lifecycle transitions.

Medium integrity is the least-privileged request origin used to prove a real
Windows elevation transition; it is not the system's authority ceiling. A
dedicated-test-appliance deployment may explicitly arm complete protected
desktop observation, semantic inspection where available, capture, keyboard,
and pointer control. The protected implementation must remain typed,
auditable, and separate from arbitrary SYSTEM command execution.

The hybrid facade is an implementation means, not the milestone. Completion
means Windows itself is deeply and efficiently controllable from target-native
components.

## Completion conditions

- A deliberately owned runtime repository contains the facade, provider
  interface, Windows service/session components, contract fixtures, and build
  instructions. Documentation, spike, testbed, and runtime ownership remain
  distinct and `SYSTEM-MAP.md` records the new boundary.
- An automatically started Windows service survives reboot, discovers the
  active console or RDP session, reports the current input desktop honestly,
  and starts or reconnects the appropriate interactive-session component.
- One interface supports local IPC and authenticated outside use. SSH or a
  tunnel may carry remote calls in this slice, but local versus remote callers
  use the same operations, target identities, capability descriptions, and
  result semantics.
- Ordinary control covers the desktop root, Explorer, Start, Search, taskbar,
  notification area and overflow, Quick Settings or equivalent flyouts,
  Windows Settings, context menus, ordinary dialogs, application switching,
  and window lifecycle/state without host input.
- The facade composes Cua with deep Windows UIA/Win32 routes per operation;
  WinApp is added only where differential evidence demonstrates an advantage.
  Results disclose attempted and actual providers, semantics/capture fidelity,
  coordinate space, delivery mode, focus/cursor consequence, effect, evidence,
  and uncertainty. Provider fallback is never silent.
- Semantic observations are compact and scoped. Representative shell tasks
  record element count, serialized bytes, approximate model tokens, latency,
  observation/action round trips, and irrelevant-tree omissions. No routine
  action requires an unbounded desktop tree.
- A genuine Medium-integrity process requests elevation while UAC and secure
  desktop remain enabled. The target-resident protected route detects the
  desktop transition, captures and controls the consent experience, approves
  and cancels separate harmless cases, and controls the resulting High-
  integrity application without outer input.
- Protected control covers the richest Windows-supported surface across the
  ordinary `Default`, UAC `Winlogon`, locked/logon, and unknown input-desktop
  states. Where UI Automation is unavailable, target-local pixels and input
  are an explicitly reported ordinary protected fallback rather than a host
  route.
- Lock, logout/no-interactive-session, reconnect, provider crash, helper
  recreation, revocation, and reboot produce truthful state and deterministic
  recovery. Credential entry is never stored in this repository and requires
  an explicitly authorized secret/human provider when a test needs it.
- A representative build and control flow runs on physical x64 Windows with
  the same architecture and no VM-host capability. Architecture-neutral code
  and Windows ARM64/x64 artifacts remain distinguishable.
- During conformance, the executing agent has no UTM/QEMU/hardware-KVM input
  tool. Outer observation may provide an independent oracle and outer control
  may recover a failed target afterward, but either route makes that individual
  control case fail.
- The test appliance returns to its prior policy, settings, process, artifact,
  and lifecycle state, or the result records a deliberately retained installed
  runtime and its removal path.

## Full-control state matrix

| State | Required target-native behavior |
| --- | --- |
| Logged-in Medium application | Rich semantics, exact-window capture, background-first actions, and independent effects |
| High-integrity application | Richest available semantics/capture/input from an authorized elevated or protected session component |
| UAC consent on secure desktop | Detect `Winlogon`, capture it, inspect semantically where Windows permits, approve/cancel through target-local input, and observe return to `Default` |
| Locked or login desktop | Report the actual desktop/session state, provide armed protected capture/input, suppress ordinary-user metadata by policy, and never claim an unlock without an authorized credential effect |
| No interactive user | Keep service health and administration available, report desktop UI unavailable, and attach a session component after login |
| Session switch or RDP transition | Rebind helpers, references, capture, and input to the authoritative active session and invalidate the old generation |
| Reboot/provider crash | Restart deterministically, expose degraded readiness during recovery, and reject stale authority and references |

## Architecture under test

```text
local caller -------------------------- local IPC ---+
                                                    |
outside caller -- authenticated SSH/tunnel --------+-->
                                                        owned facade/service
                                                          - target/session truth
                                                          - authorization profile
                                                          - provider arbitration
                                                          - normalized results
                                                          - lifecycle/revocation
                                                               |
                         +-------------------------------------+------------------+
                         |                                     |                  |
                  normal session                       protected session    administration
                  Cua + WinApp/UIA                     service/helper       native OS routes
                  native shell gaps                    input desktop        typed operations
                                                      UIA/capture/input
```

The Windows service/session design should be compared live with RustDesk's
installed-service behavior. RustDesk is a capability and lifecycle benchmark,
not a code donor or semantic contract: its AGPL-3.0 license, broad authority,
and human pixel-streaming product boundary remain explicit.

## Boundaries

- Do not disable UAC, secure-desktop prompting, UIPI, lock, or Windows session
  isolation to manufacture a pass.
- Do not accept running the entire agent or ordinary semantic runtime as
  SYSTEM merely because it controls the test appliance. Protected authority
  remains a separable deployment component and capability set.
- Do not expose an arbitrary SYSTEM shell, registry editor, file API, provider
  dispatcher, or self-modifying policy surface through the protected broker.
- Do not automate or commit passwords, PINs, recovery codes, pairing material,
  private endpoints, target identifiers, or personal screen contents.
- Do not use RustDesk source in the owned implementation without a deliberate
  AGPL-compatible decision and dependency/license audit.
- Do not freeze a universal cross-platform wire protocol, implement macOS or
  Linux, integrate YA worker placement, or seal the final golden image in this
  tactical.
- Do not count a provider acknowledgement as an application or desktop effect.
- Do not count outer pixels or input as success, even during UAC or lock.

## Implementation steps

### 1 — establish target and benchmark baselines

Run the authoritative WinVM diagnostic and preserve the prior stopped/running
state. Verify genuine UAC-enabled Medium and High integrity, current Cua and
WinApp behavior, service-install authority, build prerequisites, and available
physical-Windows target declarations. Run a bounded installed RustDesk UAC and
desktop-transition comparison if it can be isolated and completely removed.

### 2 — create the owned runtime boundary

Create a deliberately reusable runtime boundary in this repository rather than
placing product code in the research spike or WinVM. Define the smallest
versioned request/result types needed by this tactical, a provider adapter
boundary, deterministic fixtures, architecture-neutral build outputs, and
public-repository safety rules. Record that ownership in `SYSTEM-MAP.md`.

### 3 — install service and session supervision

Implement an automatic Windows service with authenticated local IPC. Discover
the active console/RDP session and current input desktop. Start, monitor, and
recreate an interactive helper at the authority needed for the selected
operation. Bind session, desktop, provider, and runtime generations to every
reference and protected grant.

### 4 — compose the ordinary Windows plane

Adapt Cua for compact ordinary-window semantics/capture/actions and WinApp or
narrow native UIA/Shell operations for the measured system-shell gaps. Route
per operation through the owned facade. Repeat and extend Tactical 001 across
Explorer, context menus, notification overflow, Quick Settings, Settings, and
window/application lifecycle.

### 5 — prove efficient semantic control

Add bounded scopes and query projection for the desktop root, taskbar, Start,
Search, a flyout, Settings, dialogs, and exact application windows. Measure
serialized size, estimated tokens, latency, and agent round trips. Compare with
the existing ChromeOS ergonomic reference and retain raw provider trees only
as target-local diagnostics.

### 6 — cross UAC and elevated application boundaries

From a genuine Medium requester, launch harmless approve and cancel elevation
fixtures. Detect the `Default` to `Winlogon` transition, inspect or capture the
consent surface, deliver protected input from inside Windows, and observe the
return transition. Control the resulting High application semantically where
possible and through explicitly reported target-local pixels/input otherwise.

### 7 — cover lock, login, and session transitions

Exercise lock, no-interactive-session, login/reconnect, helper crash, console
or RDP rebinding where available, and runtime restart. Prove truthful state,
reference invalidation, protected-policy behavior, and recovery without making
credential automation a hidden prerequisite.

### 8 — prove local, remote, and physical parity

Call the same facade locally and through the authenticated outside carrier.
Repeat a representative ordinary and protected flow on physical x64 Windows.
Record legitimate build, transport, latency, and artifact differences without
changing the conceptual operations or result semantics.

### 9 — validate failures, cleanup, and ownership

Withhold outer control from the acceptance caller. Test refused authority,
wrong desktop/session, stale generation, failed provider, unavailable
semantics, visual fallback, revoke, and uncertain completion. Restore mutated
state, uninstall experimental benchmarks, preserve only deliberately adopted
runtime components, and return the VM lifecycle. Keep adopted conformance here
while disposable third-party pins and testbed lifecycle evidence remain in
their owning repositories.

## Validation record

Execution is complete. This repository's [`src/`](../../src) and
[`tests/windows`](../../tests/windows/README.md) contain the facade, split
Medium/protected session planes, typed service lifecycle operations,
Windows-native provider, deterministic fixtures, and conformance suites.

**Current:** Windows ARM64 VM validation passed ordinary system-shell control,
local/remote parity, genuine UAC secure-desktop approve/cancel, elevated
fixture control, lock, logout/no-user state, helper recreation, revocation, and
reboot. Physical x64 validation passed the same architecture through ordinary,
UAC, elevated, lock, logout, and stock PIN/password login cases. The minimized
measurements and exact deviations live in the
[`physical x64 evidence`](../evidence/windows-physical-x64.md).

**Current:** A generic reboot after one-shot EFI `BootNext` returned the
dual-boot target to Linux and therefore did not test Windows restart. After the
testbed explicitly selected Windows again, Windows SSH authenticated, the
automatic runtime returned with a new generation, and its Medium helper
reattached. The earlier suspected pre-login SSH failure was the Linux service,
not a Windows carrier defect.

**Final:** Physical cleanup is verified and the deliberately adopted runtime
remains installed. The VM retains the final runtime, its original UAC policy,
no tactical staging or captured evidence, and its prior stopped lifecycle.
[`Tactical 004`](004-windows-provider-composition-and-agent-ergonomics.md)
connected digest-pinned Cua to the owned facade, made provider capabilities and
routing executable, passed the ordinary shell and protected regressions on
ARM64 and physical x64, and proved provider timeout, crash, absence, stale
identity, fallback, and recovery behavior.

**Decision:** A live WinApp differential found no tested operation for which
installing another adapter improved reach, fidelity, effect observability, or
ergonomics over Cua plus the owned native UIA/Win32 routes. Retaining WinApp as
an external testbed comparison deliberately satisfies the composition
condition without making its package a product dependency. All completion
conditions are closed; broader authorization hardening, environment coverage,
and image sealing are later program work.

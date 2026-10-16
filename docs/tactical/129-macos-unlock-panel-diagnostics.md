# Diagnose covered-unlock password-panel discovery

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: bounded VM reproduction and source diagnostics complete; the reported
physical password-panel failure remains unexplained.

## Objective

Investigate an approved covered session that ended with
`unlock_password_panel_unavailable` despite healthy advertised prerequisites.
Use the macOS VM for disruptive reproduction and preserve console/process
identity, ordinary authorization, cover ownership, cancellation and relock.

## Completion conditions

- Establish the running build rather than infer it from checkout HEAD.
- Distinguish actual activation, application effect and independently read lock.
- Explain discovery failures without reading password values or UI text.
- Avoid speculative input broadening or retry-window changes.
- Restore VM configuration, release claims and retain private evidence privately.

## Boundaries

Existing one-display ARM64 macOS 26.6.2 VM, temporary workstation approval
profile and signed desktop 0.6.1. No physical-host lock, app replacement,
permission change or credential submission. The VM's native operator setup and
timed observe/control approval are test preparation, not new agent API authority.
No browser login or business action is repeated.

## Ordered work

### 1 — identify the installed build

Read bundle version, sealed source revision and signature identity. The current
selected host's desktop 0.6.1 declares source revision
`de253841f10c9df1da457dc5cd4780d20c9bfd68`.
Its trigger source is unchanged in the investigation checkout. Strict resource
verification finds added Python bytecode caches; deleting those added caches
from the VM staging copy restores verification without changing signed code.
This integrity finding does not establish the cause of password-panel failure.
The requested originating claim is absent from this controller's retained audit;
coverage is incomplete, so the originating failure's installed version and
bytes remain unproven.

### 2 — exercise bounded covered control

The first VM trial ends with `disabled`, then reports a helper
`owner_disconnected` pause and revoked access. It does not isolate a password
panel fault. After recovery and fresh ordinary approval, a second trial reaches
one-display covered activation on the unchanged signed build. Independent IOKit
readback observes unlocked state. The fixture oracle confirms AX, pointer and
keyboard effects. Filtered native capture, completion, independent IOKit relock,
zero remaining covers/owner and unchanged ordinary approval pass.

Move the acceptance runner's application enumeration after activation. Its
independent file oracle binds the fixture PID before startup; the exact single
semantic fixture is checked after activation and before any fixture effect.
This makes locked-origin acceptance obey the ordinary locked-desktop gate.
Owner cleanup now runs even if final status inspection refuses or is busy.

### 3 — distinguish discovery failures

Replace the trigger's undifferentiated missing-field result with fixed,
secret-free suffixes for unavailable windows, absent/ambiguous login windows,
AX read failures, traversal limits, and absent/ambiguous/disabled/unfocused
password fields. Unexpected AX read failures refuse even when another field
looks usable. Keep the original PID resolution, enabled/focused secure-field
requirements, node/depth bounds, Return targeting and retry window.

### 4 — validate and restore

All 215 Swift tests pass, including metadata-only discovery tests that reject
password-value reads. ARM64 and Intel native app assemblies and their signature
verification pass; macOS static smoke and Python compilation pass. The new
diagnostics have not been installed on the physical host or accepted through a
live covered-unlock trial. The successful VM trial used unchanged 0.6.1 code.

The outer secret transport is explicitly unavailable, and graceful guest
shutdown lacks cached administrator authority. Documented bounded stop/start
recovers the prepared autologin VM. Reboot clears guest temporary staging,
including the initial development-app backup; restore a source-built development
resident rather than claim byte-identical rollback. Restore appliance policy,
disabled locked use and remove the temporary helper through native setup.
Exact identities, evidence and recovery friction remain in private journals.

**Current:** restoration verifies the source-built development app's signature
and matching build hash, original root-owned appliance policy, original disabled
preference, no helper installation, no active owner/covers, and healthy ordinary
resident/AX/capture/input. Temporary guest artifacts are removed. Helper service
registration is removed with the temporary helper; this is functional baseline
restoration, not byte-identical restoration of the original bundle or service
registration. The existing controller credential locator remains ready.
The VM returns to its original powered-off state and both task claims are
released; no covered session or temporary native test process remains.

## Final result and open work

**Current:** covered unlock works in the bounded one-display VM completion cell.
The reported physical `unlock_password_panel_unavailable` is not reproduced.
The separate initial `disabled` ending remains inconclusive; expiring helper
observations are a hypothesis, not an established cause.

**Open:** run a separately authorized physical trial with the diagnostic build
and correlate its exact suffix with password-panel and display transitions.
Touch ID entry, multiple displays, delayed panels, event delivery and focus
remain unqualified. No timeout increase, global input fallback or weakened
identity/focus check is justified by this evidence.

# 107 — Runtime and presentation

Status: active; Mac implementation and qualification underway.
Owning topics: [runtime and presentation](../../topics/runtime-and-presentation.md),
[host control](../../topics/host-control.md), and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

Make control independent of the settings UI, then offer personal, minimal and
appliance presentation in one existing package/release stream. Preserve the
same resident authority, providers and local/remote CLI contract. Operators
can always reopen Settings and reset presentation through supported controls.
Presentation changes never change trusted deployment policy.

First independently deliverable milestone: existing Mac personal presentation
stays responsive during delayed, missing and interrupted helper status/session
observations, with no unbounded poll queue and no late-result authority revival.

## Boundaries

No new installer family, public profile release, provider rewrite, privilege
expansion or protected-session redesign. Keep the current default and signed
identity. Do not replace the controller user's installed app or alter a target's
policy as part of planning. Dedicated target trials use doctor, exact target-use
claims and cleanup; fresh provisioning also uses the private journal and
credential handoff. Preserve existing appliance implementations during migration.

Create bounded child tacticals when implementation starts on later milestones;
this document owns sequencing, not duplicate execution logs for every platform.

Implement milestones 1–4 and their native acceptance on Mac first. Run cheap
shared frontend/contract checks and review other platform interfaces throughout;
defer Windows/Linux integration campaigns to milestone 5. Prefer an available
native Windows development host or CI runner for candidate builds and claimed
targets for deployment/effects. Linux placement may use native/CI or VM
facilities after checking availability. Do not assume a private host is
available or force every platform build onto the Mac controller's VMs.

## Ordered work

### 1 — make existing Mac status work nonblocking

Inventory blocking work and thread-affinity requirements in `ResidentServer`,
`ResidentService`, locked-use permission/status, the Swift operator bridge and
Tauri command scheduling. Distinguish display-only reads from authoritative
pre-effect checks and lifecycle operations before changing call sites.

Introduce bounded asynchronous helper/session observation with injectable
dependencies for deterministic tests. Use immutable display projections and
coalesced refreshes for tray and settings. Separate physical-activity monitoring
from slow helper discovery so a status delay cannot stop its publication.
Treat unknown helper/session readiness conservatively without reusing a last
good observation as new authority or clearing a pause based on missing data.

Replace blocking receives inside async Tauri commands with an awaited completion.
Bound queued work as well as active work; caller timeout alone does not cancel a
queued action. Use operation-specific deadlines, distinguish undispatched
cancellation from unknown delivered effects, and reject superseded completion.
Fence Stop locally before asynchronous cleanup. Keep independent watchdogs.

Acceptance: injected delayed/nonreplying status dependencies leave the main
event loop, operator status and Stop responsive. Repeated polls stay bounded.
Grant/session changes invalidate completions and prevent effects. Existing
approval, physical takeover, pause, protected watchdog and update exclusion
checks continue to pass. Investigate helper latency independently if still
present; hiding it from the UI is not proof that the helper is healthy.

### 2 — extract runtime ownership from presentation

Centralize construction/lifecycle now duplicated by the AppKit resident and
Tauri bridge. Define typed runtime state/events and operator intents. Retain
one serialized authorization/session owner; isolate UI-affine methods and
blocking providers individually. Keep the authenticated operator channel
distinct from public agent operations.

Acceptance: existing native and Tauri shells use that boundary, client operations
retain their contract, and starting a second presentation attaches to the same
runtime. Verify outside-agent access still needs no in-target agent. Review
the existing Windows/Linux service/session/operator interfaces when shaping the
boundary; defer their native integration proof to milestone 5. Do not force
identical process placement across platforms.

### 3 — make Settings optional and independently recoverable

Create Settings on explicit demand instead of retaining a hidden polling
WebView. Native notice/approval/Stop presentation remains usable independently
of it. Closing/reopening Settings leaves runtime owners, policy and lifecycle
unchanged. Minimal mode does not instantiate the full settings frontend until
requested; hiding an already running window does not satisfy this milestone.

Acceptance: no settings WebView or its polling when dormant; required notices
and approvals, Stop, open/close/reopen, single-instance forwarding and browser
control work. Verify permission and updater identity/lifecycle on a signed
candidate before accepting deployment.

### 4 — add presentation preferences and recovery controls

Implement the versioned presentation setting, explicit personal default,
Settings selector, supported local provisioning/reset commands and temporary
open-Settings launch path. Reuse one atomic configuration implementation and
define operator authority. Preserve active tasks or require an explicit bounded
transition; never silently restart on a configuration edit.

Acceptance: all three profiles can open Settings and return to personal
presentation without manual file removal. Invalid/missing configuration,
reboot, second launch and interrupted writes have deterministic behavior.
Changing presentation never changes grants, policy, protected installation or
credential custody. Approval-required configurations cannot become unattended
by selecting appliance presentation.

### 5 — qualify the shared package on desktop and appliance

Adapt platform presentation adapters to the same semantics; reuse Windows and
Linux residents and their platform permission requirements. Prove guest-local
CLI and outside-agent parity on a claimed Windows appliance, with its VM
console absent. Qualify Mac signed identity/TCC and Linux graphical-session
and portal requirements separately. Preserve supported capability omissions.

Acceptance: each advertised profile passes startup, approval/policy, Pause/Stop,
settings recovery, CLI/native effect, owner loss, restart and update checks for
its claimed platform scope. Publish using the existing package stream only
when explicitly authorized and qualified; defaults remain personal meanwhile.

Use exact-source Windows native contracts, format verification and x64/ARM64
publishes on the selected native build host/CI. Reuse Linux native checks and
its GNOME/portal acceptance targets. Compilation alone is not installed
behavior evidence, and successful Mac acceptance does not cover either OS.

## Validation and final result

**Current:** First source slice implemented: bounded background observations,
nonoverlapping UI refresh and asynchronous operator completion. Swift tests
include blocked dependency, main-queue Stop, expired snapshot and late-result
refusal. Existing approval/session suites pass. Installed acceptance and the
remaining runtime/presentation milestones are still in progress; the host
installation and public release are unchanged.

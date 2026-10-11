# Runtime and presentation

Topic: `runtime-and-presentation`

Status: Mac source implementation complete; signed qualification active. [Tactical 107](../docs/tactical/107-runtime-and-presentation.md)
coordinates the migration.

## Current boundary and evidence

**Current:** The common CLI is a client of the target resident; it is not a
replacement desktop controller. The Mac Tauri package embeds the Swift resident
and its operator bridge. The standalone AppKit resident reuses the same native
implementation but still creates a menu bar and native operator UI. Windows
and Linux already have separate resident/session components and appliance
deployments. See [host control](host-control.md),
[installed CLI](installed-agent-cli.md), and the
[system map](../SYSTEM-MAP.md).

**Current:** Installed Mac 0.5.8 polling and operator state reads performed
synchronous helper IPC on the application main thread. Bounded installed-process sampling
caught repeated waits there. The [Mac platform report](../research/platforms/macos.md#resident-responsiveness)
owns evidence and limits. This establishes a responsiveness problem, not the
helper's underlying reason for slow replies.

**Current:** The first Mac slice moves idle helper/session and helper-approval
observations to bounded workers, exposes expiring display snapshots, preserves
protected pauses when helper state is unknown, coalesces frontend refreshes,
and awaits native operator completion without blocking the async executor.
Fresh action checks remain separate. Fault fixtures hold a helper open while
resident ticks and local Stop continue; installed acceptance follows later.

## Product direction

**Decision:** One reusable logical runtime serves three presentation profiles
within the same app/package and release stream. Reuse platform providers,
authorization, admission, audit, sessions and CLI contracts. Platform-specific
languages, session placement and protected helpers remain appropriate; this is
not an all-platform runtime rewrite.

| Presentation | Intended behavior |
| --- | --- |
| Personal | Settings, tray/menu bar, access status, approvals, notices, Pause and Stop |
| Minimal | No persistent settings WebView; native approval/notices and accessible operator recovery and Stop |
| Appliance | Quiet unattended startup with optional local settings/diagnostics; authorization comes from separately provisioned policy |

**Decision:** Presentation and authorization are independent. A presentation
setting cannot install a protected provider, grant access, enable standing
authorization, remove required human consent, or select an appliance provider
as a fallback. Existing administrator-controlled deployment policy remains
authoritative. A missing or invalid presentation preference defaults to
personal without changing authorization.

An appliance presentation on a workstation still requires workstation
approval. Required approval and safety presentation must be available, or the
request refuses; hiding routine windows cannot bypass a human gate. Conversely,
opening personal Settings on an appliance does not revoke or replace its
trusted policy. Show the actual authorization policy distinctly from the
presentation choice. Returning to personal use includes explicit removal of
unattended authorization where it was provisioned.

**Decision:** UI-free operation does not mean a desktop-free target. Ordinary
desktop providers still require their supported graphical/session environment
and OS permissions. VM control runs inside the guest even when its hypervisor
window is absent. Do not infer appliance privileges from VM detection.

## Execution boundary

**Decision:** Separate serialization from UI thread affinity. Keep a serialized
owner of mutable authorization/session state, but give it short transitions
and asynchronous continuations rather than blocking socket/process/provider
waits. Main-thread-only OS/UI work remains bounded and explicit. Initially
retain existing process placement and signed identities.

**Proposal:** Use three responsibilities:

- A control coordinator owns grants, admission, operation ordering, generations,
  cancellation, update exclusion and runtime lifecycle.
- Bounded workers perform helper IPC, session probes, provider work and durable
  writes. Each dependency has deadlines, bounded concurrency and a declared
  thread-affinity requirement; moving everything to a global queue is unsafe.
- Presentation adapters consume immutable status and event projections and
  send typed operator intents. Settings, native notices and agent clients do
  not implement parallel authorization state machines.

**Decision:** UI status is a display projection, not an authorization cache.
It records observation time, generation and refresh/error state. Read-only
polls coalesce; timed-out callers cannot leave an unlimited queue of native
work. Slow or unavailable dependencies are visible without blocking menus.

Before effects, acquire the required fresh session/provider observation and
revalidate the live grant, owner, pause and generations. Results arriving after
revocation, owner loss, restart or a generation change cannot restore access,
resume paused admission, or retarget a stale reference. Unknown readiness
blocks affected control. Preserve independent input latches and protected
watchdogs while moving work; do not put them behind the worker they supervise.

**Decision:** Stop fences new dispatch and signals cancellation immediately;
it does not await slow helper acknowledgement before changing local authority.
Protected cleanup/relock continues through its existing independent mechanism.
Report pending or uncertain cleanup honestly, without replaying an action.

## Configuration and recovery

**Decision:** The same installed app can always explicitly open Settings in
every profile. Opening Settings is temporary presentation, not a saved mode
change or policy change. Provide a Settings selector and a supported local
configuration/reset CLI so recovery never depends on locating or deleting a
special file. Configuration mutation belongs to the operator/admin surface,
not the public agent action endpoint.

**Proposal:** A versioned per-installation presentation preference has explicit
defaults and atomic updates. Settings and the provisioning CLI use one
implementation. A temporary launch override takes precedence over the saved
preference and does not write it. Single-instance forwarding opens Settings in
the existing runtime rather than starting a second resident. Invalid values
produce a diagnostic and fall back to personal presentation.

**Current (source/built):** Mac uses `machine-control-presentation/v1` in an
owner-only atomic file beside the resident socket. Settings and local
`machine-control presentation status|set PROFILE|reset` use the same store.
Changes apply without restart and defer during pending approval. `--settings`
recovers a lazy Settings window; `--presentation PROFILE` is temporary.
This same-user operator surface is independent of agent socket operations
and does not provide containment against a same-user shell. See the
[desktop guide](../desktop/README.md#mac-presentation-and-recovery).

## Migration and qualification

**Decision:** Implement and qualify this refactor on Mac first: remove observed
polling stalls while retaining personal presentation, extract the
runtime/operator boundary, make Settings lazy, then add profile
configuration/recovery. Run shared frontend/contract checks throughout and
review existing Windows/Linux interfaces before claiming a portable boundary,
but defer their integration/build campaigns until the Mac slice is proven.
This is sequencing for the observed Mac execution/presentation concern, not a
change to the broader target-control North Star or its Windows vertical slice.

Reuse the existing Windows and Linux separation for later platform acceptance.
Prefer an available native Windows development host or CI runner for builds,
then deploy exact candidates to claimed test targets; do not require builds in
a slow local Windows VM. Select Linux build and test placement from available
native/CI or VM facilities. Keep defaults and release behavior unchanged until
each new profile passes its acceptance gates; Mac proof alone is not
cross-platform qualification.

**Current (source/built):** The Mac runtime and three profiles are implemented;
[Mac acceptance](../docs/tactical/108-macos-runtime-presentation.md) is underway.
**Open:** Signed installed three-profile qualification is not yet complete. Process separation on Mac is a later evidence-based choice:
account for TCC ownership, code identity, authenticated operator IPC, updater
lifecycle and browser integration before changing it. A runtime remaining
responsive with a deliberately stalled dependency is the first completion
gate, not a new installer or public headless release.

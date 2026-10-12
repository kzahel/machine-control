# Runtime and presentation

Topic: `runtime-and-presentation`

Status: all three desktop platforms implement the shared presentation design.
Bounded native qualification covers Mac ARM64, Windows x64 and Linux x64 GNOME
Wayland at their recorded revisions. Combined-source package qualification,
remaining architectures and production release remain separate.
[Tactical 107](../docs/tactical/107-runtime-and-presentation.md) coordinates the
migration.

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
resident ticks and local Stop continue. Signed candidate qualification is
recorded in [Mac acceptance](../docs/tactical/108-macos-runtime-presentation.md).

**Current (Mac hardening):** Resume now waits through one asynchronous operator
dependency. Native preflight has a caller deadline and admission-time generation
fence; timeout/Stop cannot dispatch late work under a new grant. Slow replies
share bounded capacity with handshakes. Delegation-status discovery no longer
writes action audit. Combined blocked-dependency fixtures and exact signed
ARM64 host load/recovery pass; [hardening](../docs/tactical/109-macos-runtime-hardening.md)
owns measurements and remaining synchronous lifecycle paths.

**Current (Linux candidate):** The existing ordinary-user Python/AT-SPI resident
uses one physical provider slot, cancellation/deadline fences and asynchronous
session/portal setup. Separate native approval and safety processes preserve
Pause/Stop without Settings; losing safety presentation revokes access. Local
preferences and recovery are distinct from the public agent socket and root
appliance authorization. [Linux acceptance](../docs/tactical/111-linux-runtime-presentation.md)
owns exact x64 native effects, all three profiles, browser, faults, restart,
local/outside CLI parity and remaining limits. A private GLib coordinator and
one persistent AT-SPI worker preserve context affinity. Provider deadlines
retain physical capacity; native approval children retain their slot through
kernel reaping. Disposable Settings and local recovery remain independent of
public-socket saturation and provider work.

## Product direction

**Current (Windows):** Tauri schedules companion IPC and lifecycle work away
from its event thread. One bounded provider worker retains capacity through
late completion, and admission-time authority fences prevent replacement
grants from reviving old work. Stop posts to an inherited, process-bound
native message window independently of IPC; Quit terminates the owned job.
The .NET resident owns native approvals and notices with Settings absent.
Windows implements lazy Settings, personal/minimal/appliance preferences,
same-runtime recovery, local configuration and restart-expiring overrides.
[Windows acceptance](../docs/tactical/110-windows-runtime-presentation.md)
owns exact-source builds, native fixture evidence and signing limits.

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

**Current (Mac source):** The implementation uses three responsibilities:

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

**Current (Mac source):** A versioned per-installation presentation preference
has explicit defaults and atomic updates. Settings and the provisioning CLI use one
implementation. A temporary launch override takes precedence over the saved
preference and does not write it; it expires on Restart. Endpoint-specific
forwarding opens Settings in the existing runtime rather than starting a second
resident. Invalid values
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

**Current:** The Mac runtime and all three profiles pass bounded signed ARM64
VM acceptance, native approvals/effects/restart and Settings recovery. Browser
control works with Settings absent; standing policy survives Stop/Resume and
personal recovery. Intel packaging and bounded physical-host responsiveness
checks pass. [Mac acceptance](../docs/tactical/108-macos-runtime-presentation.md)
owns exact candidate evidence and limits; no public release was performed.

**Open:** Linux ARM64 qualification for these changes, production signing and
installed/updater acceptance; Windows publisher signing, native ARM browser/GPU
qualification, Intel Mac GUI execution and broader
protected/physical qualification. Process separation on Mac remains an
evidence-based choice:
account for TCC ownership, code identity, authenticated operator IPC, updater
lifecycle and browser integration before changing it. A runtime remaining
responsive with a deliberately stalled dependency is the first completion
gate, not a new installer or public headless release.

**Current, acceptance review:** the three platform campaigns qualified different
source revisions. Later Windows/Linux work changes shared Tauri lifecycle and
frontend code while preserving the Mac Swift runtime/bridge and Windows .NET
runtime. Current-source checks and Mac builds do not retroactively qualify a
combined installed package. [Tactical 112](../docs/tactical/112-runtime-presentation-acceptance-review.md)
records the comparison; the [acceptance matrix](../docs/desktop-acceptance.md#runtime-and-presentation-candidate-acceptance)
indexes candidate evidence separately from historical releases.

**Decision:** Next qualify a single combined-source candidate through the
existing six-target package stream. Close Windows ARM64 GUI build/toolchain
and Linux ARM64 build/execution gaps on native hosts or CI, authenticate final
candidate bytes, then run platform-native profile/safety/recovery and installed
replacement campaigns. Repeat Mac effects on the hardened combined candidate;
the original profile VM campaign predates hardening. Protected helper/session
and physical/soak campaigns retain their own scope. Publication remains a
separate explicitly authorized step.

**Current, combined-source Windows ARM64:** optimized GUI/NSIS build and bounded
profile, safety, recovery, native pointer, streaming/browser and outside/local
owner effects pass. Isolated unsigned installer install/repair/uninstall also
passes. Browser effects use x64 emulation with explicit software rendering;
publisher/updater and native ARM browser/GPU qualification remain separate.
[Tactical 113](../docs/tactical/113-arm64-runtime-presentation-qualification.md)
owns this campaign and the pending Linux ARM64 and hardened Mac VM work.

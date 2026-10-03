# 069 — Durable desktop audit trail and diagnostics

Status: implemented; validation results recorded below.

Owning topic: [desktop audit and diagnostics](../../topics/desktop-audit-and-diagnostics.md).
Related topics: [host control](../../topics/host-control.md),
[capabilities and results](../../topics/capabilities-and-results.md).

## Objective and completion conditions

The originating request was to propose a durable audit trail for the desktop
app, together with logs for debugging problems, and save the plan without
implementing. Activity currently presents recent memory-only events; the
[owning topic](../../topics/desktop-audit-and-diagnostics.md) records that
source-reviewed baseline.

**Proposal:** Deliver persistent audit history and correlated diagnostics for
the Windows, Mac, and Linux desktop app. Logging must work with the settings
window closed and through existing local and remote resident entry points.

Completion requires evidence that:

- History survives resident/app restart and package replacement.
- Access decisions, operations, refusals, lifecycle, and failures are recorded
  with truthful acceptance, delivery, effect, and uncertainty.
- A crash leaves interrupted operations identifiable without inventing an
  outcome or replaying input.
- Storage is private, bounded, and excludes secrets and sensitive payloads.
- Activity can inspect retained history, and operators can export diagnostics.
- Audit-storage failure is visible, blocks new control, and never disables
  Stop or revocation.

## Boundaries

**Proposal:** This slice covers desktop-product deployments and their native
residents. Shared contracts should allow later headless/appliance adoption,
without claiming that all platforms or protected services already participate.
Do not change native permissions, grants, claims, provider selection, or
transport ownership. Machine Control owns logging; YA session coordination
and dotfiles private inventory retain their current ownership.

No automatic uploads, telemetry, full request/response recording, screen or
clipboard recording, arbitrary log-file reads through agent APIs, or new
privileged service. Local history is editable by an unrestricted same-user
process or administrator. This proposal does not promise tamper resistance.
The user subsequently authorized implementation, tests on Windows, Mac, and
Linux VMs, and a commit. The ordered proposal below is retained as the original
implementation scope; the result records the concrete behavior and limits.

## Ordered work

### 1 — define the event and diagnostic contract

**Proposal:** Define a versioned schema shared by native implementations, with
event IDs, UTC timestamps, process-local ordering, request correlation,
component/build identity, and runtime/session/desktop/provider generations
where available. Use monotonic timing for elapsed durations.

Audit events cover access requests and approval/denial, expiry, revocation,
emergency Stop, desktop/browser operations, refusals, app/resident startup and
shutdown, session changes, provider failures, and update attempts. Record
operator-originated changes through native handlers as well as agent requests.
Unexpected exits may be identified by a supervisor or on the next startup;
do not claim to record shutdown after the process has already died.

For operations, preserve requested operation, actual route, duration, typed
error, acceptance, delivery, effect, and uncertainty. Absent observations
remain unknown. Do not serialize raw result data or evidence payloads.
Separate OS-observed caller identity from bounded, caller-supplied agent,
claim, or session correlation metadata; attribution is not authentication.
Do not record bearer authority or secret-transport locators.

Diagnostic events cover permission/provider availability, IPC timeouts,
companion exits, startup/restart, and updater errors. They share request IDs
with audit events where applicable. Normal diagnostics are enabled by default;
extra detail is explicitly enabled for a bounded period. Avoid recording the
operator's one-second state polling as an unbounded stream of audit rows.

### 2 — implement private storage and durability on Windows

**Proposal:** Start with rotated JSON Lines files under each platform's
per-user application log/state directory, outside installation bundles. Each
process owns its files; serialize its writes and correlate across components
instead of allowing unsynchronized multi-process appends. Restrict directories
and files to the owning user using native permissions/ACLs, and prevent log
paths from being redirected through unsafe links.

Proposed default retention:

| Stream | Maximum age | Total size cap |
| --- | --- | --- |
| Audit | 30 days | 100 MB |
| Diagnostics | 7 days | 50 MB |

Prune when either limit is reached; define rotation, bounded record sizes,
concurrent reader behavior, and recovery from a partial final record. Account
for all component files when enforcing the stream's total cap. Surface the
earliest retained timestamp and known gaps. Preserve files across updates;
specify uninstall/removal behavior explicitly before acceptance.

Persist and flush control intent to durable storage before provider dispatch,
then persist and flush the result before acknowledging completion. A recovered
intent without a result is outcome unknown. If the action happened but result
persistence failed, return an explicit logging failure with truthful delivery
and uncertainty; do not imply the action was rolled back or safe to retry.
Buffer routine diagnostics separately.

When audit storage is unavailable, expose logging health and suspend new
control. Stop, revocation, and their safe cleanup must still execute, with
best-effort recording. Define which observation, capture, approval, and
lifecycle operations require the same durability gate before dispatch.
Recovery of storage does not grant new access or bypass normal authorization.
Measure flush latency and test native crash/power-loss guarantees rather than
equating an ordinary buffered write with durability.

### 3 — apply the contract to Mac and Linux and retain diagnostics

**Proposal:** Add native audit sinks at authorization/dispatch and operator
transition boundaries. Use the same schema, privacy rules, retention, and
recovery semantics on all three desktops. Retain the current native memory
buffers as an optional fast recent view, not the source of durable truth.

Capture structured supervisor and companion errors without corrupting IPC
stdout. Replace Windows' discarded companion diagnostics with a bounded safe
route; give Linux and Mac equivalent packaged-app coverage. Sanitize errors
at their source: raw stderr and exception strings can contain user payloads.
Rust shell/update diagnostics and native resident diagnostics remain linked
even when a companion fails to start or respond.

### 4 — connect retained history to Activity and operator export

**Proposal:** Activity reads bounded pages of retained events and shows dates
as well as times, operation/outcome filters, expandable details, retention
coverage, and logging health. Keep acceptance visibly separate from delivery
and effect. Log reading must remain responsive during control and rotation.

Add Open log folder and Export diagnostics. Exports include selected time
ranges, correlated audit/diagnostic events, and app/build information. Preview
the export before the operator shares it; never upload automatically. Use
closed native operator methods and bounded queries, not arbitrary file paths.
Do not silently expose historical local audit data to public agent endpoints.

### 5 — prove persistence, failure handling, and privacy

**Proposal:** Use deterministic native tests and injected failures before live
acceptance. Test serialization, retention, concurrent requests/readers,
partial writes, crash between intent and result, and failure after an observed
action. Test disk full, unavailable directory, permissions, and unsafe links.
Prove Stop/revocation still work when logging fails.

Use sentinel secrets and payloads to verify exclusion from both streams and
exports: passwords/tokens, typed text, clipboard contents, screenshots, UI
trees, full URLs, script bodies, raw requests/results, and secret transports.
Metadata must be allowlisted, bounded, and sanitized even in detailed mode.

Run applicable contract/native/frontend checks and Windows formatting plus
ARM64/x64 publishes when runtime implementation is authorized. On isolated,
claimed test targets, verify window-closed local/remote recording, restart and
package-update retention, Activity pagination, exports, and measured control
latency. Use synthetic fixtures; keep private live logs and support bundles
outside Git. Report platform and architecture evidence separately.

## Result and remaining work

**Current:** Implemented the schema, three native journals, private retention,
intent/result durability gate, grant-transition logging, supervisor/update
failure codes, Activity history and local diagnostic preview/export. The
[owning topic](../../topics/desktop-audit-and-diagnostics.md) owns the current
contract and [operator guide](../desktop-audit.md) owns user-facing behavior.

Validation uses synthetic fixtures and isolated candidates on claimed targets;
private evidence and actual target identifiers stay outside this repository.
Acceptance results (2026-10-03):

| Target/profile | Evidence |
| --- | --- |
| Windows x64 desktop VM | 63 live journal checks: intent/result, OS caller PID, payload exclusion, private export, debug bound, restart retention, failed-storage gate, Stop and recovery. Existing desktop-grants fixture suite also passes, with an independent counter and PNG/hash checks. |
| macOS ARM64 Aqua VM | 12 actual Tauri Activity/export checks, failed-storage refusal, Stop, and retention across replacement of an isolated app bundle. Existing control-only desktop acceptance passes visible denial/narrowing, independent fixture effect, self/protected refusal, prompt pause and Stop. |
| Linux x64 GNOME Wayland VM | 48 live journal checks, plus 53 existing native desktop regression checks including AT-SPI effects, portal consent/capture, pointer, drag, scroll, Unicode input, expiry and Stop. |

All three use dedicated candidates, with the installed appliance providing the
ordinary authoritative control/administration route. Windows and Linux tests
exercise the native operator companion; the macOS run also exercises the actual
shared Activity WebView. Resident logging works without an operator settings
window in the companion runs. No signed release or personal workstation install
is part of this acceptance.

Source checks use a plain HEAD archive with only this commit's files overlaid,
so unrelated work in the checkout cannot supply a hidden dependency. Portable
repository checks, six Python journal tests, eight Linux grant tests, 55 Swift
native tests, Windows desktop contract tests, frontend build, Rust tests and
Clippy pass. Windows runtime and contract formatting verification runs inside
the Windows VM; Windows x64 and ARM64 self-contained publishes pass. ARM64
Windows is build evidence, not live acceptance.

Interrupted intent and partial/corrupt records are simulated deterministically;
this is not a forced power-loss experiment. The measured refused-input paths
include different transports (direct Linux socket versus Windows CLI process),
so their end-to-end timings are not a cross-platform flush benchmark. Test
candidates and scheduled test actions are removed, initial powered-off states
restored, and target-use claims released.

**Open:** No sudden power-loss guarantee or signed updater/uninstall acceptance
is claimed. The first export is bounded to recent records rather than a selected
time range. Standalone headless/protected residents do not automatically acquire
this desktop product journal. Retention is fixed rather than configurable.

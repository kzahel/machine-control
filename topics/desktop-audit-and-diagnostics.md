# Desktop audit and diagnostics

Topic: `desktop-audit-and-diagnostics`

Status: implemented; Mac packaged crash/recovery hardening and source-native validation.

## Current contract

**Current:** The Windows, macOS, and Linux desktop residents write private,
rotated JSON Lines history outside installation directories. Activity reads
retained events rather than the recent memory buffer. The shared format is
[desktop-event-v0](../contracts/desktop-event-v0.schema.json).

Intent is flushed before dispatch, and result before replying. Result events
keep acceptance, delivery, effect, uncertainty, actual route, elapsed time, and
available generation/session metadata separate. Correlation uses a hashed
request identifier; caller PID is OS-observed attribution, not authentication.
Discovery and operator state polling do not produce operation audit rows.
An intent without a retained result has unknown outcome; never replay it.

**Decision:** Audit failure blocks new observations and actions, including
capture and approval. Stop/revocation still execute with best-effort logging.
A failure after dispatch preserves delivery/effect and reports
`audit_result_not_persisted` with unsafe retry advice. Recovery never creates a
grant. Logging health and known malformed/partial-record gaps are visible.

**Current:** Access transitions, resident lifecycle, operation refusals, and
failures are recorded. Structured supervisor/update diagnostics use closed
codes; companion stderr is drained without retaining its raw contents.
Diagnostics normally include failures; a local operator can enable additional
result metadata for 15 minutes. Files are bounded by age and total stream size:
30 days/100 MiB audit, 30 days/50 MiB diagnostics, 1 MiB segments.

Activity has operation/outcome filters, 50-row pages, expandable details, the
earliest retained timestamp, and Open log folder. Diagnostic export previews
up to 500 recent events from each stream, then saves a private local JSON file.
No upload occurs. These operator methods are absent from public agent routes.
Mac adds a separate explicit OS-report preview with a one-use, five-minute
snapshot; Save exports exactly what was reviewed. Ordinary export still omits
OS reports. A private per-instance marker records unclean prior termination,
bounded unfinished operation names, and executable/native-framework UUIDs.
These markers classify an unobserved exit, not a proven crash or effect.
See [operator guidance](../docs/desktop-audit.md) for locations and privacy.

## Evidence and limits

**Current (2026-10-24), private incident review:** a retained `dialog.choose`
intent without a result correlates with a macOS native keyboard-layout
dispatch assertion in the OS crash report. This demonstrates useful operation
breadcrumbs, not an in-app crash stack collector. OS reports remain outside
ordinary diagnostic export; fatal native/Rust/webview failures have no guaranteed
structured terminal event. [Crash collection guidance](../docs/desktop-audit.md#after-an-unexpected-exit)
describes correlation, retention and privacy limits. Raw incident evidence
stays private. The same assertion is subsequently reproduced twice in the
installed signed 0.6.8 app on a dedicated VM; its LaunchAgent brings the
process back afterward. A successful later request therefore does not prove
that the preceding operation survived. [Tactical 135](../docs/tactical/135-browser-file-dialog-crash.md)
records the packaged-app comparison.

**Current:** [Tactical 069](../docs/tactical/069-desktop-audit-and-diagnostics.md)
records the implementation and Windows x64, macOS ARM64, and Linux x64 VM
validation. Unit/contract tests cover retention, restart, interrupted intents,
unsafe links, unavailable storage, privacy, and bounded debug mode.

**Open:** Local history is editable by unrestricted same-user processes or
administrators. Durable writes use native flush/fsync (including macOS full
sync); sudden power loss and every filesystem/hardware combination have not
been tested. History coverage can shrink through retention or manual deletion;
an earliest timestamp and detected partial-record gap do not prove completeness.

Signed installer/update/uninstall acceptance, configurable retention, selected
time-range export, and adoption by standalone headless/protected services are
follow-up work. Windows/Linux OS-report collection and unexpected-exit tracking
remain open. Mac collection, build/symbol identity, and explicit unclean-exit
tracking are implemented in [Tactical 136](../docs/tactical/136-desktop-crash-hardening.md).
No automatic upload or raw payload logging is introduced. Bundle replacement is tested
separately from a signed updater.
This feature adds no provider, privilege, or authentication boundary. Separate
caller authorization follows the [host control](host-control.md) contract.

[Target operation audit](target-operation-audit.md) adds controller-local claim
and common CLI history. It retains claimants across release and joins selected
commands by exact resource without replacing this resident event stream.

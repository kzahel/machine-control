# Desktop audit and diagnostics

Topic: `desktop-audit-and-diagnostics`

Status: implemented for the desktop product; source-native VM validation.

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
30 days/100 MiB audit, 7 days/50 MiB diagnostics, 1 MiB segments.

Activity has operation/outcome filters, 50-row pages, expandable details, the
earliest retained timestamp, and Open log folder. Diagnostic export previews
up to 500 recent events from each stream, then saves a private local JSON file.
No upload occurs. These operator methods are absent from public agent routes.
See [operator guidance](../docs/desktop-audit.md) for locations and privacy.

## Evidence and limits

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
follow-up work. Bundle replacement is tested separately from a signed updater.
This feature adds no provider, privilege, or authentication boundary. Separate
caller authorization follows the [host control](host-control.md) contract.

[Target operation audit](target-operation-audit.md) adds controller-local claim
and common CLI history. It retains claimants across release and joins selected
commands by exact resource without replacing this resident event stream.

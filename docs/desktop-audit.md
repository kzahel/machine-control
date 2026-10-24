# Desktop history and diagnostics

Activity shows retained native resident history, including refusals and access
changes. Select an operation or outcome filter, page through records, and
expand a row to inspect delivery, observed effect, route, and uncertainty.
An intent without a result means the outcome is unknown; it is not a reason to
repeat an action. Filters can hide the matching result, and retention can
remove it. Refresh updates the current page.

The settings window can be closed while the resident keeps recording. History
survives app restart and replacement because it lives outside the app bundle:

| Platform | Per-user root |
| --- | --- |
| Windows | `%LOCALAPPDATA%\MachineControl\logs` |
| macOS | `~/Library/Logs/MachineControl` |
| Linux | `$XDG_STATE_HOME/machine-control/logs`, or `~/.local/state/machine-control/logs` |

Each root contains `audit`, `diagnostics`, and operator-created `exports`.
Directories and files restrict access to their owning user; Windows uses a
current-user ACL. Audit retains at most 30 days and 100 MiB; diagnostics retains
at most 30 days and 50 MiB. Segments rotate at about 1 MiB. Retention prunes the
oldest files. These locations survive package replacement; this slice does not
add an uninstall purge or a Clear history action. Manual deletion removes
history and cannot be inferred as a complete gap report.

If audit storage becomes unavailable, the app refuses new control and shows a
logging-health warning. Stop access remains available. Restore storage, then
refresh/check health and explicitly enable access again if needed. If a result
could not be saved after dispatch, the action may already have happened: use
independent observation before considering another attempt.

Open log folder opens the fixed native location. Preview diagnostic export
shows the latest 500 events per stream and health information. Save diagnostics
writes `exports/diagnostics.json`, replacing the previous export; Cancel leaves
it unsaved. Sharing is an explicit operator action outside the app. Nothing is
uploaded automatically. Enable debug diagnostics adds operation result
metadata for 15 minutes; it does not enable payload logging.

Logs omit typed text, clipboard data, screenshots, UI trees, script bodies,
full URLs, credentials, bearer grants, and raw requests/responses. They retain
operation names, timing, routes, outcomes, hashed correlation IDs, and available
OS caller/session/generation metadata. Even these details can reveal usage
patterns: inspect the preview before sharing. Raw companion stderr is discarded
and replaced with a generic failure event, so exports are not full crash dumps.

This is local audit history, editable by an unrestricted same-user process or
administrator. It does not provide an independent or tamper-resistant record.

## After an unexpected exit

The retained history identifies operations around a failure; it is not a
cross-platform crash-dump collector. A fatal native assertion, signal, Rust
panic, or webview failure is not guaranteed to produce a diagnostic event or
stack trace. An unfinished operation intent remains useful, but does not by
itself prove a crash or whether an action took effect. Ordinary export excludes
OS crash reports, raw companion stderr, and debug symbols.

On macOS, reaching the serving state writes a private per-instance marker.
Clean termination removes only that runtime's marker. The next launch records
`resident.previous_exit_unclean` if the preceding marker remains, including
validated executable/framework UUIDs, source revision, and up to ten unfinished
operation names from the last 500 audit records. Activity shows an unclean-exit
notice. Forced termination, an OS shutdown, and a crash can all leave a marker;
this is evidence of an unobserved exit, not a crash classification. Tracking
failure is visible in logging health. It does not disable Stop or ordinary
audit. Windows/Linux unclean-exit classification remains separate work.

On macOS, also inspect `~/Library/Logs/DiagnosticReports` for a matching
`macui-*.ips` or Machine Control report. Correlate its process, timestamp and
faulting-thread stack with the audit intent/result pair and runtime generation.
The native resident runs inside the desktop process in the packaged Mac app,
so a native trap can terminate the whole app. A source-native appliance's
LaunchAgent may restart its resident; a changed PID/generation still counts as
a failure during a test, even when the next request succeeds.

After a failure, preserve the matching OS report and the audit/diagnostic
segments privately before retention removes context. Record the app version,
OS/browser versions, approximate time and operation, and whether the app
exited, restarted or remained running with one failed request. Diagnostics
retain thirty days subject to their byte limits. Debug mode adds result
metadata, not crash stacks.

On macOS, **Preview with crash reports** explicitly reads the current user's
fixed DiagnosticReports location. It includes at most three matching
`macui-*.ips` reports from the last thirty days, each no larger than 2 MiB.
Unrelated bundle identities, links and oversized/invalid reports are skipped.
The preview explains that raw reports can contain private paths and system
details. Save writes the exact reviewed snapshot, even if the source report
changes afterward. The one-use preview expires after five minutes; Cancel
discards it. Nothing is uploaded. These methods are private operator commands,
absent from the agent socket. Standard previews/exports never scan OS reports.

Signed CI builds retain separate executable and native-framework dSYM archives
for ninety days, keyed by source/version and Mach-O UUID. Collection rejects
empty debug information as well as mismatched UUIDs; final signing is followed
by another verification. Symbols are CI artifacts, not public installer assets.

The [browser/file-dialog smoke runner](../tests/macos/browser-file-dialogs.py)
checks real download/upload effects, resident PID/generation continuity and
new OS crash reports on a dedicated Mac VM. Its bounded coverage does not
establish crash-free behavior on other machines or platforms. The controller
[packaged acceptance runner](../tests/macos/packaged-acceptance.py) installs the
actual app on a claimed VM, restores app/policy/operator state and power, and
supports a bounded seeded soak plus native-host, Stop and forced-exit faults.
Its operation timeline excludes request fields and response payloads. Keep all
raw evidence outside the public checkout.

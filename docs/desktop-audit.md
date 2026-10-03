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
at most 7 days and 50 MiB. Segments rotate at about 1 MiB. Retention prunes the
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

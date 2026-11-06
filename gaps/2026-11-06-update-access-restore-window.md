# Update access-restore window is tight for slow installers

Topic: `native-distribution`

Status: **Open — observed once on Windows ARM64; not repaired.**

## Observations

Operator-initiated updates record live surface choices in a one-shot
`update-access-resume.json`. The updated client accepts that record for only
ten minutes (`MAX_AGE_SECONDS` in `desktop/src-tauri/src/update_resume.rs`).
In one Windows acceptance run on 2026-11-06, the NSIS installer stopped on a
write-error dialog until it was retried. Access was restored about 10 seconds
before the record expired. A longer stall, or a relaunch that needs a person,
would leave access Off. The only signal would be an
`update.access.restore_skipped` diagnostic, and Settings would show no
message.

That dialog was caused by the harness polling the installed executable's
version every 50 ms; the harness has been fixed. But real installers can
also stall on antivirus scans, file locks or slow disks.

## Proposed repairs

- Raise the window to about 30 minutes. The record is already bound to the
  exact installed version and is consumed on first launch.
- When a record is skipped because it expired, show it in Settings (for
  example "Access was not turned back on after the update" with Go to
  Access), not only in diagnostics.
- Keep the same-user forgery limitation recorded in the
  [native-distribution topic](../topics/native-distribution.md) in mind; a
  longer window slightly widens it.

# Inspect target claim and command history

Use the controller's common CLI to inspect retained operational history:

```bash
bin/machine-control audit history --limit 100
bin/machine-control --target windows audit history --since 2026-01-01T00:00:00Z
bin/machine-control audit history --claimant-id example-session
bin/machine-control audit history --claim-id c-000000000000000000000000
bin/machine-control audit history --before 123 --limit 100
```

Output follows the [history schema](../contracts/target-operation-audit-v0.schema.json);
`--json` is accepted explicitly. Limits are 1–500 events. Pages
are chronological within the newest matching page; pass `nextBeforeId` as
`--before` to read older rows. Queries do not load the current registry, claim
a machine, start a VM or dispatch provider commands. A retired target's alias
can therefore still select its retained history.

`claim.acquired`, `claim.renewed`, `claim.released` and `claim.expired` retain
self-asserted claimant metadata, reason, use class and generation. Commands
correlate by claim ID; queries attach retained claim-holder attribution and an
opaque `resourceKey`. Two aliases of one exact target share a key. A new VM
behind the same alias has a different key. Claim-holder attribution does not
authenticate the command's controller process, whose observed PID is separate.

`command.intent` precedes dispatch and `command.result` records the exit status,
elapsed time and any structured acceptance/delivery/effect/uncertainty. A
successful process exit alone does not prove a guest effect. An intent with no
result has unknown outcome and must not be replayed. `run.*` records include the
scoped task's claim/workspace cleanup result.

Only known CLI grammar and allowlisted program categories are retained: for example, `testbed exec` or `target
shutdown`. Arguments, shell code, arbitrary executable names, typed text, stdin,
environment, payloads, screenshots and raw output are omitted. Never put a
credential in a claimant ID, label, reason or metadata. Normal task output still
has its own disclosure responsibilities and is not copied into this journal.

## Storage, failures and coverage

The journal lives outside repositories and application bundles:

- macOS/Linux: `${XDG_STATE_HOME:-~/.local/state}/machine-control/audit/`.
- Windows: `%LOCALAPPDATA%/MachineControl/audit/`.
- Tests or explicit private deployments may set `MACHINE_CONTROL_AUDIT_DIR` to
  an absolute private directory; all participating source adapters must use the
  same controller selection.

SQLite transactions use full synchronous writes and serialize concurrent
writers. POSIX directories are mode `0700`, files `0600`; Windows uses the
controller user's local application-data ACL inheritance. Unsafe storage links,
hard-linked files and public POSIX permissions are refused. Retention is 30 days
and at most 50,000 events of at most 16 KiB each. No upload occurs.

Unavailable intent storage refuses new common CLI work before dispatch.
Claim/workspace release, target shutdown and grant revocation remain available
with best-effort logging. If result persistence fails after dispatch, the CLI
returns nonzero and warns of a coverage gap; that is not evidence that the
operation had no effect. Shared claim-state writes preserve arbitration and
cleanup even if their best-effort history write fails.

Always inspect `coverage.startedAt`, `earliestRetainedAt` and limitations. An
absent journal returns `available: false`; it does not mean nobody used the
target. Coverage is never declared complete. Older installed clients, direct
provider/shell bypasses, other controllers, deletion and retention can leave
gaps. The journal cannot retrospectively reconstruct them or identify an
authenticated agent from a self-asserted label. Keep resident
[desktop history](desktop-audit.md) and provider diagnostics as separate
evidence rather than assuming this journal replaces them.

# Record a fresh appliance bring-up

Every fresh VM/appliance bring-up needs a dated private provisioning journal,
including successful runs with no friction. It pairs automatic command and
phase observations with agent-authored notes. Recording an improvement does
not authorize implementing it: fix blockers within the task's existing scope,
and record other ideas for later prioritization.

## Begin before preflight and carry the run

```bash
provision_run="$(bin/machine-control provision begin --platform linux \
  --profile development | jq -r '.runId')"
mc_provision() {
  bin/machine-control --provision-run "$provision_run" "$@"
}
mc_provision --target linux testbed -- factory-stages preflight --json ...
```

Use `windows`, `linux`, or `macos`; profiles are `development` or `runtime`.
`begin` is offline and requires neither a registry nor an existing VM. Its
response supplies the run ID and actual journal path. The dated ID names a
controller-local SQLite log file. Preserve that ID when resuming an unfinished
bring-up; a replacement appliance or new provisioning attempt gets a new run.

Use this wrapper for storage/media checks available through the common CLI,
precreation, pinning, doctor, claims, guest setup, credentials, phase inspection,
detachment, cold boot, conformance and cleanup. Existing claim requirements
remain in force. Run association grants no target authority. A target command
passes `MACHINE_CONTROL_PROVISION_RUN` to its children, including scoped task
programs; their nested common CLI calls join the same journal. Alternatively,
set that environment variable only for the provisioning task's process tree.
An explicit `--provision-run` overrides the inherited selection. Do not leave
the variable active for unrelated work.

Under the exact-target claim, inspect after meaningful transitions:

```bash
mc_provision --target linux --claim "$claim_id" testbed -- factory-stages --json
# Windows uses factory-stages; macOS uses bootstrap-stages.
```

The automatic journal records command intent, timestamps, elapsed milliseconds,
exit status, safe structured result fields and claim ID. Resolved target calls
also record the normal audit correlation ID: use
[target audit history](target-operation-audit.md) to correlate the claim's exact
resource and self-asserted holder. Alias equality alone does not prove resource
identity. A command may span multiple phases; its duration is not an inferred
duration for each phase.

JSON `factory-stages`/`bootstrap-stages` output is streamed normally and reduced
to an allowlisted inspector schema, stage names and states. Unknown stages are
counted as omitted; malformed or oversized output reports an unavailable
observation. Raw output, stderr, arguments, stdin, environment, inspector
evidence strings and next-command operands are not copied into this journal.
This intentionally avoids storing credentials or private payloads incidentally.

## Add notes while the details are fresh

```bash
bin/machine-control provision note "$provision_run" --kind friction <<'NOTE'
Installation remained in waiting longer than expected. Read-only inspection
showed updates still progressing; no recovery mutation was needed.
NOTE
bin/machine-control provision note "$provision_run" --kind follow-up <<'NOTE'
Consider showing installation progress and elapsed waiting time.
NOTE
```

Notes are explicitly `source: agent`, with UTC timestamps, and accept at most
4096 UTF-8 bytes through stdin. Kinds are `friction`, `workaround`, `fix`,
`follow-up`, and `summary`. Record the symptom, attempted step, observed effect,
waiting/manual intervention, workaround, remaining uncertainty, and references
to private evidence. A fix note should include its commit reference when one
exists. Distinguish an observed failure from a suspected explanation. If no
friction occurred, say so in the summary rather than leaving that ambiguous.
Never include secret bytes, answer-file contents, signed download URLs, private
keys or grants in notes. Passwords remain exclusively in the canonical secret
store; the journal never replaces credential handoff or verification.

Native media preparation, direct platform scripts, interactive recovery, and
guest-internal commands do not automatically emit common CLI events. Record
these steps and their outcomes in notes, with references to suitable private
receipts/logs. Existing evidence includes Windows's guest first-logon report
and exact-candidate attestation, Linux cloud-init status/attestation, and
platform bootstrap/post-update reports. Some temporary package-install logs
are deleted by existing scripts; this journal does not promise their retention.
Do not blindly tee secret-bearing scripts or shell tracing into a log. Keep any
needed diagnostic capture private, minimal and reviewed separately.

## Finish and review

After acceptance and task-owned lifecycle/claim cleanup, add a summary of
readiness, credential verification, retained/deleted resources, fixes and open
friction, then finish:

```bash
bin/machine-control provision finish "$provision_run" --outcome ready
bin/machine-control provision show "$provision_run" --limit 100
bin/machine-control provision show "$provision_run" --markdown
```

Other outcomes are `blocked`, `failed`, and `abandoned`. Outcomes are agent
reports, not automated acceptance certificates; a successful exit or `ready`
label does not prove a guest effect. A command intent without a result has
unknown outcome. `ready` refuses with unpaired intents; other outcomes can close
an interrupted run without inventing results. Do not replay an uncertain
mutation. A closed run refuses new work; follow-up notes remain available.

JSON and Markdown show the newest page in chronological order; use
`nextBeforeId` with `--before` for older pages. Limits are 1–500 entries. Queries
are offline and do not load the current registry or touch a VM. Markdown can
be redirected to a private dated file for review; it is not suitable for public
Git without redaction and minimization.

## Storage and coverage

- macOS/Linux: `${XDG_STATE_HOME:-~/.local/state}/machine-control/provisioning/`.
- Windows: `%LOCALAPPDATA%/MachineControl/provisioning/`.
- `MACHINE_CONTROL_PROVISION_DIR` selects an absolute private override, mainly
  for tests or an explicit deployment.

Each run is a dated `.sqlite3` file with transactional full-synchronous writes,
at most 10,000 events and a 16 KiB per-event bound. There is no automatic
retention deletion; the operator owns archiving/removal. POSIX directories are
`0700` and files `0600`; Windows inherits the controller user's application-data
ACLs. Storage symlinks, hard-linked files and public POSIX permissions refuse.
No upload occurs. Notes and metadata remain editable by the same OS user.

Intent-storage failure prevents new attached work before dispatch. Claim and
workspace release, target shutdown and grant revocation remain available with
a coverage-gap warning. Result-storage failure returns nonzero after a target
command and warns against replay; its effect may already have happened. Killed
processes can leave unpaired intents. Coverage is never complete: unattached
calls, other controllers, direct scripts, guest logs, deletion or storage
failures may be missing. Keep the normal command/claim audit and platform
evidence alongside the run rather than treating any one log as exhaustive.

Portable findings can later update the owning topic and tactical. A dated
private journal records what happened; the public topic records current truth.

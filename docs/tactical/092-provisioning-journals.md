# Dated provisioning evidence and friction notes

Topic: [operational-workflow-automation](../../topics/operational-workflow-automation.md).

Status: complete; source implementation and portable fixture validation.

## Objective and completion conditions

The operator requested automatic logs for fresh bring-up commands/phases,
alongside dated agent notes, so repeated friction can drive later improvements
without requiring fixes during provisioning. Provide durable private per-run
logs, automatic bounded observations through the common CLI, explicitly agent
notes and outcomes, usable offline inspection, updated agent instructions,
and meaningful privacy, failure and phase tests.

## Boundaries

No VM mutation, reprovisioning, credential changes or outer UI testing is
needed. The journal does not replace claims, platform logs, credential handoff
or independent effect/acceptance proof. It never automatically captures raw
arguments, output, stderr, environment, stdin or inspector evidence payloads.
Agent-authored notes must not contain secrets. Recording deferred improvements
does not authorize implementing them. Public source remains portable; actual
runs and deployment identity stay private.

## Ordered work

### 1 — identify existing evidence and gaps

Inspect controller audit, platform stage reports, first-logon/cloud-init
attestations and bootstrap reports. Preserve their distinct coverage rather
than claiming existing logs already describe a complete bring-up.

### 2 — record a dated provisioning run

Add offline begin/note/show/finish, durable bounded private storage, automatic
common-command metadata and bounded allowlisted stage projections. Carry run
selection through child tasks, preserve normal output and secret transports,
and keep cleanup available during persistence failures.

### 3 — make journaling the agent workflow

Update root/platform/installed-client instructions and the retained appliance
recipe. Explain safe notes, deferred fixes, explicit direct-script coverage,
pagination, storage ownership and honest outcome reporting.

### 4 — validate without touching accepted targets

Exercise complete fixture bring-up sequences, precreation, claims, refusals,
phase output, malformed/oversized output, failure, storage permissions/links,
concurrent writers, interrupted runs and offline review. Verify neither raw
payloads nor synthetic secret markers enter automatic storage. Run portable
repository checks and inspect public diffs before committing.

## Final result

The common CLI now provides offline `provision begin|note|show|finish`, dated
private per-run SQLite logs, bounded chronological pagination and Markdown
review. `--provision-run` and task-local inheritance group automatic command
intent/result metadata and allowlisted Windows/Linux/macOS stage states.
Normal output remains visible; raw output, arguments, stdin, stderr and
inspector evidence/command operands are omitted. Claim correlation uses the
existing audit, whose retention and coverage remain distinct.

Agent notes have separate provenance and bounded stdin input. Outcomes are
explicitly agent-reported. Unknown command outcomes remain visible; ready
refuses unpaired intents. Persistence failures refuse new work before dispatch,
return failure after an uncertain dispatched result, and preserve release/
shutdown/revocation with a coverage warning. The Mac precreation inspector is
now reachable through the common CLI without a nonexistent target claim,
matching its existing native read-only boundary; candidate inspection remains
claimed.

Root, platform and installed-client instructions now require this journal for
fresh bring-up, including no-friction summaries and direct-script evidence
notes. The retained recipe links the workflow. The packaged CLI includes the
implementation, and repository checks isolate any inherited provisioning run.

Twenty focused tests pass, covering offline notes/review, dated storage,
pagination, closed/interrupted runs, private permissions/link refusal,
concurrent writes, precreation and claim enforcement, inherited nested CLI
tracking, malformed/oversized phase output, result-persistence failure and
synthetic secret omission. The stage vocabulary is checked against all three
owned inspectors. Full portable checks passed; subsequent small changes were
covered by final focused tests and whitespace verification. No accepted VM
was reprovisioned or changed for this logging slice. Direct scripts, guest logs,
other controllers and unattached commands remain explicit coverage limits.

# Scoped Target Tasks

Topics: [target-use-claims](../../topics/target-use-claims.md),
[operational-workflow-automation](../../topics/operational-workflow-automation.md)

Status: complete for the common runner, fixture failure coverage, and live
Mac claim acceptance. Native Windows and live workspace acceptance remain
unverified in this execution.

## Objective and completion conditions

Replace repeated claim parsing, renewal, and trap boilerplate with one bounded
common-client command. The caller supplies truthful attribution and a local
task; the runner owns doctor, acquisition, renewal, inherited selection, and
finally release. Success, task failure, interruption, and renewal failure must
leave verified release or an explicit unresolved result. Workspace cleanup
must use the returned handle and claim.

## Boundaries

Compose authoritative adapter contracts without changing provider ownership,
exact-identity enforcement, or outer-input guards. Do not start an agent, infer
shutdown authority, log private configuration, or turn this into a long-lived
session service. Plain claims do not own target power transitions. Existing
manual commands remain available for independently coordinated tasks.

## Ordered work and validation

1. **Scope a local task.** Add `run`, pinned inherited selection, bounded
   management calls, and minimized acquired/final audit records.
2. **Own the task's lifetime.** Renew before expiry, handle signals, terminate
   descendant tasks before release, and report failed cleanup without guessing
   or reacquiring. Use POSIX groups and a gated Windows Job Object.
3. **Compose workspace cleanup.** Retain both receipt selectors, renew against
   the workspace, and release that handle under its claim.
4. **Exercise failures independently.** Stateful adapter fixtures record held
   resources and call order; delayed child effects reveal escaped cleanup.
   Include task failure, signal, renewal refusal/timeout/mismatch, malformed
   receipts, preflight refusal, and unresolved release.
5. **Verify the real claim route.** Use the prepared suspended Mac target for a
   bounded read-only scope with renewal; independently inspect final claim and
   power state. No host focus or VM start is required.
6. **Publish the simpler workflow.** Update the common guide, schemas, topics,
   and tactical index with actual evidence and remaining platform limits.

## Result

Implemented [`run`](../../client/scoped_run.py) and bounded
[process management](../../client/scoped_process.py), with pinned private
selection, inherited common-client claim/workspace defaults, early renewal,
receipt-bound cleanup, and a minimized
[audit schema](../../contracts/run-result-v0.schema.json). Task arguments and
management diagnostics are not copied into the audit. Plain scopes leave
target power transitions to the task. Existing manual commands and all
ordinary/disruptive guards remain available.

The stateful client suite independently checks held-resource files and delayed
process effects across successful and failing tasks, interrupted acquisition,
interrupted descendants, renewal refusal/timeout/identity mismatch, unknown or
partially malformed receipts, and failed workspace release. It also checks
registry pinning, inherited selection, successful provider-owned background
services, and termination of timed-out management calls. Successful management
does not kill provider-owned services; task descendants are stopped before
claim release.

The expanded tests reproduced a Darwin process-group edge case: a group
containing only a just-exited zombie can return `EPERM` during a liveness
probe. Bounded reap/recheck handling resolves that transient state; persistent
denial still reports failed cleanup and retains unresolved authority.

The portable repository suite passed on macOS, with the final scoped tests
rerun after process-cleanup refinements. The public
[`live-scoped-run.py`](../../tests/client/live-scoped-run.py) acceptance also
passed against the prepared suspended Mac target: two claimed read-only status
operations crossed a successful renewal, the runner reported release, an
independent claim-status check reported availability, and final doctor still
reported suspended. No guest start, host focus, credential read, or outer
input was involved. Private credentials remained recorded and ready.

The Windows Job Object path has source-reviewed implementation and portable
test coverage scheduled by the existing Windows CI matrix; this Mac execution
does not establish native Windows acceptance. Workspace composition passed
stateful adapter fixtures, not a fresh live allocation. No new platform
factory or inventory-preflight workstream was started.

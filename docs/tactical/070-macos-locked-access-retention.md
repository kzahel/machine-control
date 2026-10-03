# Retain approved access for unattended Mac tasks

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: complete within bounded physical live-tested scope. The full scripted
takeover cell remains unpassed because hardware input raced its startup check.

## Objective

Keep existing ordinary approval usable for subsequent unattended tasks when
the person has enabled and prepared locked use. The physical completion trial
in [Tactical 067](067-macos-physical-unlock-trigger.md) passed automatic covered
control and relock, but ordinary approval was then revoked by the desktop-lock
transition. Idle locking without an active task had the same policy gap.

## Completion conditions

- Preserve the same approval across an idle lock and clean task completion.
- Start another bounded task on the already locked console without new approval.
- Preserve approval expiry, Stop, failure and physical-takeover revocation.
- Refuse unknown, replaced or different-user console identity.
- Prove physical hardware takeover still relocks and requires manual recovery.
- Keep exact fixture process identity tied to its independent file oracle.

## Boundaries

Existing awake console, open lid, prepared workstation profile. The preference
creates no grant, no persistent privileged unlock authority, and no password
store. Each unlock still needs ordinary approval and a separate finite owner
connection. Native operator controls remain separate from agent commands.
No new hypervisor route, sleep prevention, closed-lid or preboot support.

## Ordered work

### 1 — bind approval to the current console

Bind each newly issued approval synchronously to the unlocked current user's
console identity. A timer or request checks that same grant and console before
dispatch. A grant that could not be bound at issuance cannot be adopted later.
Unknown or changed identity revokes approval, including a change that does not
pass through the locked state.

### 2 — retain access through expected locks

Prepared, enabled and unpaused locked use may retain approval while idle or
relocking after completion or control-lease expiry. Interruptions and missing
preparation refuse retention. Approval expiry remains independent of the
shorter task lease; Stop and failures continue to revoke it.

### 3 — prove successive unattended tasks and takeover

The live runner selects exactly one fixture, targets its PID and requires its
file oracle and snapshot to report that same PID. It can start on an already
locked console and require unchanged approval after clean relock. Run an idle
lock, a completed task, a second task starting locked, then hardware takeover.
Use independent IOKit lock readback and keep captures private.

## Validation and current result

**Current:** all 91 Swift tests pass in the installed wake/maintenance revision.
The retention tests cover normal retention,
interruption, missing preparation/pause, changed or unknown console identity,
and approval issued without an unlocked console. The socket suites use explicit
synthetic console observations, so host lock state cannot authorize their grants.
Native ARM64/Intel framework builds passed and the staged Developer ID candidate
passed deep strict signature verification. Python compilation, runner help and
whitespace checks passed. After manual recovery, the signed candidate replaced
the running test bundle while the console was unlocked and no control session
or covers were active. The existing helper initially rejected the changed caller
generation and required native Repair, which also cleared the checkbox. Those
maintenance problems are addressed and physically checked in [Tactical
072](072-macos-helper-update-maintenance.md). The latest signed build is ready;
the person re-enabled ordinary Access and the checkbox. The physical idle-lock
cell then retained the same approval with no active task. The next task refused
because the display had become inactive; that failure revoked Access, and the
Mac remained locked with no covers or owner. [Tactical
073](073-macos-locked-display-wake.md) owns the bounded startup wake fix.

**Current:** after that signed update and native Access re-enabling, a physical
idle lock retained the original approval. Completion reached independent native
AX/pointer/keyboard effects, filtered capture and relock; a final runner check
initially used the wrong grant field name. Direct status verified the same
approval survived with zero covers and no pause. After correcting the check,
two further tasks started already locked and passed unchanged-grant assertions,
exact single-fixture PID/oracle attribution and independent OS relock. The first
of those began with an inactive display and required no external wake command.
No manual unlock or new approval occurred between the completion cells.

**Current:** the 90-second bounded task-expiry cell also passed covered native
effects and independent OS relock. Its exact ending reason was
`duration_expired`, the original approval survived, and there were no remaining
covers or manual-unlock pause. It started already locked with an inactive display
and used no external wake command.

**Current:** a hardware-takeover cell reached covered native effects and capture,
then waited for physical input. No hardware event was detected before its wait
expired. That trial is inconclusive for takeover, rather than a passed revocation
cell. Cleanup completed the exact session, independently confirmed OS lock,
removed all covers, stopped the owned fixture and released the claim. Ordinary
approval remained active and no manual-unlock pause was present. Whether the
person actually attempted movement while covered is still unknown.

**Current:** a subsequent operator-confirmed takeover trial reached the active
phase, then physical input raced the runner's next stable-unlocked assertion.
The script failed that startup assertion rather than reaching its later takeover
prompt. Resident IOKit-backed status nevertheless recorded `physical_presence`,
OS lock, no remaining session/covers, revoked ordinary approval and a persisted
manual-unlock pause. The person reported the takeover worked and the next native
probe observed the console already unlocked. Fresh status confirmed recovery had
cleared the pause while Access remained revoked; a new one-second control request
refused with `approval_required`. The fixture was stopped and both the test and
follow-up claims were released. The helper remained ready and the preference on.

This is bounded physical `live-tested` cancellation/recovery evidence, not a
passed full scripted takeover cell: the independent probe ran after recovery,
and that trial did not reach the additional covered-fixture/capture checks.
Earlier completed/expiry cells own those independently observed effects and
relock checks. The visible cover's invitation to take over permits input before
a test's own prompt; future takeover qualification should handle early input
without requiring a stable covered interval or treating a stale prior ending
reason as evidence for a new session.

**Open:** complete the scripted takeover cell with independent lock readback
before manual recovery, additional OS revisions, multiple displays, Intel
execution and distribution. Those broader qualifications are not first-version
acceptance claims.

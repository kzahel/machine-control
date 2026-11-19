# Tactical 165 — Locked-use agent experience verification

Status: in progress — reproduction before repair.

Topics: [macOS locked use](../../topics/macos-locked-use.md),
[access admission and pause](../../topics/access-admission-and-pause.md),
[target-use claims](../../topics/target-use-claims.md) and
[browser control](../../topics/browser-control.md).

## Objective

Agents on a locked Mac workstation often tell the operator to unlock it,
even though Machine Control can already use the browser while locked and
unlock the console behind covers for a Desktop task. The operator also
lacks a clear model of how consent, claims, control owners and locked use
relate, and when each ends.

Reproduce each suspected cause in a disposable Tart workspace before changing
code or documentation. Repair only what reproduces. Then add a simple bounded
"keep unlocked for a while" command over the existing prepared-console owner.
Past descriptions of this behavior have drifted. Every claim this tactical
makes about behavior must cite an observed result or the exact source that
decides it.

## Motivating observations

Sanitized from recent physical-workstation agent sessions (Desktop and
Browser Automatic, consent until turned off, locked use and browser while
locked enabled):

- A task reading a web mailbox while the console was locked: `browser tabs`
  succeeded, `browser snapshot` refused with `browser_detached`. Doctor showed
  `browserWhileLocked: {enabled: true, active: false,
  requiresUnlockedApproval: true}`. The agent told the operator to unlock or
  approve. Six days earlier another agent used the browser while locked with
  identical flags. A separate unlocked session also produced
  `browser_detached`.
- A build task blocked by the screen lock asked the operator to unlock three
  times before trying Machine Control. When asked, it said an indefinite unlock
  was impossible. It then held a `--prepared-console` owner that worked, until
  the harness's two-hour background-command limit killed the owner process
  and the console relocked.
- In both sessions the first request on a new Desktop owner was a status
  query. It was refused (`operation_not_permitted_by_control_channel` or
  `unsupported_operation`) and the refusal ended the owner. Both agents built
  ad hoc fifo/`nohup` holders to keep a prepared-console owner alive.
- The operator sees a short start notice for many individual agent CLI calls.

## Suspected problems to verify

Each item is **Open** until reproduced or refuted below.

1. **Misleading browser-while-locked status.** `requiresUnlockedApproval` is a
   constant `true` in the Mac resident status. `active` is true only when the
   browser route is ready and the Desktop route is not. With a prepared
   console the Desktop route is ready while locked, so `active` stays false
   even though browser work is admitted.
2. **`browser_detached` is not a lock signal.** The extension reports it when
   Chrome's debugger detaches from a tab. Determine what detached in the
   locked case and whether the lock contributes.
3. **Status as a first owner request.** Determine which first-request
   operations a Desktop owner refuses and whether a refusal ends the owner.
4. **Restart clears access.** Shared admission never restores live authority
   after a restart, and enabling a surface requires an unlocked operator
   console. Confirm the refusal an agent sees on a locked console after a
   restart, and whether doctor says what to do.
5. **Per-call notices.** Determine whether each one-shot `control call`
   (or other one-shot CLI command) produces a separate start notice, and
   whether one `control stream` task produces exactly one.
6. **Covered takeover semantics.** Confirm that pointer movement during
   covered control does not end it; key-down, button-down or scroll ends it,
   relocks and pauses Desktop (`covered_takeover`); an operator password unlock
   becomes a `local_use_episode` pause; and relock plus 30 seconds of quiet
   allows a fresh owner. Confirm that Browser stays independent.
7. **Long holds.** Confirm renewal past 900 seconds under one owner, relock
   when the owner process is killed, and the four-hour claim lifetime.

## Boundaries

- Use a disposable isolated Tart workspace with the published app. Do not
  modify the retained base or the physical workstation's policy.
- A VM cannot reproduce Touch ID, lid, multiple displays or the
  classification of a physical keyboard on real hardware. Record those as
  physical-only cells for a later operator-supervised run.
- No new authority: the hold command composes the existing claim and
  prepared-console owner. It does not leave a visibly unlocked workstation and
  does not bypass takeover, Stop or watchdogs.
- Keep private identifiers, credentials and raw logs out of this record.

## Ordered work

### 1 — reproduce in a disposable workspace

Acquire an isolated Tart workspace, install the published app, enable locked
use and browser while locked through the native operator UI, and run each
cell above. Record the observed result and the cause of each finding.

### 2 — correct status and agent guidance

For reproduced issues only: correct status fields and refusal remediation,
accept or clearly document status as a first owner request, and correct the
installed `agent instructions` text. Find the Windows and Linux counterparts
and change them in the same slice, or state why not.

### 3 — bounded keep-unlocked command

Add a CLI command that acquires or uses a claim and holds one prepared-console
Desktop owner for a requested duration, renewing both, and relocks on exit,
signal, takeover or expiry. Report the actual ending reason. Validate renewal
past 900 seconds, process kill, takeover and claim expiry in Tart.

### 4 — topic and documentation update

Update the owning topics with verified current truth only.

## Validation

Per cell: the command, the observed result, and the source that decides it.
Run unit and contract tests for any changed code.

## Results

### Physical workstation, unlocked, published 0.7.2 (2026-11-19)

Operator-approved check against a throwaway local page in one background tab
of a real Chrome profile; Browser Automatic with a 5-second notice. The tab
was closed and the claim released afterwards.

- **Current, item 5 confirmed with a refinement.** Each one-shot CLI command
  that needs ownership opens its own `ControlSession`
  (`client/control_session.py` `complete_session_handoff`). `browser navigate`
  and `browser click` each took about 7 seconds, which matches a separate
  5-second notice per call. `browser snapshot` took 2 seconds: a background-only
  read does not wait for a notice. One `control stream` paid the notice once
  (6.5 seconds for its first request), and its following click took 0.2 seconds.
- **Current, new finding.** A reference from a one-shot `browser snapshot`
  is refused as `stale_reference` (`delivery: refused`, no click effect) when a
  separate `browser click` uses it. The reference embeds the owner session, and
  every one-shot command has a new session. Inside one `control stream`, the
  same snapshot-then-click sequence had an independently observed effect. This
  explains the repeated `stale_reference` reports. The one-shot
  `browser snapshot` / `browser click` pair that the help text suggests cannot
  work.
- **Current, item 3 confirmed.** In a Browser `control stream`, a `status`
  request returned `operation_not_permitted_by_control_channel` as a client
  error. The stream then exited with code 2 and did not answer the next request.
  A refusal that was never dispatched still ends the owner.

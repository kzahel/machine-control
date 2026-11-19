# Tactical 165 — Locked-use agent experience verification

Status: VM-qualified repairs complete; physical takeover cells and Windows
compilation remain open.

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

### Disposable Tart workspace, current source (2026-11-19)

The test was an isolated discard-on-release workspace derived from a local
Tahoe base: macOS 26.6.2 guest, SIP disabled (Cirrus posture), one display.
The full desktop app was built from source at this tactical's start, after
`desktop-v0.7.2`. Only Python client files differ, so the resident behaves as
0.7.2. The app was ad-hoc signed with the pinned development requirement and
used the workstation policy. Through the real Settings UI, the setup chose
Desktop and Browser Automatic until turned off, plus browser while locked and
prepared tasks behind covers. The native helper was approved in System
Settings with the stored VM credential through the one-shot transport.
Chrome for Testing ran an isolated profile. The agent used the installed CLI
inside the guest under its own claim. Locking used the checked-in
`session-lock` tool, and lock state was read independently from
`IOConsoleLocked`.

- **Current, item 1 confirmed.** On a locked console, `target doctor` exits 1
  with `ready: false` and `fail` for desktop, semantic and input.
  `browserWhileLocked` reports `active: false, requiresUnlockedApproval:
  true`, and `deployment.browserOnlyWhileLocked` is false. Yet `browser tabs`,
  `browser navigate --new-tab` and `browser snapshot`, each opening a new owner
  after the lock, all succeeded in about 1.7 seconds. There was no unlock, no
  approval and no notice wait (notices are not shown while locked). `active`
  stays false because the prepared Desktop route is also ready
  (`Server.swift` `browserOnlyWhileLocked`), and `requiresUnlockedApproval` is a
  constant. Both fields told the agent the opposite of what works.
- **Current, new finding.** A plain one-shot Desktop request while locked,
  without `--prepared-console`, also works. A flagless `control call`
  `applications` succeeded in 29 seconds: macOS still admits a flagless owner
  on a locked console as covered control, unlocks it behind covers and relocks
  it (ending reason `cancelled`). Prepared-console use is the documented path,
  but the flagless one-shot path is not refused.
- **Current, item 3 confirmed while locked.** A prepared-console stream whose
  first request was `status` answered after 15.7 seconds (covered startup) with
  `operation_not_permitted_by_control_channel`. It then exited with code 2 and
  relocked.
- **Current, prepared hold.** A prepared-console stream whose first request was
  `capabilities` was accepted. While it was held, `IOConsoleLocked` was false,
  so the console is genuinely unlocked behind covers and a screen-lock check
  such as the `xcodebuild` wrapper's would pass. Resident `desktopState` was
  `unlocked`, `target doctor` reported `ready: true`, and one-shot browser calls
  from another process still worked. Closing stdin relocked the console in
  2.6 seconds, as independently observed.
- **Current, long hold (item 7).** One prepared owner stayed active for 17
  minutes under the same control session. It renewed about every three
  minutes (remaining time went from about 100 seconds back to about 290), and
  read requests at minutes 4, 8, 12 and 16 were accepted. A SIGKILL of the
  owning CLI process relocked the console in 2.9 seconds. Locked use then
  showed `recovering` (`owner_disconnected`, recovery condition
  `same_console_locked_healthy_and_quiet`) and became `ready` again within
  about 35 seconds, when a fresh prepared call succeeded. The claim has its own
  four-hour ceiling. Locked use enforces no separate total limit on a renewed
  owner, so agents' "15-minute" limit is only the renewal interval.
- **Current, item 4 confirmed.** Restarting the resident while locked left
  both surfaces Off. A Browser call refused with `surface_disabled` (`This
  surface is Off`), and a prepared Desktop call ended with `surface_disabled`.
  Doctor said only "the person enables a surface", without noting that this
  needs an unlocked console. This is the one case reproduced here where an
  agent truly needs the person.
- **Current, new finding.** In a prepared-console stream, a read that races
  covered activation is refused with `control_generation_changed` (no
  delivery, no uncertainty) while the owner stays live. Before the repair below,
  that also ended the stream.
- **Correction and limit, item 6.** Guest Screen Sharing through a headless
  AsyncVNC client connected as observe-only ("Your screen is being observed"):
  typed password characters never reached the login field. So the pointer
  movement and Escape sent that way during covered control show nothing about
  how remote human input is classified; they were probably not delivered at
  all. Kernel `IOHIDPostEvent` movement and an Escape key-down, from the
  extended `kernel-pointer-fixture --key`, were delivered but did not end the
  covered owner. The guard counts only events whose source process ID is 0, and
  these carry the posting process. In this VM profile no available route
  simulates physical takeover: the outer Tart window route is prohibited here
  and would drive the controller desktop. Takeover by key, click or scroll,
  movement tolerance, the `local_use_episode` pause after a password unlock,
  and quiet resumption therefore remain **Open** for an operator-supervised
  physical cell. Source review (`LockedUse.swift` event tap,
  `Broker.m` pause handling) supports the documented design but does not
  qualify it.

### Repairs and their verification

Commits `4b508f83`, `01bf3b04`, `371a52d9`, `d2e917b9` and `da1e84a3`. The
same workspace was verified again with a rebuilt resident and the committed
source client:

- **Streams.** `status` and `desktop.status` inside a stream are answered
  from ordinary read-only status. A refusal that dispatched nothing
  (`safe_not_dispatched`) or a read that delivered nothing with no uncertainty
  keeps the stream open. The locked VM sequence status, generation refusal,
  capabilities, refused `browser.tabs`, status (now unlocked) and applications
  ran on one owner and exited 0 with an observed relock. One-shot `control call`
  is unchanged.
- **Status.** On the locked console with a prepared route, `browserWhileLocked`
  now reports `active: true, requiresUnlockedApproval: false` (macOS).
  `requiresUnlockedApproval` is true only for Ask first on macOS, Linux and
  Windows. A Browser stream worked while locked.
- **Doctor.** Host doctors add `extensions.lockedConsole`. The client adds a
  `locked_console` check, for example: "The console is locked. Browser
  commands work now without unlocking. For Desktop work, or anything that needs
  the session unlocked, hold `control stream --surface desktop
  --prepared-console` ... Do not ask the person to unlock." With a prepared
  route, the locked `fail` checks become `warn`. After a restart while locked it
  reports access Off and that only the person can turn it on from an unlocked
  console. `ready` keeps meaning ordinary unlocked readiness.
- **keep-unlocked.** `control keep-unlocked --for D --reason TEXT` refused on
  an unlocked console and when the claim was shorter than the hold. It unlocked
  in about 12 seconds (`IOConsoleLocked` false and no
  `CGSSessionScreenIsLocked`). It ended `duration_elapsed` after 2 minutes, and
  ended `signal_sigterm` on SIGTERM, each with an observed relock.
- **Agent instructions** describe these rules, the stale one-shot
  references, and relock on owner process exit.

### Remaining limits

- The Windows `requiresUnlockedApproval` change and Windows `keep-unlocked`
  use were not compiled or run: this controller lacks the .NET SDK and no
  Windows target was exercised. Linux has no locked Desktop route;
  `keep-unlocked` refuses there through `locked_use_unsupported`.
- One-shot `browser snapshot` references remain stale for later one-shot
  commands by design (owner-generation fencing). The repair is guidance to use
  one stream, not a cross-owner reference model.
- Physical takeover, password-unlock local-use pause and quiet resumption,
  Touch ID, lid and multiple displays need the physical cell above.
- A flagless one-shot Desktop request on a locked Mac is still admitted as
  covered control (about 29 seconds per call). This tactical did not change it.
- `browser_detached` in the original incident was not reproduced. The extension
  emits it only when Chrome detaches its debugger, and an unlocked session hit
  it too, so the lock is not its established cause.

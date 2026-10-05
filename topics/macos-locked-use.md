# macOS locked use

Topic: `macos-locked-use`

Status: implemented experimental first version; bounded one-display Tart VM
evidence and SIP-enabled physical idle-lock, successive-task and expiry evidence
on macOS 26.6.2. Operator-confirmed physical takeover/recovery is live-tested
with a scripted timing caveat. Multiple displays, additional OS revisions,
Intel execution and distribution qualification remain open.

## Decision

Add an initially disabled, persistent local setting named **Allow Machine
Control while screen is locked**. The person completes native helper approval in Permissions, then enables
the preference, approves ordinary access, and locks the Mac normally.
The checkbox never requests a grant or installs software.
An approved, bounded control session may temporarily unlock the existing
console session behind opaque covers on every display. The setting grants no
ordinary access by itself. No account password is stored by this feature.

This follows the documented [OpenAI locked-use flow](https://learn.chatgpt.com/docs/computer-use#locked-use).
Product wording and task-end relock are Machine Control decisions, rather than
claims about undocumented OpenAI UI or implementation details.

**Decision, current source:** cleanup may request lock only when the task's
native starting observation was locked. An unlocked-origin legacy control
lease ends when a later idle lock occurs; it cannot enter covered unlock or
inherit relock authority. Ordinary completion leaves an unlocked console
unlocked. The new regression is in `LockedUseTests`; native Mac execution of
this adjustment remains pending. [Tactical 102](../docs/tactical/102-windows-covered-control.md)
owns the cross-platform correction and Windows cover slice.

**Current source:** physical keyboard/pointer activity cancels control and
requests immediate relock while preserving otherwise valid ordinary access.
Manual Pause gates observations/actions and ends covered control without
revoking that access. Root automatic-unlock inhibition still needs the new
quiet/resume integration; physical acceptance of this source is pending.
Display changes, sleep, session changes, expired access, Stop, disconnect,
process failure, and disabling the setting end temporary unlock. Covers remain
until lock is independently observed. A root watchdog owns failure relock;
ordinary provider calls remain grant checked and generation bound.

**Current policy:** prepared locked use retains existing ordinary approval
across idle locks
and clean task completion, within the approving console and approval lifetime.
Every subsequent task still acquires a finite owner connection. Changing console
identity, unknown state, safety failure, missing preparation or expiry ends
access. Ordinary manual/physical pauses retain valid access.

**Decision — next direction:** ordinary physical takeover should pause access
and preserve otherwise valid standing authorization. Fresh covered control may
resume when locked and physically quiet; an owner who unlocks to work remains
protected by a local-use pause. Explicit Pause, Resume and Stop have distinct
effects. The cross-platform
[access admission and pause topic](access-admission-and-pause.md) owns this
successor contract and its proposed implementation plan. These semantics are
partly implemented in source; unattended resumption and physical acceptance
remain open. Earlier physical evidence retains the behavior of its tested
revision rather than inheriting these new semantics.

## Boundaries

- First version: awake Mac, open lid, existing console session only.
- No sleep prevention, closed-lid control, fresh login, FileVault/preboot,
  general remote unlock, or arbitrary privileged command API.
- First implementation uses native desktop input/capture; unsupported routes
  must refuse rather than produce covered screenshots or bypass takeover.
- Existing explicit appliance unlock retains its separate authority/profile.
- Same-user shell access is not contained. The authorization plug-in consumes
  a short session-wide grant; it cannot authenticate the original agent.
- Local enable/disable belongs to the native operator, never the agent socket.

## Current implementation

Permissions owns SMAppService registration, native System Settings helper
approval, typed preparation, and the capture-consent preflight. The Settings
checkbox only persists the local preference after preparation is ready.
After a signed update, native maintenance refreshes an already approved managed
helper on the same unlocked console, once per launch and only while idle and
unpaused. Preparation preserves the checkbox choice; initial setup remains off.
Ordinary same-build launches leave a healthy helper alone. Initial installation,
revoked OS approval and actual failures remain visible in Permissions.
Disabling immediately persists local revocation; installed idle helpers have
no standing grant. The existing signed executable runs a separate cover/input
guardian, while the root broker owns the maximum deadline, heartbeat watchdog,
and durable restart marker. Operator windows are hidden during coverage to
preserve self-interface protection without blocking underlying pointer targets.

The same typed `session.control` / exact-ID `session.control.end` contract works
locally and remotely. The calling integration must own that bounded connection
for the real task; the resident does not infer completion from unrelated calls.
Native capture, AX/key/pointer effects, physical keyboard/pointer takeover,
completion, expiry, disconnect, resident stall/crash, persistent pause, and
manual recovery have bounded VM evidence. See the
[current guide](../platforms/macos/docs/locked-use.md) for usage and removal.

**Current:** integrated physical control passed programmatic lock, automatic
covered unlock, native fixture AX/pointer/keyboard effects, filtered capture,
and independent completion relock with no remaining covers or manual-unlock
pause. The trigger verifies loginwindow's kernel identity and posts directly to
it; screen notifications check actual layout and cover health. Native helper
repair also succeeded after fixing re-registration ordering. Tactical 067 owns
the bounded evidence and the earlier negative/diagnostic trials.

**Current:** the installed revision retains prepared, unpaused approval across
expected locks and binds each grant synchronously to the approving console.
Physical idle lock, two consecutive already-locked tasks and bounded task expiry
passed with an unchanged approval and independent OS relock. Each task verified
exact single-fixture PID/oracle attribution and native AX/pointer/keyboard
effects. Agent capture showed the fixture beneath excluded covers. None of
those cells required a manual unlock, external wake or new approval between
tasks. Physical takeover also recorded immediate cancellation, OS lock, revoked
Access and a manual-unlock pause; observed recovery cleared the pause while a
new task still refused without fresh approval. The operator confirmed the
takeover worked. It raced the runner's startup assertion, and the independent
probe ran after recovery, so the full scripted takeover cell is not passed.
Tactical 070 owns those precise live-tested boundaries and the timing caveat.

**Current:** all 91 Swift tests, ARM64/Intel framework builds and strict signed
candidate verification pass.
Automatic maintenance of the existing approved helper and same-build relaunch
passed on the physical Mac without a Repair click. App restart still clears
ordinary Access; maintenance does not regrant it.
A bounded native display wake in guardian startup passed task activation from
an inactive display while the OS remained awake. The temporary assertion is
released on readiness or bounded failure; no standing sleep-prevention policy
is installed. That signed update again maintained the helper automatically and
preserved the enabled checkbox. Tactical 073 records the earlier readiness gap
and bounded physical fix.
**Open:** a full scripted physical takeover cell with independent lock readback
before recovery, multiple displays, additional OS revisions, Intel execution
and distribution qualification.

## Execution

[Tactical 064](../docs/tactical/064-macos-locked-use.md) owns implementation,
validation, and the precise final acceptance scope.

[Tactical 065](../docs/tactical/065-macos-helper-permission.md) replaces the
initial command/password setup with the native permission flow. Its live
acceptance remains separate from Tactical 064's earlier VM evidence.

[Tactical 066](../docs/tactical/066-macos-physical-locked-use.md) records the
failed physical trial and safe manual recovery, rather than physical acceptance.

[Tactical 067](../docs/tactical/067-macos-physical-unlock-trigger.md) owns the
programmatic-lock and targeted-trigger iteration and its remaining acceptance.

[Tactical 070](../docs/tactical/070-macos-locked-access-retention.md) owns
console-bound access retention and successive unattended-task acceptance.

[Tactical 072](../docs/tactical/072-macos-helper-update-maintenance.md) owns
approved-helper update maintenance, choice preservation and ordinary relaunch.

[Tactical 073](../docs/tactical/073-macos-locked-display-wake.md) owns bounded
display wake for authorized task startup after idle lock.

**Current (source/policy fixtures):** [Tactical 077](../docs/tactical/077-mac-quiet-resumption.md)
replaces the physical takeover root latch with a durable physical/local-use
pause. The same locked console may resume after 30 seconds of trustworthy HID
idle and pause age; owner-unlocked work stays paused. Helper faults retain
separate recovery. This has not yet replaced the prior signed physical result.

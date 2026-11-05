# 157 - Desktop access experience

Owning topics: [desktop-access-experience](../../topics/desktop-access-experience.md),
[access-admission-and-pause](../../topics/access-admission-and-pause.md),
[runtime-and-presentation](../../topics/runtime-and-presentation.md).

Status: **Implementation authorized; frontend phase accepted.**

## Objective

Record the agreed design, review independently, then discuss implementation
scope with the operator. Simplify the working product through small UI and
bounded policy changes, without repeating the previous architecture migrations
or a broad qualification campaign.

The motivating request followed a functional installed smoke test: confusing
Ask first/Automatic controls and similar notices, too much text, repeated Apply
buttons, global/surface pause clutter and misleading presentation names. The
operator chose separate Desktop/Browser switches and start settings; task-local
delays in Activity; configurable Desktop yielding; and no automatic Browser
physical-input yielding for now.

## Completion conditions

- A design records copy/sketches, On/Off and draft/apply semantics, task notices,
  delayed approvals, Desktop yield, Browser exclusions and startup presentation.
- An independent reviewer checks UX and code feasibility and identifies changes
  that need more than presentation work.
- A staged plan defines files, focused validation, limits and deferred work.
- Findings are resolved or explicitly retained for discussion. The operator
  receives the plan/review before product implementation.

## Boundaries

- Reuse shared admission and native presenters; no React authorization timers.
- No new provider/controller, inventory/credential flow, browser interaction
  detector, foreground-as-intent heuristic or tab ownership engine.
- Preserve exact profiles, owner/claim/consent ceilings, Stop, generation fences,
  unknown-readiness handling and protected session/cover/relock guards.
- The operator subsequently authorized implementation, Opus review of each
  phase and a commit after each accepted phase. No provisioning, installed
  replacement or release is required.
  Reviewer prompt/output/session receipts remain private; publish only sanitized
  conclusions. One reviewer, no nested delegation or product edits.

## Ordered work

### 1 - review design and implementation scope

Read the [design](../../topics/desktop-access-experience.md), surface component,
native notices/status, shared admission and current fixtures. Request one review
through the operator-selected YA route. Verify selected/applied model, effort,
permission mode and work-pool binding, retain exact worker identity privately,
collect the report and stop the owned reviewer process.

Resolve contradictions before implementation: master/surface On, enabling dirty
settings, partial Apply, consent renewal, delayed approval versus deferral,
per-surface policy fields, task-only pause versus resource deferral, and recovery
of existing global/surface pauses. Review is not authorization to implement.

### 2 - simplify Access and move task decisions to Activity

**Review recommendation:** this is the first deliverable, together with startup
relabeling. Keep it frontend-only: retain current ask/automatic semantics and
one honestly labeled shared warning duration; omit Immediate, Allow-in and new
task-only Pause controls until their runtime support exists. Native notices
remain unchanged in this slice, so do not claim Allow starts without countdown.

Edit `desktop/src/surface-access.tsx`, `desktop/src/main.tsx`, existing choice
storage/styles and `tests/desktop/surface-access.mjs`.

Use one draft model/dirty comparison and one conditional sticky Apply/Discard
footer. Off is immediate; On explicitly grants using visible selections. Apply
only changed surfaces. Preserve edits across polls and show concurrent changes.
If bridge methods apply sequentially, show partial success and resynchronize;
do not imply a new atomic configuration engine or retry uncertain mutations.
Do not extend consent by applying unrelated/unchanged settings. Existing
configure renews the changed surface's timed lifetime: choose explicit renewal
copy for a frontend-only slice or add exact preserve-expiry support separately.
Do not approximate exact expiry with a timer in React or silently round a short
remaining lifetime up to the native minimum.

Move live requests/task controls to Activity. Remove general pause clusters;
use existing Allow/Start now/Cancel, and show inherited resource/surface holds
with accurately scoped Resume. Task-local Pause/Continue is a later primitive,
not a relabel of today's resource-wide deferral. Preserve advanced/Permissions
discoverability. Hide unimplemented options in any intermediate deliverable.

### 3 - simplify native notices, status and startup controls

Stage native work after the first frontend slice and the separate core-only
Browser exemption; numbered work here records dependencies rather than requiring
native changes before the smaller core patch. Native notice changes should land
with the corresponding start/delay policy instead of exposing inert controls.

Update Mac `AdmissionNotice.swift`/`StatusMenu.swift`, Windows native notice/tray
presenters and Linux notice/tray UI. Reuse exact-intent binding, native Stop and
owner lifecycle. Add a brief yield acknowledgement, compact semantic status,
accessible icon labels and truthful ended-task feedback. Coalesce transitions;
avoid notification spam and focus stealing. Browser activity is not desktop
takeover. Keep wire terminology where harmless instead of renaming all APIs.

Replace the startup profile dropdown with concrete behavior labels mapped to
existing modes. Do not create an unsupported fourth combination or modify
authorization. Keep active visibility, required prompts, Stop and Settings
recovery independently available.

Reuse existing agent wire states (`paused` plus blocking reasons,
`waiting_for_approval`) rather than introducing yielded/scheduled as new wire
states that current clients reject. Linux notification banners have limited
actions: use Allow/Decline/Open there, with delay menus in the full native panel.
Define dismissal without an implicit new resource deferral.

### 4 - implement bounded start and delay policy

Change the shared policy/protocol first, then thin operator adapters and UI:

- Per-surface countdowns including zero for explicit immediate start; the
  existing single `noticeSeconds` is insufficient.
- Initial approval authorizes and starts without a redundant second warning;
  all adapters must acknowledge that operator click before activation, including
  Allow from Activity, so a late-published click cannot immediately yield.
- Task-bound delayed approval and deferral under the existing owner/consent/task
  ceiling, cancellable and unable to survive disconnect/Stop/restart as authority.
  Disable choices exceeding the current remaining wait/task ceiling. New
  intent-local not-before/hold state does not reserve resources while waiting.
- Migration preserves existing Ask/Automatic choices and timed consent. Version
  or advertise new fields; unsupported clients must not broaden authority.

Use `runtime/src/admission.ts`, existing host/operator protocol and platform
adapters. Keep transitions/audit shared and timers authoritative. Do not record
secrets or unnecessary task content. This patch is separate from form-only work.

### 5 - add Desktop yield options and exempt Browser from input yielding

Browser-only work, including CDP/evaluation/streams, must not yield because of
human input. Do not simply label all Browser work nondisruptive: contention,
initial handoff, profile, console and safety checks still matter. Separate yield
eligibility from the existing disruptive/resource classification only as needed;
ensure native input publication cannot reintroduce a Browser yield elsewhere.

**Review recommendation:** deliver the Browser exemption as a small core-only
patch after the UI slice and before new native controls. Gate both input-trigger
and cooldown/physical-monitor-readiness blocks on a Desktop-including predicate.
Decide Browser's human-input reservation explicitly; do not leave non-yielding
Browser tasks holding Desktop behind a renewable owner forever. Keep the existing
countdown/impact classification separate. See discussion points below.

Implement configurable Desktop wait and continue/reapprove once in shared policy.
Reapproval also gates Automatic tasks after yield. Preserve the original live
owner, consent ceiling, fresh sessions/references and no uncertain replay.
Desktop-dependent compounds retain Desktop admission/yield. Unsupported native
fallback refuses. Protected input/quiet/relock policy is unchanged; surface
stronger blocks truthfully instead of promising ordinary timeout continuation.

### 6 - validate the changed surfaces narrowly

Use existing deterministic infrastructure first, then bounded native effects.
Use retained claimed targets if needed; no factory rebuild or full historical
matrix just to change UI. Expand only when actual changes/failures warrant it.

| Change | Focused evidence |
| --- | --- |
| Form/layout | TypeScript/build; headless UI fixture for switches, dirty Apply/Discard, Off while dirty, refresh/concurrent changes, partial failure, exact profiles and minimum window layout; visual review |
| Task/status/notices | Exact-intent commands, stale callbacks, expiry/disconnect, unavailable/ended states, native render/layout and no-focus-steal smoke |
| Startup copy | Round-trip existing mode mapping; active status/Stop/Settings recovery; no authorization mutation |
| Start/delay | Fake-clock tests for zero/per-surface countdown, approve-and-start, delayed approval versus deferral, Off/cancel/disconnect/expiry and no resurrection |
| Desktop yield | Configured wait, movement ignored, approval-click acknowledgement, continue/reapprove including Automatic, fresh ownership and no replay |
| Browser exemption | Fake-clock admission and existing process-inlet tests: input, Desktop cooldown and unknown physical-input monitor do not block Browser; pause/Off/expiry/cancellation and Desktop-dependent gates remain; explicit resource-rule test. Real-browser smoke only if route/stream dispatch changes or deterministic evidence leaves uncertainty |

Existing commands:

```sh
pnpm --dir desktop build
pnpm --dir desktop test:access-choices
pnpm --dir desktop test:surface-access
pnpm --dir runtime check
pnpm --dir runtime test
```

Use project Playwright Chromium or another separately identified test browser,
never the user's primary browser with a temporary profile. Keep captures/live
evidence private. Follow doctor/claim/renew/release and usage-note policy for
accepted VM targets. No broad platform effect claim follows from a mocked UI.

Build native adapters whose code changes. .NET runtime edits still require
format verification, contract tests and ARM64/x64 publishes. Native notices
need their platform render/build evidence; Mac smoke is not Windows/Linux
native acceptance. Report unavailable checks. Protected changes or dispatch
regressions justify broader validation. Normal candidate/release gates remain
in force if publication is later requested.

## Review and final result

**Current:** an independent Opus 5.5 high review completed through the
operator-selected YA work pool with bypass permissions. Selected/reported model,
applied effort/permission mode and pool binding were verified privately. The
reviewer performed source inspection only, wrote a private report and was
stopped with verified shutdown and automatic resume disabled. Heartbeat-disable
confirmation was false; no stronger cleanup claim is made. No product edits or
tests were performed by the reviewer. Raw report and operational identifiers
remain private.

The review accepted the UX direction and recommended frontend first, followed
by the small core-only Browser exemption, then separately reviewed native/
operator-policy changes. Its main actionable findings are incorporated above:

- Existing task Pause is a shared-resource deferral, not task-local; it prevents
  bypass by creating replacement tasks. True task holds need an explicit rule.
- Browser exemption must address input triggers, the global cooldown and
  activity-monitor readiness separately from countdown and resource arbitration.
- Configure resets timed consent. Expiry preservation needs actual support or
  explicit renewal copy, not a presentation-only promise.
- Delayed approval/hold options must fit current wait/task deadlines. Approval
  without a countdown requires operator-input acknowledgement on every adapter.
- Existing clients can retain wire states with new reasons. Native range and
  Linux notification-action differences must be handled in their own slices.
- Startup can be relabeled through one concrete three-choice selector, without
  introducing new runtime profile combinations.

### Discussion before implementation

1. Keep the first deliverable strictly frontend-only, with existing semantics
   and explicit timed-renewal copy, or include the tiny expiry-preserving
   operator change? Do not quietly advertise the full future behavior.
2. For a future manual task hold/reapproval, should replacement Desktop tasks
   also wait for approval? The review recommends retaining protection against
   bypassing the operator by submitting a new task. Also decide whether a yield
   always gets a fresh short warning even under immediate initial-start mode.
3. Remove Browser-only ownership of the shared human-input resource, allowing
   Desktop and Browser work concurrently? The review recommends this alongside
   no Browser automatic yield, while retaining Desktop requirements for actual
   native input/dialogs and existing browser/profile contention.

**Current result:** written design, implementation sequence and source review
are complete. Document links and whitespace are checked. Product code, runtime
settings, target installations and release state are unchanged. Implementation
and any later qualification remain pending operator discussion.


## Implementation execution

### Phase 1 - compact Access and Activity

**Current:** frontend implementation and focused checks completed; independent
Opus review accepted after fixes. Independent surface switches, remembered
master selection, draft Apply/Discard with explicit timed-renewal consequence,
concurrent/partial-failure handling, Activity task actions/recovery and concrete
startup labels reuse the existing operator methods. New timing/yield choices
are not exposed until their policy support lands.

Validation: desktop build, access-choice fixture and the updated surface fixture
pass. The surface fixture exercises no automatic arming, dirty edits/navigation,
Off while dirty, exact profiles, Apply touching only affected surfaces, partial
failure, concurrent edits, Activity actions, startup and minimum-width layout.
These are mocked-native frontend checks, not native/package acceptance.

Phase 1 review fixed master-On authority guessing and restored exact Browser
profile disclosure in Activity approvals. Follow-up review accepted the phase;
smaller fixes retain surface memory on Apply, keep unapplied duration edits,
avoid inert Resume controls and preserve Off during unavailable/busy state.
Native notices and new timing/yield behavior remain for subsequent phases.


### Phase 2 - Browser physical-input independence

**Current:** shared policy separates physical-input eligibility from disruptive
countdown classification. Browser-only tasks do not reserve human-input or wait
for Desktop input readiness/cooldown; compounds retain Desktop guards. Updated
fake-clock and process-inlet checks cover independence/concurrency, manual
pause/Stop, stale owners and refusal of native Desktop work on Browser owners.
Runtime strict checking and all shared runtime checks pass before review.
Independent Opus review accepted the phase with a recorded foreground-opt-in
interference follow-up. Its focused admission suite passed independently; the
coordinator's complete runtime suite and strict check also pass. Added the
reverse Browser-deferral/Desktop-independence assertion and narrowed the input
monitor copy to Desktop. No native/provider dispatch code changed.


### Phase 3 - bounded shared start, delay and yield policy

**Current:** per-surface zero/countdown preferences, explicit approve-and-start,
intent-local delay/hold and Desktop continuation/reapproval are implemented in
the existing shared core/operator inlet. Agent wire states remain unchanged.
Manual holds/reapproval gate replacement starts on the surface until an
explicitly approved task acquires it. Returning after Desktop yield on a presentable
unlocked route warns for at least five seconds, even in immediate mode and for a replacement
task. Original wait/task/consent/owner ceilings remain authoritative.

Fake-clock cases cover independent/compound notice lengths, delayed approval
versus postponement, expiry/Stop/disconnect, held-task resource release and
anti-bypass, configurable yield wait, stale sessions and next-start reapproval.
Native input acknowledgement and presentation integration follow in phase 4;
this core phase is not packaged/native acceptance.

Phase 3 follow-up Opus review accepted after queued pre-yield approvals and
non-input Desktop accepts were prevented from bypassing the return warning.
Continue now respects protected/readiness blocks; stale active approvals are
idempotent and cannot schedule a running task. Delay checks include notice
budget. All 96 runtime tests and strict checks pass. Native/UI integration is
still separate, and scheduled eligibility remains subject to actual readiness.

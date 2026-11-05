# Desktop access experience

Topic: `desktop-access-experience`

Status: **Implementation authorized; frontend phase accepted.** The operator
authorized staged implementation, independent Opus review and a commit after
each accepted phase. The target design below is not yet fully implemented.
[Tactical 157](../docs/tactical/157-desktop-access-experience.md)
owns sequencing, review, validation and results. This topic owns the proposed
product experience; [access admission](access-admission-and-pause.md) owns
existing policy and evidence. Proposed behavior below is not shipped evidence.

## Motivation and boundaries

**Current:** mode changes apply immediately while profile/duration changes need
Apply. Repeated Apply buttons, explanatory text and global/surface pause
controls obscure ordinary use. Native approval and countdown panels look too
similar. Personal/minimal/appliance presentation names suggest authorization
differences they do not supply.

**Decision:** simplify the experience over the existing shared admission engine
and native providers. Keep Desktop and Browser separately configurable, with no
shared setting and hidden Browser override. Access contains configuration;
Activity contains live task decisions and waiting details. Preserve exact
profile authorization, owner/claim/lifetime/generation checks, Stop and native
protected-session safeguards. Do not undertake another platform migration.

## Access page

**Decision:** one master Agent access switch and separate Desktop and Browser
switches. Off disables governed access and cancels affected tasks, rather than
pausing them. Master Off affects both surfaces. Explicitly enabling access
never resurrects previous tasks, connections or references.

```text
+------------------------------------------------------+
| Machine Control                                      |
|                                                      |
| Access    Activity    Permissions    Settings          |
| ------                                               |
|                                                      |
| Agent access                              [ ON ]     |
|                                                      |
| Desktop                                   [ ON ]     |
| Before starting                                      |
| [ Give me a heads-up                       v ]        |
| [ 10 seconds                               v ]        |
|                                                      |
| Browser                                   [ ON ]     |
| Before starting                                      |
| [ Start immediately                        v ]        |
|                                                      |
| Browser profiles                                     |
| [x] Personal                                         |
| [ ] Work                                             |
|                                                      |
+------------------------------------------------------+
| Unsaved changes              Discard   Apply changes  |
+------------------------------------------------------+
```

**Decision:** master On means at least one surface has live authorization;
individual switches identify which. Master On explicitly enables the remembered
selected surfaces with the visible choices, not every capability/profile. With
no valid remembered selection, require a choice instead of guessing. Off keeps
form preferences, not authority. Expired access is not On; provider failure or
a safety block gets a concise unavailable state rather than falsely claiming
the operator switched Off. Turning an individual surface On while master access
is Off grants only that surface and makes the derived master display On. If
one surface expires, the other remains enabled under its own lifetime. Advanced
settings that currently turn access Off must update these same live switches
and show that consequence before the change.

**Decision:** Off takes effect immediately even with unsaved edits. On is an
explicit authorization action that applies visible settings and the selected
lifetime. Editing an enabled surface's start behavior, profiles or duration
stays draft until Apply. Discard does not change authority. Keep live enabled
state separate from draft configuration.

**Decision:** one sticky footer appears only for unsaved changes. Remove
per-card Apply/Enable buttons and routine instructional paragraphs. If applying
a changed surface ends its tasks, show that consequence once near Apply.
Apply only affected settings; do not reauthorize an unchanged surface, extend
finite consent or restart work through an unrelated edit. Preserve dirty edits
through status refreshes; expose concurrent changes and partial apply failures.
Do not imply atomic success if native methods applied surfaces sequentially.

**Current, review finding:** existing `surface.configure` ends a surface's
tasks and resets its timed expiry to now plus duration, even for a mode/profile
edit. Exact expiry preservation is therefore not just a React dirty-state
change. **Open:** use a bounded preserve-expiry operator change, or retain the
existing renewal behavior with an explicit duration/renewal consequence in the
first frontend-only slice. Do not claim that Apply preserves expiry until it
does. Applying an unchanged surface is unnecessary in either approach.

**Proposal:** existing access-duration choices live in an expandable access
options section. Preserve the selected/default lifetime; never silently turn
finite consent into indefinite consent. Protected/locked-use options stay
discoverable in advanced options/Permissions with unchanged setup and guards.

### Before starting

**Decision:** each surface independently offers:

| Choice | Behavior |
| --- | --- |
| Start immediately | No advance warning or approval click; active status remains visible |
| Give me a heads-up | Start after a configurable countdown unless delayed/cancelled |
| Wait for my approval | Start only after explicit approval for this task |

Only heads-up displays a seconds control. Suggested choices: 5, 10, 30 and 60
seconds. Do not show zero or infinity as user-facing mode values. Task/owner
expiry still applies to an approval wait.

**Decision:** migrate Ask first to Wait for my approval, and Automatic to
heads-up with its existing duration. Immediate requires explicit selection.
Approval combines permission and initial start; no redundant second warning or
approval. Desktop and Browser warning durations must be independent; today's
global notice field cannot honestly represent the design.

## Task notices and Activity

**Decision:** task means the existing connection-owned admitted task, not every
click/tool call. Show task reason and surface; preserve truthful caller
assurance in accessible details. A task name is not verified agent identity.

```text
+--------------------------------------------+
| Agent wants to use Desktop                  |
|                                            |
| Edit a note in TextEdit                     |
|                                            |
| Decline       Allow in... v       Allow now |
+--------------------------------------------+

+--------------------------------------------+
| Desktop control starts in 10 seconds        |
|                                            |
| Edit a note in TextEdit                     |
|                                            |
| Cancel        More time v         Start now |
+--------------------------------------------+
```

**Decision:** notices never steal focus. Start now shortens an authorized wait;
Allow now authorizes and starts this task. The input used to choose either
must not immediately trigger yield. Decline/Cancel ends only the named task.
Immediate mode has no advance popup but retains active status and Stop.

**Decision:** Allow in an interval is explicit delayed approval for that exact
task under the original consent/owner/task ceiling. It is not merely deferral
of an unanswered approval request. More time postpones the named authorized
task. Suggested intervals: 30 seconds, 1 minute and 5 minutes. Dismiss the
popup after choosing; show the result in Activity:

```text
Edit a note in TextEdit
Desktop - Allowed in 4m 32s              Cancel   Allow now
```

If the live owner/authority cannot survive the interval, refuse the choice or
show the task ended; never extend consent or manufacture a replacement task.
The time denotes eligibility, not guaranteed dispatch: contention, readiness
and safety still apply. Replace the timer with the actual blocking reason.

**Decision:** Activity shows active, waiting, yielded, manually paused and
recently ended tasks with minimal reason/surface/time and applicable controls.
Remove general Pause/Resume controls from the normal Access page/menu.
Task-specific Pause/Continue and Cancel/Stop are the target Activity experience,
including for Browser. A manually held task stays held until continuation,
cancellation or the original task/owner/consent deadline; it is not kept alive
indefinitely. Master/surface Off stops the relevant work immediately.
Existing external/manual pauses must remain visible and recoverable during
migration; removing their old controls must not strand an installation.

**Current, review finding:** today's request Pause writes shared resource
deferrals, can hold other tasks and survives the original task ending. There
is no intent-local Continue primitive. The first UI slice must label inherited
holds by their actual scope, for example "Desktop held" with Resume in Activity,
instead of presenting them as task-only pauses. **Open:** whether a future
task-local hold also gates replacement tasks on that surface, retaining today's
protection against bypass by opening a new task. Define popup dismissal
explicitly too; current Windows/Linux dismissal can defer resources.

## Yielding

**Decision:** use yielded for returning control after deliberate human input.
Hide raw physical_takeover/global pause/deferral names. Yield does not turn
access Off and cannot undo already-delivered effects.

### Desktop

**Current:** ordinary Desktop yields on non-agent keypresses, mouse clicks and
scrolling, not movement alone. A fixed 60-second cooldown precedes a fresh
warning for a still-live eligible task; continued input does not reset that
minute. A CLI stream may instead end on interruption. Protected/covered control
has additional native safety rules.

**Decision:** retain immediate Desktop yield and add an expandable section:

```text
When you take control                              v

  Wait before trying again       [ 1 minute       v ]
  Then                           [ Continue task  v ]
```

Suggested waits: 10 seconds, 30 seconds, 1 minute, 5 minutes. Then offers
Continue the approved task or Ask for approval again. Default: 60 seconds and
preserve approval, matching the operator's pause-like preference. Reapproval
clears only this task's permission and also applies when the surface normally
starts automatically. It does not turn the surface Off or affect other tasks.

**Decision:** continuation requires the same live task and valid original
consent, fresh ownership/references and observation; never replay uncertain
actions. Automatic continuation follows the configured warning, or no warning
for immediate mode. Reapproval waits for Allow after the delay. Wait and warning
are additive: 60 seconds plus 10-second notice means roughly 70 seconds.

**Open, review recommendations:** always give a short heads-up after Desktop
yield, including when initial starts are immediate; and make reapproval gate
the next Desktop start rather than only the interrupted intent. Otherwise a
still-typing operator can encounter a restart/yield loop, or a replacement
Automatic task can evade the reapproval choice. These are proposed refinements
for discussion, not silently adopted changes to the agreed initial-start UI.

**Decision:** briefly acknowledge yield without focus stealing:
"You have control. Agent waiting 1 min." Show its timer and Continue now/Cancel
in Activity, not permanent Access-page text. Disconnected tasks are ended,
not promised to resume. Ordinary settings cannot bypass protected quiet,
cover, relock, recovery or other native safety blocks.

### Browser

**Decision:** no automatic physical-input yielding for Browser-only automation
in this iteration. Typing, clicking, scrolling, switching apps, foregrounding
an agent tab or watching its work do not yield it. Defer same-tab interaction
detection, foreground-as-intent heuristics and tab ownership redesign. Tab
groups are presentation, not an authority boundary. The operator can manually
pause/cancel in Activity, disable Browser or turn all access Off.

This is a bounded behavior change from unrestricted Browser's conservative
admission today. It does not remove initial approval/countdown, exact-profile
selection, debugger/tab contention, owner liveness, expiry, cancellation,
generation checks, console/session policy or protected safety guards. Never
yield Browser means no automatic physical-input yield, not immunity from Stop.

**Current, review finding:** `disruptive` currently couples countdown,
human-input reservation, monitor readiness and physical-input cooldown. Changing
the input callback alone does not exempt Browser: a Desktop cooldown can still
block it. **Proposal:** use an explicit Desktop-including yield predicate in
the shared core. Browser-only work should not depend on the physical-input
monitor's health; retain independent browser/provider/console safety checks.
**Open:** also remove Browser-only ownership of the shared human-input resource,
as the reviewer recommends. Keeping that reservation without yielding can let
long-running Browser work block Desktop indefinitely. Removing it allows
concurrent Desktop/Browser work and requires a deliberate resource-policy test.

**Decision:** native Desktop input, OS dialogs and other Desktop-dependent
operations still require Desktop admission and yield rules. Browser permission
never authorizes a native fallback. A compound owner may need to stop as a
whole when Desktop yields; do not promise independent continuation without
existing support. Do not solve this through a new browser impact engine.

## Status and startup presentation

**Decision:** menu bar/tray distinguishes Off, enabled/idle, approval needed,
starting, active and yielded/waiting. Use icon shape/badges and accessible
labels, not color alone. Short text/countdown can appear during transitions.
An active Desktop task takes precedence over less urgent Browser status;
background Browser work is not labeled desktop takeover. Put details in the
menu/Activity rather than more permanent Access controls.

**Decision:** replace Personal/Minimal/Dedicated appliance presentation names
with one concrete "When Machine Control starts" choice: Open Settings, Stay in
menu bar/tray, or Stay hidden until needed. This maps the existing three modes
without the unsupported fourth combination created by two independent toggles.
Do not change administrator-owned deployment policy. Native
approval, active status, Stop and explicit Settings recovery remain available
when idle presentation is hidden. Browser profile selection keeps its meaning
and is unrelated to startup/deployment profiles.

## Delivery scope

**Decision:** lead with frontend layout/copy/form consistency, task placement
and existing-state feedback. Per-surface countdowns, approve-and-start, delayed
approval, yield options and Browser yield exemption require small shared-policy
changes with focused evidence. They are not cosmetic edits. Keep these steps
separately reviewable and hide unsupported choices in intermediate UI slices.

**Decision:** avoid a broad VM rebuild or full qualification campaign for UI
polish. Use deterministic UI/policy tests, native render/build checks and bounded
route effects appropriate to actual changes. Do not infer full platform/package
acceptance from those checks. Existing release gates still apply if publication
is later requested. Implementation is now authorized with review before each phase commit; replacing
the installed app and publication are separate.

**Open:** final icon artwork, exact time choices, minimum-window layout and the
first implementation slice's boundary. Review and operator discussion precede
product changes.

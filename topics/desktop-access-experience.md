# Desktop access experience

Topic: `desktop-access-experience`

Status: **Source implementation complete in four independently reviewed
phases.** Focused frontend/shared-policy/native-adapter checks pass. Installed
package acceptance and publication are separate; see the tactical evidence
limits. The operator authorized a commit after each accepted phase.
[Tactical 157](../docs/tactical/157-desktop-access-experience.md)
owns sequencing, review, validation and results. This topic owns the source
product experience; [access admission](access-admission-and-pause.md) owns the
underlying contract and evidence. Source checks are not shipped-package proof.

## Motivation and boundaries

**Motivating observation:** the previous UI applied modes immediately but left
profile/duration edits pending. Repeated Apply buttons, explanatory text and
global/surface pause controls obscured ordinary use. Approval and countdown
panels looked too similar, and startup-profile names suggested authority they
did not supply.

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

**Current:** mode/profile/lifetime changes still use `surface.configure`, ending
the changed surface's tasks and starting a fresh consent ceiling. The single
Apply footer explicitly discloses that renewal/duration consequence. Warning
and yield-preference changes use a separate operator command, preserving live
consent and tasks. Unchanged surfaces are not reapplied. **Open:** exact-expiry
preservation for mode/profile replacement would need a separate typed change;
the UI does not claim it today.

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

**Current:** Activity's new task Pause uses an intent-local hold. The old
resource-wide deferral remains available for inherited pauses, accurately
labeled by scope with Resume. A manual hold requires approval for replacement
work on that surface until an explicitly approved task acquires it; cancelling
or expiring the original task cannot bypass the decision. Explicit surface
reconfiguration/Off clears this next-start gate. Dismissal of native notices
makes no implicit approval or resource deferral.

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
requires explicit approval of the next Desktop start, including replacement
Automatic tasks. It does not turn the surface Off or affect independent Browser
work; an approved task must actually acquire control to consume the gate.

**Decision:** continuation requires the same live task and valid original
consent, fresh ownership/references and observation; never replay uncertain
actions. Automatic return on an unlocked route with visible notices always
gets at least five seconds of warning, including immediate initial-start mode.
Reapproval waits for Allow after the delay. Wait and warning are additive:
60 seconds plus a 10-second notice means roughly 70 seconds. Explicit Continue
can end the ordinary input wait but cannot clear protected/readiness blocks.


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

**Current, source and deterministic/process-inlet tested:** the shared core
separates Desktop physical-input yielding from Browser countdown/impact policy.
Browser-only tasks neither reserve the shared human-input resource nor wait for
its monitor readiness/cooldown. This permits concurrent Desktop and Browser
work while preserving exact-profile/browser contention. Desktop-including
compound tasks retain Desktop input reservation, readiness and yield rules.
Native/package acceptance is separate from this bounded shared-policy evidence.

**Open, release boundary:** explicit Browser foreground opt-ins (including raw
CDP presentation controls) remain cooperative today and can bring Chrome forward
while a Desktop owner is active. This core-only change does not yet require a
Desktop-including fence for those opt-ins. Before qualifying Browser/Desktop
concurrency as preserving native input routing, gate foreground opt-in through
Desktop authority or explicitly qualify its residual interference. Ordinary
background operation remains preferred; this is not same-tab yield detection.

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

**Current:** the source UI and native adapters implement the design with the
existing presentation profiles and version-2 agent states. Time choices and
minimum-width layout are covered by focused fixtures; exact icon artwork and
broader native/package qualification remain later work. Explicit foreground
Browser opt-ins retain the interference boundary recorded above.

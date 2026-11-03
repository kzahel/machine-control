# Unified permissions and predictable handoff

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[shared resident core](../../topics/shared-resident-core.md),
[browser profiles](../../topics/browser-profiles.md).

Status: **implementation in progress; shared surface-policy checkpoint
implemented, Windows adoption and native acceptance pending**.

## Motivation and objective

The user reported repeated Windows desktop-busy refusals while trying to finish
local work. They want a warning with time to finish, followed by automatic
handoff unless explicitly deferred. Accidental mouse movement must not interrupt
an agent; deliberate takeover should yield and lead to another announcement
about a minute later. They approved independent Desktop and Browser modes and
confirmed that Browser includes supported CDP and page JavaScript.

The user prioritizes a clean Windows-first implementation over preserving
Mac/Linux compatibility. Temporary integration breakage or disablement is
acceptable. An inexpensive isolated legacy route may assist migration, but its
removal is part of the destination.

Implement the [owning contract](../../topics/access-admission-and-pause.md#unified-permissions-and-handoff-contract)
in one shared engine, prove it with stateful reference providers and synthetic
clients, then qualify the actual Windows operator/client/provider composition.
The earlier [Windows browser cutover](152-shared-runtime-windows-adoption.md)
remains accepted for its declared scope; its 39 checks do not establish this new
active-human handoff or permissions model.

## Completion conditions

- Independent Off / Ask first / Automatic modes for Desktop and Browser;
  one complete supported Browser capability and exact profile selection.
- Separate consent lifetime, operator pause, waiting intent and active ownership,
  with truthful status and no busy/refusal resubmission loop.
- The agreed countdown, deliberate-input classification, fixed cooldown and
  fresh-owner rules, including interaction with the notice itself.
- Independent browser work can proceed while Desktop waits, is paused or Off;
  compound native-desktop effects obey Desktop's selected mode.
- One shared policy runs under synthetic clients/reference providers and the
  Windows adapter; native identity/effects and safety remain native.
- Clean candidate acceptance, independent effects, honest platform/route limits,
  verified cleanup and an explicit legacy-removal accounting.

## Boundaries

Keep the Python CLI/client language, while allowing API/protocol changes needed
for the model. Keep Windows native authentication, activity classification,
UIA/capture/input, operator presentation and protected services. Preserve exact
browser identities and stale-reference fencing. Do not build an entire fake OS
or another grant/admission engine inside the reference provider.

Mac/Linux integration preservation is not a gate for Windows development.
Unsupported builds/routes must report that honestly and refuse incompatible
semantics. Do not silently run a legacy policy behind a new-mode UI. This plan
is not an all-platform implementation or a publication/personal-install change.
Protected/covered changes retain independent lock, cover, credential and relock
proof; ordinary desktop UX does not bypass those native guards.

## Ordered work

### 1 — define surface policy and migration

Map the existing scope flags, grants, admission states, notifications and client
handoff paths to the owning contract. Record the Windows source gaps: activity
can refuse a normal call before queue negotiation; quiet precedes announcement;
Start now does not acknowledge recent input; explicit quiet Off and configurable
surface modes are missing. Distinguish source findings from a reproduction of
an unknown historical installed build.

Specify a versioned surface-mode projection, task-bound Ask first authority,
request/response states, surface/global Pause and Stop, duration/expiry, and
unsupported outcomes. Settle foreground/compound routing and restart-consent
migration explicitly. Do not reinterpret a legacy narrow browser approval as
new full Browser authority. Identify any temporary adapters, their owners and
removal conditions before adding them. Replace tests for retired semantics;
do not add compatibility solely to keep an obsolete assertion passing.

### 2 — expand the shared core, reference target and synthetic clients

Move reusable authorization/admission/handoff policy into the existing shared
core. Trusted adapters supply observed intent, health, operator decisions and
provider effects; public caller labels cannot mint these facts. Model desktop
and browser effects independently behind that same engine.

Use a controlled monotonic clock and real client/host contract boundaries.
Synthetic clients retain connections, heartbeat, accept offers, cancel, die,
reconnect and contend. Hold provider completion independently of effect; release
late callbacks and verify that retired sessions cannot resume. Exercise the
cross-product of both surfaces' modes without duplicating policy in fixtures.

### 3 — adopt the Windows client and operator experience

Route ordinary calls into one waiting intent when appropriate, including during
activity/cooldown and operator pauses. Keep status and cancellation usable;
return terminal disabled/denied states clearly. Never replay dispatched actions.

Expose the surface modes, selected profiles, lifetime and pause status in the
operator UI. Provide native notices independent of Settings, visible countdowns
and the agreed start/defer/deny controls. Bind approval to the waiting task.
Classify mouse movement separately from click/key/scroll and acknowledge the
Start now interaction without ignoring later deliberate input. Report unknown
activity and provider/OS omissions instead of simulating readiness.

### 4 — prove Windows behavior and remove its replaced path

Run portable policy/client tests, formatting, native contracts and ARM64/x64
publishes. Then use an exact clean candidate on an exclusively claimed Windows
target with independent fixture effects and native input observations. Use a
separately identified test browser and follow credential, usage-note, process,
registration, claim and power cleanup requirements.

Test normal ongoing user input, native clicks on the notice, accidental mouse
motion, deliberate takeover, fixed cooldown, deferral, concurrent clients,
Settings closure, provider failure and restart. Distinguish virtual/synthetic
input evidence from physical hardware and qualify only the actual route tested.
Delete the replaced Windows policy and compatibility plumbing after its new
path passes; do not retain it solely while awaiting Mac/Linux adoption.

### 5 — converge macOS and Linux, then retire legacy support

After Windows/reference/client acceptance, adapt macOS and then Linux to the
same permissions and handoff engine. Reuse native peer identity and OS providers.
Temporary disabled integrations are acceptable and must be visible in capability
and build status. Each platform needs its own input, focus, permission, lifecycle
and package acceptance before claiming support.

Remove each platform's old permission/admission path at its cutover. Once all
three implement the common contract and their declared native/package gates
pass, remove remaining legacy mode switches, old protocol mappings and tests
that exist only to sustain the retired experience. Update the owning topics
with deletion/accounting rather than leaving an indefinite compatibility layer.
Unrelated future device/physical coverage is not a reason to retain a shim once
its declared migration gates pass.

## Validation

| Scenario | Required oracle |
| --- | --- |
| Desktop Ask first, Browser Automatic | Browser fixture effects complete while Desktop stays undispatched awaiting its own approval |
| All nine surface-mode combinations | Off is quiet, Ask needs explicit task approval, Automatic obeys handoff; no cross-surface permission inheritance |
| Full Browser capability | Supported ordinary, CDP/eval and streamed effects share one mode and exact profiles; no extra scripts checkbox |
| Input during countdown | Finishing typing/moving does not reset the deadline; activation still rechecks authority/resources/safety |
| Start now | The human click/key choosing it is acknowledged; later deliberate input still yields |
| Movement versus deliberate takeover | Mouse motion leaves ownership/effects intact; click/key/scroll retires ownership promptly |
| Fixed cooldown | Same live intent waits 60 seconds and reannounces despite continued normal activity; no action replay |
| Timed/global/surface/manual pause | Correct scope and deadline; unrelated surfaces proceed; global override wins; no notification while manually paused |
| Multiple or duplicate clients | Bounded fair waiting, one relevant notice, no deferral bypass or orphaned owner |
| Off, deny, expiry and cancellation | No provider dispatch or surprise reapproval; correct terminal outcome, unchanged consent ceiling |
| Compound browser/native operation | Required Desktop policy is checked before native effect; no implicit fallback or partial resource hold |
| Loss, restart and late completion | No restored owner/stream/action; truthful uncertain effects and explicitly reviewed consent migration |
| Legacy/unsupported integration | Typed unsupported result or explicit legacy route; no silent downgrade or false parity claim |

## Result and next step

**Current:** the pure TypeScript surface-policy engine and its private Node
host inlet implement independent modes, task approval, original consent
ceilings, atomic resources, handoff, pauses, cooldown and ownership fencing.
Nineteen deterministic and real-process tests cover all nine mode combinations
and interrupted effects. This checkpoint does not change installed behavior:
Windows still needs to adopt the engine, operator UI and client contract, then
pass new native/package acceptance before the requested broad review.

The approved autonomous sequence is Windows/shared/reference implementation and
acceptance, one broad Opus 5.5 High review through the work-account router pool
with weekly-pace routing and bypass permissions, findings correction, then
macOS and Linux adoption with their own acceptance. Reviewer routing evidence
and appliance details remain private. Do not substitute a different model or
account when the requested route is unavailable.

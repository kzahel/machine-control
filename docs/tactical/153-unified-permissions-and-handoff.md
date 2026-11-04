# Unified permissions and predictable handoff

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[shared resident core](../../topics/shared-resident-core.md),
[browser profiles](../../topics/browser-profiles.md).

Status: **Windows candidate conformance passed; broad review pending,
then macOS and Linux adoption**.

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
semantics. Do not silently run a legacy policy behind a new-mode UI. Delivery
proceeds through Windows, macOS and Linux; publication and personal installation
remain outside this workstream.
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
Twenty-five deterministic and real-process tests cover all nine mode combinations
and interrupted effects. This checkpoint does not change installed behavior:
Windows now delegates admission to that engine and exposes the v2 operator UI
and Python channel. Its former C# queue/grant-request policy was removed.
Native contracts use the real shared process; the fixture clock host is not
packaged. The Windows candidate now passes the bounded qualification below;
the requested broad review precedes macOS/Linux adoption.

The approved autonomous sequence is Windows/shared/reference implementation and
acceptance, one broad Opus 5.5 High review through the work-account router pool
with weekly-pace routing and bypass permissions, findings correction, then
macOS and Linux adoption with their own acceptance. Reviewer routing evidence
and appliance details remain private. Do not substitute a different model or
account when the requested route is unavailable.

### Implementation choices under qualification

- Private host and public resident admission both negotiate v2. Incompatible
  resident clients refuse explicitly; extension messaging remains v1.
- Unrestricted Browser/CDP/eval work conservatively affects the human browser
  context. A narrowed server-checked observation set may skip the warning.
  Disruptive tasks share a human-input reservation; independent background
  profile work remains available while Desktop is Off, paused or awaiting Ask.
- Consent is never restored across resident restart. Form preferences remember
  the selected Ask/Automatic mode and exact profiles without arming.
- Native admission keeps channel identities, safety facts and event-generation
  projections. It does not retain a second queue or task-approval engine.
- Native `observe`/`control` and `browser`/`devtools` strings remain internal
  provider capability mappings. The v2 operator and public admission contract
  expose Desktop and full Browser, rather than separate script consent.
- The separate borrowed-claim outer recovery protocol stays explicitly v1
  during migration. It cannot silently satisfy v2 resident requests.

- Deferral and deliberate-takeover cooldown bind the shared human-input resource
  so switching clients or surfaces cannot bypass them. Background Browser work
  remains independent. Prepared locked routes skip an invisible notice using a
  trusted native visibility fact, while retaining reservations and Ask approval.
- Operator state limits detailed requests to sixteen and prioritizes actionable
  notices; total counts remain complete. The private engine retains its bounded
  full queue. Native physical-HID input remains a separate qualification from
  explicit policy facts and real injected-hook observations.

### Local validation checkpoint

**Current:** strict runtime checks and all 73 runtime tests pass. Windows native
contract tests run the real Node process through the C# inherited IPC client;
the mode matrix, live channel ownership, native safety, activity classification,
audit, bounded work and late-result checks pass. Windows runtime formatting
verification and self-contained ARM64/x64 publishes pass. These local checks
are source/build and fixture evidence; the separate live Windows qualification
is recorded below.

- Legacy Windows operator `arm`/target-wide `decision` commands and the old C#
  policy-only test project are removed. The v2 Python API/CLI uses surfaces;
  old SDK scope arguments fail explicitly rather than silently widening a
  narrow task. Native provider scope strings remain an internal mapping.
- Start now acknowledges the native input watermark and tolerates the countdown
  boundary. A click already classified as takeover can lead only to a fresh
  owner; manual/protected pauses and missing approval remain blocking.
- Qualification reproduced a retained stdio transport stall with a single
  worker: an idle anonymous-pipe read prevented request/reply progress. The
  native owner proxy and extension native host now use dedicated I/O threads,
  retaining their existing framing and ownership. A separate-process contract
  exchanges ten frames with one worker and checks both caller and resident EOF;
  it fails with the previous pool-based transport and passes with the new one.
  Portable native contracts, formatting and ARM64/x64 publishes pass. The
  subsequent clean candidate qualification is recorded below.
- Packaged Settings inspection exposed a transient status-poll collision with
  operator/update work. Treating that collision as a lost resident unmounted
  the form and discarded unarmed profile choices. Windows now returns explicit
  pending metadata without queueing; the UI retains its form until the next
  poll. A rendered regression reproduces the lost choice in the previous UI
  and passes with the correction, while real transport failure still removes
  control widgets. Native visual inspection also found a clipped pause label;
  the notice now uses wider, evenly spaced button columns.

### Windows candidate qualification

**Current (2026-11-04):** clean product source `9721b92` passes native desktop
and unlock contracts, all 25 native handoff checks, four Windows Rust operator
tests and the production Tauri build. The full browser/Settings actor passes
all 44 checks, including independent native/page effects, two stable regular
profiles in one browser, exact selection, supported CDP/eval/upload/capture,
live expiry, reconnect fencing, actual policy-child death, Settings closure,
window recreation and fresh consent after app restart. Its scratch profiles,
temporary registration and owned processes are cleaned by the actor; controller
staging, claim and power cleanup remain separate work.

The native handoff actor includes the diagnostic-only `0714e2e` change. An
earlier rehearsal missed the fresh warning after cooldown; aggregate status
omitted its terminal intent. The unchanged-deadline diagnostic rerun passes,
but that earlier failure has no established cause and remains a review
question. Visual inspection of the corrected notice confirms legible button
labels and preserved foreground focus on the owned fixture.

These are unsigned ARM64 VM results with a separately identified, sandboxed
Chromium and software rendering. ARM64/x64 runtime publishes pass; this does
not establish live x64, physical-HID, signed installer or protected-transition
qualification. Physical takeover facts in the handoff fixture are supplied
in process; native hooks separately observe real injected keyboard/mouse
events. Existing protected guards and their contract checks remain in place.

The rendered Settings regression proves that pending metadata preserves an
unarmed profile edit while terminal transport failure removes the controls.
This is UI contract evidence, complemented by the actual Windows lifecycle
run; it is not an OS or authorization oracle by itself. Broad review and any
resulting corrections are the next Windows gate.

### Broad review and corrections

**Current (2026-11-04):** the requested single independent broad review is
complete. It found a late-takeover lifetime defect and a locked preparation
quiet-guard bypass when a background Browser owner was active. The corrections
also cover unknown human-input observation, scoped pause origins, common
operation narrowing, admission audit transitions, exact profile notices,
nonmodal notice errors and current agent instructions.

- `1fdaba4` reproduces and corrects resumed waiting after the initial wait
  expires. A fresh cooldown/notice/offer period stays under the task ceiling;
  each SDK wait pins the new server period rather than the original submission.
- `8f9dbfd` counts active Desktop ownership for protected quiet eligibility,
  blocks the shared disruptive-input resource on unknown observation, preserves
  unrelated background Browser work, keeps global/surface pause origins,
  enforces narrowed operations and journals closed transition metadata with
  hashed correlations. Lightweight native queries omit task text/full views.
- `f4188d3` names selected profiles in native/Settings tasks, keeps notice
  errors inline and records closed native presentation exception classes. It
  replaces obsolete agent grant instructions and wires rendered UI acceptance
  into the common check entry point and CI.
- `618718f` adds explicit ordinary owner renewal under the same consent and
  owner/generation fence. Prepared Windows owners refuse renewal until their
  independent guardian can acknowledge it. Heartbeats and pauses do not renew.
- `bb0f5e8` migrates covered/enrolled actors to v2 and reuses the real-profile
  actor for locked Browser effects, streams, Pause/Resume and Stop. The native
  Ask fixture inspects both profile names before allowing its exact task.
- `8a5e618` exposes independent global pause controls and distinct scope labels.
  Global Resume retains an independent surface pause.
- `3da11a9` keeps explicit ordinary renewal responsive during a held provider
  action. Its transport regression fails with the action-busy guard and passes
  when renewal is allowed to retain the same owner independently.

Strict TypeScript, all 79 shared runtime tests, portable repository checks,
rendered UI checks, native contracts and ARM64/x64 publishes pass. The clean
`8a5e618` candidate passes native contracts and 26 actual Windows handoff
checks, including late takeover, and four native Rust operator tests. Full
Browser/Settings and protected-transition qualification are still in progress
at this checkpoint. The subsequent renewal correction requires final clean
candidate qualification.
The earlier missing cooldown warning remains unexplained; the diagnostic code
improves future failure evidence and is not an established fix for that miss.

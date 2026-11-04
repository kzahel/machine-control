# Unified permissions and predictable handoff

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[shared resident core](../../topics/shared-resident-core.md),
[browser profiles](../../topics/browser-profiles.md).

Status: **Windows broad review complete; final locked/protected corrections
under qualification before macOS and Linux adoption**.

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

### Post-review transport and protected-surface corrections

**Current (2026-11-04):** `13447a8` corrects a synchronous writer deadlock:
a native safety query could time out acquiring a permit that an asynchronous
write completion would release only after the occupied managed pool ran its
continuation. A one-worker, delayed-reader process fixture fails against the
old semaphore path and passes with the bounded owned-writer queue. The clean
candidate passes actual Windows formatting, native/unlock contracts, 26 native
handoff checks, four Rust operator tests, the production Tauri build and all
48 Browser/Settings checks, including intentional policy-child termination.
Actor cleanup is verified. The earlier candidate's pre-kill child loss matched
the write-timeout failure class; no crash dump establishes it as the sole cause.

`94db085` separates Desktop consent revision from Browser configuration and
publishes Browser-while-locked readiness changes without globally stopping both
surfaces. Native regressions fail against the previous implementation and pass
with the correction. The closed audit vocabulary now includes relock pending.
Its final ordinary, locked-Browser and enrolled-Desktop qualification remains
in progress; source/build success alone does not qualify protected transitions.

The separate test-only `98601dd` enrolled actor requires independent native
counter effects and real captured PNG pixels after unlock, checks that Browser
configuration preserves covered Desktop ownership, and verifies relock on both
owner completion and Stop. Its provenance is separate from product source
`94db085`; no product files changed between those revisions. Helper staging
must restore original executable bytes, ACLs, service state and presentation
preferences without copying or replaying the credential vault.

The clean `94db085` candidate passes the complete 48-check ordinary
Browser/Settings run with cleanup. Its locked-Browser actor then independently
observes lock but refuses a fresh owner because exact selection was cleared.
The native audit records `console_session_changed` during the transition.
A same-logon unavailable/not-yet-locked native fixture reproduces consent loss:
input-desktop and WTS observations need not settle in the same poll. The
correction retains consent under exact logon identity while readiness continues
to deny effects; a different or unavailable logon identity still revokes it.
The regression fails before and passes after the correction. Full native
contracts and ARM64/x64 publishes pass; fresh candidate qualification follows.

### Companion verification before Settings startup

**Current (2026-11-04):** `0779cac` passes actual Windows formatting,
native/unlock contracts, 26 handoff checks, four Rust operator tests and the
production build. Its ordinary actor passes 42 checks, including policy-child
termination and Off restart, then times out starting Settings. Actor cleanup
is verified. The protected helper and enrollment remain unchanged; this is
not full ordinary or protected acceptance.

Settings had a separate three-second `uac-resolve` cutoff before its longer
resident handshake. That command checks the protected helper and hashes both
executables. A limited interactive diagnostic on the same ARM64 VM measures
successful verification at 7.80 seconds, followed by 1.48 and 1.40 seconds;
this is three bounded samples, not a performance benchmark. The failed app
reported unavailable about three seconds after startup. The timing and source
identify a real premature cutoff; the earlier generic diagnostic does not
independently identify every possible startup failure.

Companion verification now has a separate finite fifteen-second budget.
Cancellation and timeout kill and reap the exact owned resolver. A four-second
process fixture fails with the old budget and passes with the new one; bounded
cancellation/timeout tests also pass. Closed verification, launch and job-setup
codes retain stage evidence without recording raw errors or paths. The native
Windows gate now includes these process tests alongside its operator tests.
Fresh product qualification is required before proceeding to locked/covered
acceptance or adopting the model on Mac.

The expired test window was not extended in place: after the failed actor's
verified cleanup, the controller restored Off and released its claim, then
acquired a fresh bounded scope on the same appliance. No VM was created.

### Bound verification I/O as well as its process lifetime

**Current (2026-11-04):** `030f3d2` passes native/unlock contracts, 26 handoff
checks, all seven Windows process/operator tests and the production build.
Its ordinary actor again reaches 42 checks, then times out at Settings startup;
cleanup succeeds. The new diagnostic identifies `companion.resolve_timeout`
at the fifteen-second verification cutoff. The earlier timing correction alone
therefore does not establish successful Settings startup.

A standalone Rust process comparison, with and without concurrent stdout drain,
finishes both variants; it does not reproduce a pipe deadlock. Observation of
the actual app's resolver instead shows continuing image reads and a page-in
wait: about 140 MB has been read at fifteen seconds. The two executable images
are approximately 172 MB each and differ in length by 20,480 bytes. Their size
already proves that the old helper cannot be this candidate; hashing both full
images unnecessarily competes with GUI startup for disk reads.

The native identity matcher now rejects unequal lengths before reading image
contents and uses buffered sequential reads for the full SHA-256 comparison
when lengths match. It still requires complete equality before selecting the
installed companion, after the existing protected-path verification. A metadata-
only stream regression fails with the previous hashing algorithm and passes
with the cheap rejection. Identical, same-size-but-different and truncated
file fixtures pass. Full native contracts, format verification and ARM64/x64
publishes pass. The resolver's fifteen-second bound remains unchanged.
Fresh ordinary qualification and a matching-installed-helper startup check
are required; neither the standalone probe nor source checks qualify that
composed startup. No protected helper or enrollment has been changed yet.

The clean `670d235` product passes the native gates, all seven Rust tests and
production build. Its first ordinary actor stops after 37 checks when the owned
test Chromium does not exit within fifteen seconds of its direct fixture
`Browser.close`; actor cleanup succeeds. This occurs before Settings startup
and does not qualify or disprove the identity-reader correction.

The fixture now closes its own control socket, requests termination of its
exact owned browser if graceful shutdown exceeds the bound, and records both
that request and independently observed process exit. This phase's oracle is
provider disconnection and stale-reference fencing, not graceful browser exit.
A failed termination remains a failed run, and no page action is replayed.
Real-child tests distinguish clean exit, forced recovery and cleanup failure.
The subsequent run uses the same product bytes with separately pinned actor
source; this harness correction is not a product acceptance claim.

**Current, subsequent same-product run:** `670d235` passes all 48 ordinary
Browser/Settings checks with cleanup using actor `6911df3`. All three recorded
fixture-browser shutdowns complete within their grace windows without a forced
termination request. Settings starts and survives the required close/recreate/
restart sequence, qualifying the cheap identity-mismatch correction in that
composition.

Locked Browser then passes 32 checks: real named-profile effects, capture,
ordinary/root/streamed CDP, Pause, fresh Resume ownership and Stop all occur
while Windows remains locked. Its next negative assertion fails because an
unowned Desktop snapshot is correctly refused but reports `desktop_unavailable`
instead of `surface_disabled`. Cleanup succeeds. No protected staging occurs.
The native facade checked physical readiness before ordinary access for Desktop
operations, unlike its Browser path. It now checks access first and retains the
worker's final authorization before effects. Off reports disabled; enabled
callers receive task-negotiation guidance before availability waits. Capability
metadata also names surface/task ownership instead of retired target-wide
grants. Native contracts, formatting and ARM64/x64 publishes pass; fresh live
qualification must establish the corrected facade composition.

**Current, protected qualification checkpoint:** `97fccfc` passes the clean
Windows native gates, seven Rust process/operator checks, all 48 ordinary
Browser/Settings checks and all 35 locked Browser checks, with actor cleanup.
A matching installed companion also passes seven startup checks after an actual
cold boot. Enrolled Desktop then fails before credential delivery during
protected preparation. The service reports cancellation with `credentialRead:
false` and `delivery: not_sent`; the journal's first ownership interruption is
`relock_pending`, followed by the stale-session refusal. This does not establish
what ended the guardian. The original helper, ACLs, service and two protected
preferences are restored and verified. Enrollment is unchanged.

A bounded diagnostic now preserves the guardian's first implementation-owned
ending cause alongside its independently observed relock status. Unknown or
crashed exit codes cannot acknowledge cleanup. Refusal evidence includes only
that closed reason and exit code, with no input or credential values. This
instrumentation does not qualify protected effects; the Windows gate remains
open until preparation, native effect, capture and owner/Stop relock pass.
Portable contracts, formatting and ARM64/x64 publishes pass for the diagnostic.

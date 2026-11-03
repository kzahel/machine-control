# Access admission and pause

Topic: `access-admission-and-pause`

Status: **unified Desktop/Browser permissions and handoff design agreed;
Windows implementation next, before Mac/Linux adoption**. Existing admission
implementations and their bounded acceptance remain current evidence below;
they do not implement or qualify the complete new experience.

## Scope and motivation

**Decision:** standing authorization, temporary availability and exclusive
control have separate lifetimes. An operator choosing **Until I turn it off**
should be able to leave a computer useful to authorized agents. The operator
needs a predictable warning before takeover, a deliberate way to defer it,
and reliable return of control. An accidental mouse movement must not interrupt
an agent. The original Windows busy/refusal loop and inconsistent platform
behavior motivate settling this experience before further platform migration.

The same admission vocabulary should apply to physical desktops, resident VM
control and explicitly authorized outer recovery. Their resource requirements
and human-interference risks remain different. This topic owns admission,
waiting, interruption, resume and their composition. It does not replace
[caller authorization](caller-authorization.md),
[target-use claims](target-use-claims.md),
[inner-first routing](inner-first-routing.md) or platform protected-control
policy.

## Unified permissions and handoff contract

**Decision (2026-11-03):** configure **Desktop** and **Browser** independently
with the same three modes. This supersedes the earlier idle-first default,
movement-as-takeover rule and requirement to preserve legacy desktop behavior
throughout migration. It is an agreed destination, not current product support.
[Tactical 153](../docs/tactical/153-unified-permissions-and-handoff.md) owns the
Windows/shared-core/reference-target implementation and acceptance gates.

| Mode, per surface | Agent request | Operator interaction |
| --- | --- | --- |
| Off | Refuse with an explicit disabled result; no approval or takeover notifications | Only an operator can re-enable the surface |
| Ask first | Keep one live request awaiting approval for its task/session | Allow that task, defer, or deny; approval is not requested for every click |
| Automatic | Authorize within the operator's selected surface, profiles and lifetime | Announce before disruptive use, then start unless deferred; no approval click required |

**Decision:** Automatic is the normal operating choice when the operator enables
access, matching the always-armed workflow. Initial setup does not itself grant
access. Ask first is an explicit alternative, and Off is genuinely quiet.
Remember an explicit operator mode choice without silently replacing Ask first
with Automatic when access is re-enabled. For example,
**Desktop: Ask first; Browser: Automatic** is a supported combination.
Neither surface inherits the other's approval, pause or automatic permission.
Global Pause and Stop override both; surface-specific controls affect only their
surface. Off need not disconnect an extension: bounded setup/status discovery
can remain available, without querying page contents or executing browser work.
Unknown activity/readiness or another owner's reservation remains a separate
eligibility condition, never permission supplied by a countdown.

**Decision:** Browser includes the complete **supported** browser automation
surface: tabs, page interaction, capture, raw CDP, page JavaScript evaluation
and streamed sessions. There is no additional user-facing scripts/DevTools
permission tier. Existing `browser`/`devtools` flags are current implementation
and migration details, not two product permissions to preserve indefinitely.
Provider omissions, restricted CDP commands, OS permissions and native protected
control retain their real boundaries. Browser approval names exact enabled
installation IDs under the [profile contract](browser-profiles.md); a new profile
never silently joins existing consent.

**Decision:** capabilities, selected profiles, access mode, consent lifetime,
temporary availability and active ownership are distinct. Checking capabilities
is not arming, and remembering form choices is not restoring authority. Offer
an explicit finite lifetime or Until turned off, with visible current armed/
paused/expired status. A timed pause, heartbeat or retry never extends consent.
Ask first approval applies to the admitted task/owner, rather than making an
unrelated waiting task automatically eligible under a target-wide grant.
A still-authorized task can resume through a fresh handoff without another
approval click; it receives a new active session under the original consent
ceiling. A different task cannot inherit that approval.

**Decision:** a request can be submitted while its surface is temporarily busy
or paused and remains connection-owned under bounded liveness/usefulness limits.
The CLI/SDK maintains the wait; an LLM should not repeatedly submit actions or
ask for approval. Off and denial are explicit refusals. Busy, deferred and
paused are waiting states, not misleading permission failures. Deduplicate
requests and coalesce notices for conflicting work; changing clients or request
IDs cannot bypass an operator deferral.

### Automatic handoff and taking control back

**Decision:** for ordinary unlocked desktop use, the default is a visible,
non-focus-stealing **10-second announcement**, configurable by the operator.
Show the task reason, truthful caller assurance and remaining countdown.
Ordinary typing and pointer activity during the countdown let the person finish
their work; they do not reset it or reinstate a hidden 30-second quiet prerequisite.
At the deadline, recheck permission, reservation, session readiness and safety,
then activate automatically. The notice must not steal the input it warns about.

Provide **Start now**, **Pause 30 seconds**, **Pause 1 minute**,
**Pause until Resume**, and a distinct way to deny/cancel the request. Stop
access remains separately available. Start now acknowledges the current operator
interaction, including the click used to choose it; that interaction must not
immediately interrupt the new owner. A later deliberate input still can.
Ask first combines approval and starting into one coherent interaction instead
of requiring a second approval for the same task.

**Decision:** mouse movement alone never counts as taking control back.
Non-agent keyboard input, mouse clicks and scrolling are deliberate takeover
signals for ordinary desktop control. After activation, yield promptly on such
input, retire the old session/references and give the operator control. Preserve
valid consent and the live waiting intent. Do not undo or replay uncertain
application effects; obtain fresh ownership and observe again before acting.
The emergency Stop shortcut remains immediate.

After deliberate takeover, wait a fixed **60-second cooldown**, then issue a
fresh announcement. Normal activity during that cooldown does not continually
restart it. Multiple agents cannot generate multiple competing countdowns.
Timed Pause instead uses its chosen deadline, and Pause until Resume has no
automatic retry. Returning from a pause uses a fresh handoff, not silent reuse
of an old active session. Denial/cancellation is terminal for that request;
Stop turns affected surfaces Off and cancels their work.

### Browser independence and compound operations

**Decision:** background browser work that preserves the person's desktop and
does not contend with their browser task must not reserve the entire desktop
or wait for unrelated desktop quiet. Work affecting a browser context the
person is using needs an appropriate browser handoff under Browser's mode.
Per-profile/tab contention and debugger reservations remain explicit.

An operation requiring native desktop input or an OS dialog must also satisfy
Desktop's mode before that part dispatches. Browser Automatic cannot authorize
a desktop fallback when Desktop is Ask first or Off. Classify actual route and
interference, not whether a call happens to use CDP. Acquire the required
resources together without holding a partial reservation during approval or
pause. If the needed route is unavailable, report it without replaying through
another surface.

**Open:** finalize the operation/impact table for foreground changes, browser
versus OS dialogs, and other compound effects. Specify touch/pen/remote-human
intent classification, persistence of automatic authorization across restart,
and task-lifetime details. Persisted preferences must never resurrect an old
owner, stream or queued action. Until an explicit migration policy is tested,
legacy consent must not be reinterpreted as broader unified Browser authority.
Protected/covered input changes require their own native safety evidence;
independent cover, lock, credential and relock guards remain authoritative.

## Current foundation

**Current, source-reviewed gaps (2026-11-03):** Windows can return
`access_paused` before declaring that a call needs a control session, while the
[Python handoff](../client/control_session.py) queues only an explicit
`control_session_required` refusal. Its [activity policy](../src/MachineControl.Windows/DesktopActivityPolicy.cs)
requires 30 seconds of quiet before the normal 10-second announcement, and
[Start now](../src/MachineControl.Windows/AccessAdmission.cs) does not acknowledge
recent physical input. [Native notices](../src/MachineControl.Windows/DesktopNativePresentation.cs)
lack the visible countdown/short-pause choices. A missing grant can still trigger
[approval](../src/MachineControl.Windows/DesktopGrants.cs), so current unarmed
and quiet Off are not distinct. These findings explain possible failure paths;
they do not identify or reproduce the user's historical installed build. The
existing tests and bounded browser cutover do not qualify the new handoff model.


**Current, unreleased Mac source:** operational grant retirement retains saved
operator consent by default; Stop and verified console replacement invalidate
it explicitly. A partial same-console probe never proves replacement. Locked
browser scopes can restore independently while protected desktop readiness is
unavailable; missing saved scopes report temporary unavailability. An upgrade
retires the restricted grant and issues fresh generations, never reviving queued
work. A fault fences desktop dispatch until fresh helper cleanup/recovery;
operator Pause remains independent of automatic root recovery.
[Tactical 138](../docs/tactical/138-remote-arming-recovery.md) owns the slice.

**Current, unreleased Windows source and focused x64 VM evidence:**
[Tactical 103](../docs/tactical/103-windows-activity-pause.md) adds a Default
desktop activity monitor and composed 30-second quiet policy. Input injection
flags distinguish agent input from ordinary takeover; conservative session
idle is used for locked admission rather than as a human-input classifier.
Covered takeover retains consent; observed relock plus quiet permits a fresh
session, while owner-unlocked local use retains its independent pause.
No existing action or session is restored. Native hooks, real quiet time and
ordinary/covered virtual-keyboard takeover now have focused VM evidence.
Physical hardware, owner-unlocked local-use, ARM64 live and signed installed
qualification remain separate; local-use policy has deterministic coverage.

**Decision:** task-end cleanup may request lock only for a task that started
locked, using an immutable native observation at ownership acceptance. An
unlocked-origin task must finish without locking; a later user/idle lock stays
in place and cannot supply temporary-unlock authority to that original task.
Acquire a new locked-origin owner for covered work. [Tactical 102](../docs/tactical/102-windows-covered-control.md)
implements this fence on Windows and corrects the macOS legacy lease path.

**Current, unreleased Windows native integration:**
[Tactical 101](../docs/tactical/101-windows-desktop-locked-use.md) admits an
explicitly prepared, finite observation/control owner while the exact local
console is locked. Ordinary dispatch still refuses until password unlock is
independently confirmed. An independent SYSTEM guardian owns relock, and a
relock barrier fences new work after authority loss. That historical candidate
used a temporarily visible console. [Tactical 102](../docs/tactical/102-windows-covered-control.md)
adds opaque one-display VM presentation and native task-origin fencing;
physical takeover and signed installed qualification remain distinct gates.

**Current:** [Tactical 075](../docs/tactical/075-admission-contract-and-arbiter.md)
records the common contract/arbiter checks and Windows builds.
[Tactical 076](../docs/tactical/076-resident-pause-enforcement.md) owns resident
pause enforcement and its remaining native/platform gates. [Tactical 078](../docs/tactical/078-live-admission-channels.md) records live
desktop owner channels. [Tactical 079](../docs/tactical/079-consent-and-control-notices.md)
records Mac persistence and notices, and
[Tactical 081](../docs/tactical/081-macos-admission-physical-acceptance.md)
qualifies their bounded physical behavior.
[Tactical 082](../docs/tactical/082-queued-target-claims.md) adds live exact-target
claim waiting through explicit v1 negotiation. Claim v0 still advertises no queue.

**Current, source and fixture evidence:**
[Tactical 095](../docs/tactical/095-windows-required-owner-session.md) makes
connection ownership mandatory for ordinary Windows desktop-product native and
browser dispatch, including when the desktop is idle. Common CLI calls can
negotiate a short owner session; `control stream` retains one across related
actions. Headless/appliance profiles keep their existing authority.
[Tactical 096](../docs/tactical/096-windows-owner-session-acceptance.md) now records
focused staged Windows ARM64 native/browser effects, contention, disconnect,
heartbeat expiry and real operator Pause/Stop. Complete signed release
acceptance remains open; this is not authenticated exact-claim binding.

**Current, source-reviewed:** these are separate mechanisms today:

| Mechanism | Implemented behavior | Gap for this feature |
| --- | --- | --- |
| VM target-use claim | Exclusive exact-resource lease; legacy fail-fast v0 and opt-in connection-owned v1 waiting, offers and expiry fencing | Cooperative attribution; queued workspaces and shared outer reservation remain open |
| Mac approval request | One pending native request; default 120-second approval timeout, bounded to 5–600 seconds; a second request receives `approval_pending` | Prompt timeout is not queue liveness or a resumable pause |
| Mac ordinary access | Target-wide same-user scopes; timed or until-stopped local consent derives fresh grants across the same console/boot after permission checks | Caller isolation remains open; restored consent never restores a queue or active owner |
| Mac covered control | Connection-owned finite session, five-second heartbeat, covers and watchdog relock; source retains consent and composes physical/local-use pause | Revised queue-driven takeover/quiet resumption still needs native lock qualification |

The sources are the [claim authority](../providers/claims/claims.py),
[Mac grant broker](../platforms/macos/resident/Sources/macui/Grants.swift) and
[covered-control owner](../platforms/macos/resident/Sources/macui/LockedUse.swift).
The common [claim capability validator](../client/machine_control.py) currently
requires the v0 schema and `queueing: false`. Adding a queue requires an explicit
compatibility design, not changing that flag alone.

**Current, bounded live-tested:** Mac idle-lock, successive covered tasks and
clean task expiry can preserve ordinary access. Physical takeover/recovery has
operator confirmation and a scripted timing caveat. The
[Mac topic](macos-locked-use.md) and
[Tactical 070](../docs/tactical/070-macos-locked-access-retention.md) own those
limits. They do not establish the proposed grant-preserving pause behavior.

## Independent lifetimes

**Decision:** the public model must distinguish these facts:

| Fact | Meaning | What ending it does |
| --- | --- | --- |
| Operator consent or integration trust | Local choice permitting a defined kind of access | Revokes associated authority; cannot be restored by an agent |
| Caller grant | Authority for a caller, scopes and applicable target/session generations | Prevents further governed operations; timed expiry keeps running during pauses |
| Availability | Whether the resource can be used now; a set of blocking reasons | Pause blocks use while leaving otherwise valid authorization intact |
| Waiting request | Live intent to obtain access before a caller deadline | Cancellation/expiry removes the intent, not standing consent |
| Target-use claim | Finite exclusive reservation of an exact resource | Releases coordination ownership, not permission or VM lifecycle ownership |
| Active control session | Finite, renewable ownership of actual desktop control | Fences old actions and performs route-specific cleanup/relock |

Persistent consent is not an infinite protected session. With authenticated
integration grants, consent may survive a restart while a dead connection's
delegation does not. Fresh callers must authenticate and obtain fresh authority
under the remaining consent. Existing target-wide grants must not silently
become authenticated or acquire broader scopes during migration.

**Proposal:** report these as independent projections in status, rather than
one overloaded `claimed` or `granted` flag. Include effective blocking reasons,
owner attribution/assurance, relevant deadlines, resume conditions and a
generation/revision for conditional operations and event recovery. Public
identifiers remain selectors, never bearer credentials.

## Pause, physical takeover and resume

**Decision:** distinguish four operator actions:

- **Pause:** block access temporarily; preserve valid consent and grants.
- **Resume:** clear the operator pause; other blocking reasons still apply.
- **Cancel request / end task:** stop that waiting request or active session.
- **Stop / Turn off access:** revoke access and cancel affected work. Trusted
  automatic grants remain suspended until the operator re-enables them.

**Proposal:** availability is the intersection of independent conditions:
manual pause, deliberate takeover/cooldown, optional idle-first policy,
operator deferral, resource contention, authorization validity, session readiness
and safety faults. Apply reasons to their actual surface/resource. Clearing one
condition must not clear another. Agent-facing clients may cancel their own
work, but cannot clear operator pauses, re-enable access or acknowledge a
safety fault on the operator's behalf.

| Situation | Proposed behavior |
| --- | --- |
| Deliberate input during covered control, after native qualification | Fence dispatch immediately, end the finite session, request relock and retain covers until lock is independently observed; preserve valid ordinary authorization |
| Screen remains locked after takeover | Wait for verified physical quiet, then allow a fresh unattended session under remaining authorization |
| Owner unlocks after takeover to work | Stay paused while that local-use episode continues; become eligible after re-lock plus quiet, or explicit operator Resume |
| Initial authorized use of an unlocked desktop | Apply the selected surface mode and predictable announcement; ordinary activity does not indefinitely postpone Automatic |
| Manual pause until Resume | Stay paused across activity changes and clean task completion; no idle timer clears it |
| Manual timed pause | Clear only that reason at its deadline; do not extend timed authorization |
| Broken cover, uncertain lock state, helper failure or changed console identity | Relock/cleanup through the existing watchdog and refuse further control; retain a safety block or revoke affected session authority as appropriate |

**Proposal, later Mac covered qualification:** retain the existing awake,
open-lid Mac boundary. It needs a verified activity monitor while idle as well as while
covered. Unknown activity/lock readiness blocks automatic activation. Agent
synthetic input must not count as a human takeover or restart the quiet timer.
The new ordinary-control intent rules above require native fidelity evidence;
touch, remote human input and noisy devices need explicit classification. The root guardian's relock responsibility must not
depend on the queue or the desktop UI remaining alive.

Resumption creates a fresh control session and generations. The agent observes
the application again before acting; old element references, coordinates and
pending input cannot be blindly replayed. A pause can prevent undispatched
operations and invalidate sessions, but cannot undo an effect already delivered.
Report interrupted or uncertain in-flight effects honestly.

The shared desktop remains unavailable while relock/cover cleanup is pending.
Only independently observed safe completion permits the next activation; ending
an owner lease alone does not prove that the desktop is ready for another agent.

## Polite activation

**Decision:** the [unified handoff contract](#automatic-handoff-and-taking-control-back)
owns ordinary unlocked activation, countdown and cooldown defaults. Automatic
permission and considerate activation are separate; Ask first is an explicit
approval mode. Operator deferral affects the shared conflicting resource, so
another agent cannot issue an immediate replacement notice. Presentation belongs
to the native operator UI and remains independent of Settings and the agent.

An explicitly authorized, locked and prepared target can activate unattended
under Automatic or an already-approved task and its separate protected policy,
without demanding a locked-screen acknowledgement. Missing Ask first approval
still blocks activation.
Preserve covers, verified unlock/relock, task-origin fences and independent
watchdogs. The ordinary unlocked announcement rule does not relax these guards.

## Common admission and resource arbitration

**Decision:** Machine Control owns authoritative admission, exact-resource
arbitration and provider enforcement. YepAnywhere owns agent-session
coordination and may present waiting/paused state or suspend an agent's broader
work. Dotfiles remains private inventory, not the live arbiter. CLI and SDK
clients must work without a YA-specific queue.

**Proposal:** a waiting intent progresses through typed states such as
`waiting_for_approval`, `waiting_for_resource`, `waiting_for_user_idle`,
`announcing`, `offered` and `active`. An interrupted intent can report `paused`
while its former active session is terminal. Status must show simultaneous
blocking reasons even when one state is chosen for display. Denial and absolute
policy prohibition are terminal outcomes, distinct from temporary unavailability.

| Route | Resources to arbitrate | Host desktop consequence |
| --- | --- | --- |
| Physical target-native desktop | Exact physical desktop/session | Local human activity and shared-screen policy apply |
| VM resident control | Existing exact VM claim plus its resident desktop/session | No controller focus, pointer or keyboard reservation |
| Outer VM focus/input recovery | Existing exact VM claim plus controller desktop | All VMs and direct physical-host use contend for the same host desktop |
| Headless or capture-only outer route | Exact VM and any actually contended provider resource | Report actual impact; do not invent focus/input interference |

Aliases, workspaces and route names must resolve to the same exact private
resource where they overlap. A desktop queue must compose with the existing
target claim authority, not establish a competing VM lease. Holding two
different VM claims never authorizes simultaneous use of one host keyboard.

**Proposal:** for the first multi-resource slice, one controller authority
admits the complete required resource set atomically. It holds no partial host
desktop reservation while awaiting approval, quiet or another resource. An
already valid VM claim for ongoing work can remain held within its existing
limits; host desktop access is a separately bounded sub-reservation. Recheck
all resources, grants, routes and generations at activation. Cross-controller
transactions are an explicit later design gate, not an implied guarantee.

The queue is FIFO among eligible conflicting requests, with bounded entries
per admitted caller and no advantage from polling faster or duplicate requests.
Disjoint resources can proceed concurrently. A paused interrupted intent must
yield the shared desktop; the initial candidate is rejoining eligible work at
the tail rather than reserving priority forever. Existing VM lifecycle claims
and their cleanup duties remain separate. Exact fairness under repeated human
deferral and mixed resource sets needs fixture evidence before it is promised.

**Decision:** a claim, queue position or notice never overrides an absolute
outer-control prohibition. A possible future policy allowing a scoped recovery
request after notice must be explicit opt-in. Preserve resident-first routing,
disruptive classification, recovery reason, verified target/geometry and role
checks. Never silently escalate an ordinary request to outer control.

## Cancellation and clocks

**Decision (2026-10-29):** finite owner leases may renew under the original
authorization; timed approval never restarts, and Until I turn it off permits
continued authorized work until Stop or task/authority/safety termination.
Claim renewal and watchdog heartbeats alone extend no control deadline.
**Current, unreleased Mac source:** typed same-connection renewal pins the grant
and its monotonic ceiling and requires protected acknowledgements. Existing
owners are never reopened. [Tactical 144](../docs/tactical/144-renewable-control-owners.md)
owns source/contract validation and bounded packaged sustained VM acceptance;
older providers and legacy finite control keep their existing bounds.

**Proposal:** use separate clocks with separately observable expiry reasons.
The handoff defaults below are decided; other candidate timings still need
measurement. Each clock must report its own expiry reason.

| Clock | Candidate | Required semantics |
| --- | --- | --- |
| Waiting-request keepalive / lease | Heartbeat about every 10 seconds; expire after about 60 seconds | Remove dead waiters; retain authorization; expired entries cannot be resurrected |
| Caller usefulness deadline | Caller supplied, bounded by policy | Stop waiting even if heartbeats continue; do not perform a task after its deadline |
| Activation offer | About 15 seconds | Require a live, ready owner to accept; otherwise offer to the next eligible waiter |
| Optional idle-first / protected quiet interval | Existing platform policy; presently about 30 seconds | Does not gate the default unlocked Automatic handoff; uncertainty and protected readiness remain separate |
| Unlocked-screen notice | Default 10 seconds, operator configurable | Finishing input does not reset it; recheck authority, resources and safety at activation |
| Deliberate-takeover cooldown | Default 60 seconds | Fixed delay before a fresh announcement; unrelated normal input does not continually extend it |
| Approval timeout | Existing platform-specific bound | Lack of approval is separate from queue liveness |
| Active claim/session | Existing finite platform bounds initially | Continue heartbeat and hard expiry; standing consent cannot remove watchdog limits |
| Timed authorization and manual pause | Their own operator/caller deadlines | Pause never extends authority; clearing a pause is not a grant renewal |

The SDK/CLI owns heartbeats; an LLM need not issue a tool call every few seconds.
An owner-bound wait/poll operation may renew its waiting lease. Unrelated status
inspection must not keep abandoned work alive. Slow polling can observe expiry
and rejoin at the tail, but cannot recover an expired position. A single bounded
intent may remain live while awaiting a human decision; no heartbeat extends
the separate approval timeout or caller usefulness deadline.

Offer acceptance and acquisition form a generation-checked transition. Do not
create an orphan active claim merely because a request reaches the front.
Late acceptance, an old countdown callback or an old cancel must not affect a
new request/holder. Request submission, cancellation and release are idempotent
within the authenticated owner and generation; caller labels alone do not
establish ownership. Proposed terminal outcomes include `cancelled`,
`queue_lease_expired`, `wait_deadline_exceeded`, `activation_offer_expired`,
`authorization_expired` and `policy_denied`.

Canceling a pending intent withdraws its notice, offer and associated approval
request without revoking unrelated authorization. Stop, trust removal and grant
expiry invalidate every affected intent, offer and active session before new
dispatch. A late approval callback cannot revive canceled work. While the
operator pauses a resource, live waiters may remain pending under their own
leases/deadlines; pausing does not silently cancel them or keep them alive.

Within a runtime, use monotonic time for intervals. Define wall-clock handling
for persisted deadlines and refuse automatic use when validity is uncertain.
Restart discards queue positions, activation offers and active connections by
default. Persisted operator consent, manual pause and Stop state must be scoped
to the correct local identity and policy; never restore stale session authority.
Persistence format, logout behavior and crash recovery need explicit review
alongside [Tactical 071](../docs/tactical/071-desktop-caller-authorization.md).

## Enforcement and agent experience

**Decision:** pause gates governed computer use, including observations and
actions. Read-only control status, diagnostics, cancellation and Stop remain
available. It does not promise to freeze an entire agent or contain arbitrary
shell access under the same OS user.

**Proposal:** recheck effective availability and ownership at every relevant
provider dispatch, not just at queue entry. Cover semantic observation/action,
capture, keyboard/pointer, application/window operations, clipboard where
scoped, browser relay/CDP and already-open streaming connections. Invalidate
old subscriptions/handles or bind each message to the live generation so
relevant surface and global pauses fence existing streams as well as new calls.
A Desktop-only pause does not block independent Browser work, and Browser-only
pause does not block independent Desktop work. Compound routes satisfy all
required surfaces; no implicit alternate-route bypass is allowed.

Agents receive structured wait/paused status, remaining authorization,
retry/resume conditions and a cancellable bounded wait/event surface. They
should not repeatedly request approval or busy-poll actions. Event loss requires
status resynchronization; event ordering/generations cannot retarget stale work.
YA can use the same information for broader session pause and user messaging.

Audit request, admission, deferral, pause, offer, activation, expiry, cancellation,
resume and rejected stale dispatch transitions through the existing
[desktop audit boundary](desktop-audit-and-diagnostics.md). Keep private logs
minimal, with truthful assurance and outcome; public examples contain no real
infrastructure, grant material, screenshots or user activity contents.

## Delivery direction and open decisions

**Decision (2026-11-03):** implement the new permission/handoff policy once in
the TypeScript [shared resident core](shared-resident-core.md), alongside the
reference target and synthetic clients, and adopt it on Windows first. Stabilize
that experience before macOS, then Linux. Retain Python for the CLI/client and
native languages for authentication, input observation/effects, presentation
and protected watchdogs; moving client implementation languages is unnecessary.

The user explicitly accepts breaking or temporarily disabling Mac integration
while this model is developed. The same migration allowance applies to bringing
Linux forward. Older clients, permission flags, grants and platform behavior
are not permanent compatibility requirements. Version negotiation must reject
unsupported semantics clearly rather than discard fields or widen authority.
Do not implement the new engine independently in Swift, C# or Python to keep
old integrations superficially working.

A legacy mode is optional when inexpensive and useful. Isolate it behind an
explicit route/build or capability boundary, label it legacy, and keep it out
of new-model acceptance. Never silently downgrade a failed new-model request.
Remove each platform's replaced policy as that platform cuts over; remove the
remaining shim/flags/legacy-only tests after migrated Windows, macOS and Linux
pass the common corpus and their declared native/package gates. The migration
plan must identify the owner and exit condition of every temporary bridge.
Compatibility is a temporary delivery tool, not a second long-term product.

[Tactical 153](../docs/tactical/153-unified-permissions-and-handoff.md) is the next
bounded implementation plan. Older tacticals remain execution history. The
new rules do not broaden outer-control permission or replace target-native
providers, target-use claims, caller authentication or protected safety guards.
Repository/candidate integration may temporarily be unsupported; this decision
does not replace a personal installation or authorize publication by itself.

**Open:** authenticated waiting-client admission, hardware/remote activity
fidelity, fairness, in-flight cancellation, precise foreground/compound-route
impact, persisted automatic consent and distributed multi-resource authority.
Native evidence must qualify each advertised route; synthetic success alone
cannot establish focus, HID classification, protected control or package identity.

**Current:** standalone CLI/SDK and Mac/Windows desktop transports expose
connection-owned intents with pause/ownership fencing. Mac inner native effects
and queued claim handoff have independent counter/stale-reference evidence.
Bounded physical Mac presentation, pause, persistence and Stop are qualified;
revised protected takeover/quiet resumption remains a separate gate. Windows
ordinary approval is memory-only and supports timed or until-stopped access;
bounded signed ARM64 Pause/Resume/Stop evidence is recorded in the Windows
topic. New activity behavior has its own Tactical 103 qualification. Native
shared outer input now borrows an existing exact VM claim under the
claim-store operation lock and the host desktop fence; socket fixtures cover
two VM contenders, physical contention and stale input refusal. Actual Tart/UTM
effect acceptance remains pending in [Tactical 084](../docs/tactical/084-native-outer-desktop-admission.md).
Authenticated signed native YA ordinary integration now has bounded acceptance
in Tactical 086; protected composition remains open. The
[API guide](../docs/access-admission.md) owns wire/client details;
linked tacticals own execution evidence.

**Current:** [Tactical 085](../docs/tactical/085-macos-admission-transport-cleanup.md)
distinguishes a healthy resident cancelling a lost agent from guardian failure,
bounds queue polling and releases interrupted pointer presses. Four bounded physical covered tasks pass independent effects, relock and
consent retention, including two abrupt client disconnects. Hardware takeover
and sustained-load acceptance remain separate.

**Current:** the [native delegation receiver](../docs/tactical/086-native-desktop-delegation.md)
composes admitted ordinary-session scopes with the same pause/resource arbiter.
The full signed YA/CLI/MC operator path now passes bounded ordinary acceptance
with independently observed AX effects. Native Pause retains trust; Resume
waits through a fresh notice and accepts new ownership. Stop refuses reconnect
and remains off after signed resident restart. The owned provider is a protocol
fixture, not an LLM. Prepared-console consent composition is source implemented
in Tactical 087; covered tasks and revised genuine physical takeover/resumption
remain separate acceptance gates.

**Current:** [Tactical 088](../docs/tactical/088-targeted-native-effect-observation.md)
qualifies signed native window capture, pointer/key/activation effects and their
Pause refusals. A bounded busy-owner run observes exactly 32 fresh AX effects
with ownership retained under the unchanged five-second watchdog. Physical
covered resumption, broader load and remaining platform cells stay separate.

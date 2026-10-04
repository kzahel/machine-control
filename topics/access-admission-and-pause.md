# Access admission and pause

Topic: `access-admission-and-pause`

Status: implementation active. Common arbiters and live owner-bound channels
pass deterministic checks. Mac physical notice focus, independent AX effect,
composed operator pause, consent/pause restart and persistent Stop have bounded
live evidence. Protected takeover/local-use resumption, shared outer reservations,
authenticated integration and Windows native acceptance remain open.
Capabilities are qualified separately before release.

## Scope and motivation

**Decision:** standing authorization, temporary availability and exclusive
control have separate lifetimes. An operator choosing **Until I turn it off**
should be able to leave a locked computer useful to authorized agents. Moving
the mouse should interrupt current control and protect the local screen without
requiring the operator to approve access again. The operator also needs a
deliberate way to pause agents while using the computer.

The same admission vocabulary should apply to physical desktops, resident VM
control and explicitly authorized outer recovery. Their resource requirements
and human-interference risks remain different. This topic owns admission,
waiting, interruption, resume and their composition. It does not replace
[caller authorization](caller-authorization.md),
[target-use claims](target-use-claims.md),
[inner-first routing](inner-first-routing.md) or platform protected-control
policy.

## Current foundation

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
actions. Headless/appliance profiles keep their existing authority. Installed
Windows acceptance remains open; this is not authenticated exact-claim binding.

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
manual pause, recent physical activity, operator deferral, resource contention,
authorization validity, session readiness and safety faults. Clearing one
condition must not clear another. Agent-facing clients may cancel their own
work, but cannot clear operator pauses, re-enable access or acknowledge a
safety fault on the operator's behalf.

| Situation | Proposed behavior |
| --- | --- |
| Physical input during covered Mac control | Fence dispatch immediately, end the finite session, request relock and retain covers until lock is independently observed; preserve valid ordinary authorization |
| Screen remains locked after takeover | Wait for verified physical quiet, then allow a fresh unattended session under remaining authorization |
| Owner unlocks after takeover to work | Stay paused while that local-use episode continues; become eligible after re-lock plus quiet, or explicit operator Resume |
| Initial authorized use of an unlocked desktop | Apply ordinary idle/notice policy; post-takeover protection does not forbid every unlocked session |
| Manual pause until Resume | Stay paused across activity changes and clean task completion; no idle timer clears it |
| Manual timed pause | Clear only that reason at its deadline; do not extend timed authorization |
| Broken cover, uncertain lock state, helper failure or changed console identity | Relock/cleanup through the existing watchdog and refuse further control; retain a safety block or revoke affected session authority as appropriate |

**Proposal:** the first physical adapter keeps the existing awake, open-lid
Mac boundary. It needs a verified activity monitor while idle as well as while
covered. Unknown activity/lock readiness blocks automatic activation. Agent
synthetic input must not count as a human takeover or restart the quiet timer.
The exact treatment of scrolling, touch, remote human input and noisy devices
requires platform evidence. The root guardian's relock responsibility must not
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

**Decision:** authorization may be automatic while activation is considerate.
No extra approval dialog is required merely because authorized work waited or
was paused. New scopes and protected/outer authority retain their approval
requirements.

**Proposal:** default to waiting during local activity and a non-focus-stealing
notice before taking an unlocked shared screen. Show who wants control, why,
and the expected duration when known, with **Start now**, **Wait 1 minute** and
**Pause until Resume**. Preferences may select immediate eligible activation
or always announce. Start now clears the applicable notice/deferral; it cannot
override missing authority, another holder or a safety fault.

A locked, physically quiet, prepared Mac can activate unattended, covering the
displays before temporary unlock. It must not wait for someone to acknowledge
a notification on the locked screen. Activity during a countdown invalidates
that activation attempt. The arbiter rechecks eligibility at countdown end.

Deferral applies to the shared desktop resource, so another agent cannot
immediately issue the same takeover notice. Multiple waiters share one relevant
notice; unrelated resident VM work continues. Presentation belongs to the
controller/native operator UI and must not require every provider to host a GUI.

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

**Proposal:** use separate clocks with separately observable expiry reasons.
The examples below are starting values for evaluation, not accepted defaults.

| Clock | Candidate | Required semantics |
| --- | --- | --- |
| Waiting-request keepalive / lease | Heartbeat about every 10 seconds; expire after about 60 seconds | Remove dead waiters; retain authorization; expired entries cannot be resurrected |
| Caller usefulness deadline | Caller supplied, bounded by policy | Stop waiting even if heartbeats continue; do not perform a task after its deadline |
| Activation offer | About 15 seconds | Require a live, ready owner to accept; otherwise offer to the next eligible waiter |
| Physical quiet interval | About 30 seconds | Reset on verified human input; uncertainty blocks activation |
| Unlocked-screen notice | About 10 seconds | Recheck all admission conditions before activation |
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
old subscriptions/handles or bind each message to the live generation so a
browser route cannot continue through a desktop pause. Report operations with
independent non-interfering scope explicitly; no implicit alternate-route
bypass is allowed.

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

**Decision:** deliver independently reviewable slices behind explicit
capabilities. Preserve legacy fail-fast claim acquisition and v0 clients; new
waiting/admission support is negotiated through an additive versioned surface.
Do not advertise queueing or activity detection before the authoritative
provider enforces and tests it. Unsupported platforms report omissions and
typed refusals rather than pretending to offer the Mac covered-use profile.

The [implementation plan](../docs/tactical/074-access-admission-and-pause.md)
orders contract fixtures, enforcement, queues, physical activity, UX, outer
recovery and integration acceptance. Windows remains the common resident
contract proving ground; the Mac adapter is the first physical covered-use
regression target. This is neither an all-platform rewrite nor a release plan.

**Open:** settle timer defaults and accessibility of notices; initial/manual
pause persistence and logout policy; authenticated waiting-client admission;
hardware versus remote/synthetic activity fidelity; fairness and interrupted
queue position; provider cancellation of in-flight work; exact route impact
classification; distributed multi-resource authority; and which background
operations warrant an explicitly independent scope. Record measured answers in
the owning topic/platform report without promoting this proposal to evidence.

**Current:** standalone CLI/SDK and Mac/Windows desktop transports expose
connection-owned intents with pause/ownership fencing. Mac inner native effects
and queued claim handoff have independent counter/stale-reference evidence.
Bounded physical Mac presentation, pause, persistence and Stop are qualified;
revised protected takeover/quiet resumption remains a separate gate. Windows
ordinary approval is still timed and memory-only, and native acceptance remains
unavailable. Native shared outer input now borrows an existing exact VM claim under the
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

# Access admission and pause implementation plan

Status: active coordinating plan; implementation authorized after planning.
Acceptance remains incremental and capability-specific.

Owning topic: [access admission and pause](../../topics/access-admission-and-pause.md).
Related owners: [target-use claims](../../topics/target-use-claims.md),
[caller authorization](../../topics/caller-authorization.md),
[host control](../../topics/host-control.md),
[inner-first routing](../../topics/inner-first-routing.md) and
[Mac locked use](../../topics/macos-locked-use.md).

## Objective

Let authorized agents wait politely for a computer, yield to local use and
resume unattended without confusing a temporary pause with revocation.
Compose this with exact-resource claims, finite protected sessions, explicit
outer-recovery policy and authenticated callers. Cancellation, liveness loss
and all expiry paths must be observable and fence stale work before dispatch.

The motivating product requirement is that **Until I turn it off** remains a
meaningful authorization choice: physical activity ends current covered
control and relocks the screen, but should pause otherwise valid access.
Operator Pause and Stop have different effects. Physical desktops and VM
routes share the vocabulary while reserving different resources.

## Completion conditions

This coordinating plan is implemented only when its selected platform slices:

1. Expose separate authorization, availability, waiting and active ownership
   state, with cancellation, deadlines, owner assurance and generations.
2. Preserve valid authorization through ordinary pauses; retain revocation for
   Stop, expiry, removal of trust and invalid session identity.
3. Enforce pauses and ownership across every advertised governed route,
   including established browser/stream connections.
4. Remove dead waiters, require timely activation acceptance, preserve fencing
   and release shared desktops promptly on interruption.
5. Admit host-interfering outer recovery against both VM and controller desktop
   resources without weakening forbidden routes or resident-first policy.
6. Pass deterministic race/failure fixtures and independent local/remote live
   effect, lock and non-interference checks for each claimed capability.
7. Preserve old client behavior; document unsupported platform capabilities and
   the precise remaining physical/distribution acceptance limits.

Recording this document completes planning only. Each implementation step
should receive a bounded follow-up tactical with its own result and evidence;
do not mark the parent complete after the first working demo.

## Boundaries and dependencies

- Implementation and incremental commits are authorized. Release publication
  is a separate step; this tactical does not imply distribution acceptance.
- Keep existing component ownership from [SYSTEM-MAP](../../SYSTEM-MAP.md).
  MC owns resource arbitration/enforcement; native/controller UI owns notices;
  YA owns broader agent-session coordination. No new inventory authority.
- Preserve native/inner-first control and existing finite protected watchdogs.
  Initial Mac acceptance is awake/open-lid with an existing console session.
  Closed-lid, sleep, fresh login and FileVault/preboot remain excluded.
- Compose with [Tactical 071](071-desktop-caller-authorization.md). Public
  claimant labels, request IDs and claim IDs cannot authenticate a caller.
  Queue fixtures may use admitted test identities; automatic delegated access
  cannot ship before its actual caller boundary is established.
- Persistent operator consent is separate from connection-bound grants. Never
  restore a dead session or widen current target-wide grants through migration.
- Windows owns the reusable resident contract/provider boundary and remains
  its first common enforcement proving ground. Mac-specific covered-control
  work follows the same contract; other platforms adopt only measured slices.
- Keep concrete deployment state, grants, screenshots and test credentials in
  private stores. Use existing claim/doctor and credential-handoff rules for
  any future live appliance work; do not reproduce private inventory here.

## Ordered work

### 1 — specify admission and build deterministic fixtures

Inventory every current grant, claim, session and provider dispatch boundary.
Define versioned status, request, wait/heartbeat, cancel, offer/accept and
availability-event contracts. Specify authenticated ownership, resource sets,
idempotency, generation checks, terminal outcomes and bounded metadata.

Build a fake-clock, fake-provider state-machine harness with independent
dispatch/effect counters. Cover composed pause reasons, timed authorization,
waiting leases, caller deadlines, offers and restart invalidation. Model
physical, resident VM and host-interfering outer routes as distinct resources.
Keep initial candidate timings configurable and named by purpose.

**Gate:** agreed transition tables and executable fixtures prove no effect
while ineligible, no stale-owner mutation and no accidental authority renewal.
Settle the first single-controller multi-resource transaction boundary before
implementation; defer distributed transactions explicitly.

### 2 — enforce resumable pause in one resident vertical slice

Add effective availability at the owned resident boundary, with operator Pause,
Resume and Stop kept distinct. End active sessions on pause and fence dispatch
and subscriptions synchronously. Audit all exposed routes, including browser
relay, CDP, capture streams and platform escape hatches. Define honest outcomes
for actions already delivered or not cancellable inside a provider.

Prove the common contract through the Windows resident/provider tests first.
Then apply it to the Mac broker/guardian boundary without weakening watchdog
relock. Replace physical-takeover revocation with the documented ordinary pause
path; keep failures and invalid console identity blocked separately.

**Gate:** timed grants expire while paused; Resume clears only its own reason;
Stop cannot be undone by a client. Every advertised observation/action route
refuses while paused, and an already-open route cannot bypass the gate.

### 3 — add owner-bound waiting and claim composition

Add waiting intents to the existing authoritative arbitration boundary.
Preserve legacy fail-fast `claim acquire` and v0 capability validation through
explicit version negotiation. Add CLI/SDK bounded wait/cancel support; the
client runtime owns keepalives and prompt cleanup when its parent exits.

Production owner-bound waiting depends on reviewed caller/session admission
from Tactical 071; ownership enforcement cannot wait until consumer integration
in step 7. Any prototype using the current same-user profile must disclose its
cooperative boundary and must not advertise authenticated queue ownership.

Implement bounded queue entries, duplicate submission handling, caller deadline,
lease expiry and short offers accepted by a live ready owner. Resolve aliases
to exact resources, admit complete resource sets and retain claim fencing.
Reuse an already-owned valid VM claim where appropriate; never create a second
independent VM holder. Waiting for approval/idle must not reserve the host
desktop. Expired intents rejoin at the tail; status observers cannot renew them.

**Gate:** two contenders yield one owner; dead waiters/offers clear; aliases
contend; disjoint resident VMs run concurrently; stale heartbeat/accept/cancel
cannot resurrect or alter newer work. Prove bounded storage and fair behavior
under duplicate/flood requests before enabling the queue capability.

### 4 — validate physical activity and unattended Mac resumption

Extend the Mac activity/pause monitor to idle periods, with truthful hardware,
synthetic-input and unknown-state classifications. Implement the post-takeover
local-use episode: locked quiet permits fresh unattended admission, whereas an
owner unlocking to work remains protected until re-lock/quiet or operator
Resume. Keep independent manual pause and failure blocks composed.

Specify secure persistence and migration for operator consent, manual pause,
deferral and Stop. Restart ends offers, queue positions, old delegation and
control sessions. Verify identity/readiness before deriving fresh grants from
remaining consent; uncertain persisted timing fails closed.

**Gate:** physical input cancels covered effects and relocks, existing consent
survives, quiet locked use resumes with a fresh session, and owner-unlocked use
stays paused. Helper failure still relocks; automated input cannot impersonate
operator Resume or keep itself eligible. Native permission setup remains in
Permissions; ordinary pauses do not request a new OS grant.

### 5 — present polite control and operator pause

Add shared status distinguishing allowed, waiting, paused and active. Provide
timed Pause and Pause until Resume, Resume, Cancel request and Stop with their
different consequences. Add configurable unlocked-screen intent notices with
Start now, Wait 1 minute and Pause until Resume. Present truthful caller
assurance and duration; unknown duration is not an invented estimate.

Use one resource-level notice/deferral for competing agents. Countdown
completion revalidates all generations and eligibility. Locked prepared use
does not require a notice acknowledgement. Keep notices accessible and avoid
stealing keyboard focus; reconcile event loss through status.

**Gate:** another agent cannot bypass deferral; stale timers cannot activate;
physical activity cancels an offer/countdown; manual pause stays latched;
screen-reader/keyboard paths work; closing presentation does not orphan control.

### 6 — compose explicit outer recovery with the host desktop

Introduce a private exact controller-desktop resource shared by physical host
use and all host-interfering VM routes. Map actual route impacts, including
headless/capture-only exceptions. Integrate VM claim plus desktop reservation
atomically within the supported controller authority; roll back failed
activation without losing legitimate existing VM lifecycle ownership.

Retain absolute outer prohibitions, disruptive class, explicit reason and
exact target/geometry checks. Any new scoped recovery-request policy is
operator opt-in; notification expiry never grants previously forbidden access.
Declared controller attendance remains the source of truth until a measured
activity capability replaces it for that route.

**Gate:** two different VMs and direct host control contend on one desktop;
ordinary resident VM control does not contend there. No partial reservation
deadlock, silent outer fallback, wrong-target input or forbidden-route dispatch.

### 7 — integrate authenticated agents and lifecycle recovery

Compose with the authenticated integration from Tactical 071. Bind intent,
offer, grant and active session to the admitted owner and transport generations.
Provide cancellable waits and stable event/status semantics to standalone
CLI/SDK and YA. YA may pause the broader agent; MC remains its machine-use
authority without requiring YA to exist.

Exercise session closure, integration crash, transport loss, broker/UI restart,
trust removal, Stop and reconnect. Persist consent/pause choices only under
their reviewed policy; grant fresh delegation after authentication rather than
replaying tokens. Add minimal audit transitions and readable diagnostics.

**Gate:** unrelated/stale callers cannot inherit a queue entry or activation;
closing a session cleans up its work; reconnect cannot undo Stop; missed events
recover from status without duplicate activation or notification storms.

### 8 — qualify selected routes and roll out capabilities

Run deterministic and contract suites before headed/native acceptance. Use
command-driven fixtures, independent effect/lock probes and isolated signed
test installations. Freeze exact Mac candidates so another build cannot replace
an executable during physical permission/helper tests. Use a separately
identified test browser and reap it after browser-route acceptance.

Prove local/remote parity on the Windows appliance and the bounded Mac physical
profile. Use read-only doctor, exclusive attributed claims, renewal and
finally-style release for accepted VM work. Run outer interference tests only
on an explicitly authorized test controller. Physical takeover trials need
independent lock readback before the operator unlocks for recovery.

Update platform reports with precise evidence, topic status with accepted
capabilities, and the common matrix with honest omissions. Runtime changes
follow normal platform checks, including .NET formatting, contract tests and
appropriate ARM64/x64 publishes before any eventual runtime commit. Do not
infer physical, multi-display or distribution acceptance from unit tests.

**Gate:** release only the capabilities whose matrix cells pass; unsupported
routes refuse explicitly. No standing session, covers, claims or test processes
remain after trials; rollback preserves operator consent and safety policy.

## Validation matrix

The fixture layer supplies exhaustive timing/race tests; native trials supply
hardware, session and effect evidence. Each cell needs success and refusal
oracles, not merely a successful API return.

| Area | Required cases | Independent evidence |
| --- | --- | --- |
| Authorization | Timed/until-off; narrow scopes; expired/revoked/untrusted caller; trust removal | Provider dispatch counter stays zero on refusals; grant/consent identities and deadlines match policy |
| Composed pause | Manual + activity + safety fault; timed/manual Resume; Stop; restart | Clearing one reason leaves others effective; no fresh approval after ordinary pause |
| Queue and offer | FIFO eligible peers; aliases; duplicates; dead client; slow poll; offer timeout; useful deadline | Exact single holder, terminal reason, new generation and bounded queue contents |
| Concurrency races | Cancel/accept; activity/countdown; Stop/dispatch; expiry/renew; old release/new owner | No newer-owner mutation; stale dispatch refused; in-flight effect uncertainty recorded |
| Cancellation scope | Pending approval/notice/offer; paused live waiter; late approval; cancel one caller versus Stop all affected work | Canceled intent cannot revive; unrelated consent survives; wait deadlines still run while paused |
| Resource composition | Two VMs sharing host input; direct physical host; VM aliases; disjoint inner routes; unavailable second resource | Host ownership singular; no partial hold/deadlock; resident routes do not alter host focus/cursor |
| Physical covered use | Keyboard/pointer takeover; locked quiet resume; owner unlock/work/re-lock; explicit Pause | Independent OS lock/session readback, cover count and single-fixture effect oracle before recovery |
| Failure recovery | Disconnect, broker/guardian crash or stall, permission loss, cover/display change, sleep, console change, clock jump | Relock watchdog remains independent; no automatic control while readiness/time is uncertain |
| Alternate routes | AX/UIA, capture, input, app/window, scoped clipboard, browser/CDP, open stream | All advertised governed routes honor pause/fencing; stale handles/connections cannot bypass |
| Presentation | Notice timeout, defer, Start now, manual Pause/Resume, many agents, lost events, UI crash | Correct state/assurance, focus unaffected, one resource-level notice, no orphan activation |
| Compatibility | Old/new clients and providers, queue unsupported, activity unknown, local/remote | Legacy fail-fast contract preserved; new features negotiated; equivalent typed outcomes |
| Installation | Signed update/relaunch, helper healthy/revoked, consent persistence, immutable candidate | No routine Repair/reapproval; genuine OS denial stays visible; no stale session restoration |

Use fake clocks to test just-before/at/after every deadline and generated
interleavings of relevant transitions. Add real clock/load trials to choose
heartbeat grace and timer defaults; do not shorten privileged watchdogs merely
to reuse queue timing. Bound queue, event and audit storage under sustained load.

## Result and next work

Implementation is active. Step 1 establishes contract/state-machine fixtures
and the compatibility/authority decisions needed for resident enforcement.
Subsequent slices record their evidence before advertising new capabilities.

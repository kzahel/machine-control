# Private native host inlet

Status: **v2 Windows/reference broad review and bounded native candidate
qualification passed; macOS ordinary packaged slice passed, stream/protected
gates open; Linux adoption pending**. [Tactical 153](../docs/tactical/153-unified-permissions-and-handoff.md#windows-candidate-qualification)
records current evidence and its unsigned ARM64 VM limits.
This private inlet is not an agent API or an independently installed service.
The language/deployment decision and migration gates live in
[the shared-core topic](../topics/shared-resident-core.md) and
[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md).

## Placement and trust

The native resident launches `node/main.ts` as a private child using the
packaged executable and inherited anonymous stdin/stdout. It clears interpreter
environment overrides. There is no TCP listener, approval URL or reusable
approval bearer. Each direction uses the bounded framing in `node/framing.ts`:
four-byte little-endian UTF-8 JSON length and a bounded write backlog of twice
the selected frame limit. The original fixture defaults to 1 MiB; the Windows
and macOS private channels use the 16 MiB limit described below. Diagnostics must never
share stdout.

The parent authenticates operator decisions and provider peers before invoking
this inlet. It must not forward arbitrary agent method names or frame objects.
The methods below convey trusted decisions: they are deliberately unavailable
on the public agent transport. This adds no containment against a same-user
agent with unrestricted shell access.

## Original fixture inlet and correlation

Every parent call has a bounded string `id` and one `method`. The first call is
`hello` with `protocolVersion: 2`. The reply is
`{type:"reply", id, ok:true, data:{protocolVersion:2, bootId, admissionSchema:"machine-control-admission/v2"}}`.
A v1 parent or child is refused before arming; there is no silent downgrade.
The Chrome extension/native-messaging protocol remains version 1.
`bootId` changes on each process creation. IDs and generations are diagnostic
selectors, never public authority. The host never deserializes a core handle.

| Method | Fields and result |
| --- | --- |
| `provider.connect` | Fixture-assigned logical `profileId`; returns `connectionId` and generation. Production installation identity uses `browser.attach` below. |
| `provider.frame` | `connectionId` and worker `frame`; returns whether an exact pending completion applied. |
| `provider.disconnect` | `connectionId`; fences that route. Retains bounded correlation only while already-dispatched work is unsettled. |
| `operator.approve` | Exact `connectionIds` and finite `durationMs`; returns authorization generation. No future profile wildcard. |
| `operator.stop` | Revokes approval before emitting cancellation and inactive grant projections. |
| `request` | `connectionId`, expected `authorizationGeneration`, public `requestId`, `timeoutMs`, typed `operation`; returns submission acknowledgement separately from terminal result. |
| `state` | Returns bounded policy state, process epoch and self-reported runtime/RSS diagnostics. No page data. |

The original fixture request subset is `browser.tabs`, `browser.snapshot` with `tabId`,
and `browser.click` with an issued `reference`. Snapshot references bind the
process epoch, connection and approval generation before the worker's opaque
reference. They cannot cross profiles, reapproval, reconnects or restarts.

Child events can precede a call's acknowledgement:

- `provider.send` carries the exact `connectionId` and bounded worker frame.
- `provider.close` asks the parent to close that exact transport.
- `request.finished` carries the core terminal result. Submission acceptance
  and application effect remain distinct; no automatic retries are permitted.

Do not assume a terminal result and its following authority projection share
one pipe read. Respect message order while independently draining every frame.

The parent must consume events while awaiting replies and bound both pending
calls and transport buffering. The fixture client permits at most 64 calls.
The core permits 16 current providers and 64 retained requests; the host also
bounds active plus retired provider adapters to 80. Unknown dispatched effects
remain retained until exact completion. A trusted native host can explicitly retire a permanently disposed transport
and release its correlation slots. Retirement preserves unknown application
outcomes and rejects late callbacks; it never supplies a successful effect.

## Scheduling and failure

The Windows parent drains synchronous anonymous-pipe reads and stderr on
dedicated threads and serializes writes through one bounded dedicated worker.
Blocking pipe I/O cannot occupy the managed pool needed for reply processing.
The three-second write watchdog terminates the exact owned child to release a
blocked or partial write; it never retries the frame. Terminal child failure
revokes browser authority while the native safety monitor remains available.


The core provides the next deadline. The executable schedules a single wake
only while authority or a request has a deadline; Off has no periodic timer.
Fresh dispatch and completion checks still enforce the exact deadline, even
when a timer fires late. Settings never owns this process or its consent.

EOF revokes, emits cleanup if output remains writable, and exits. Malformed
framing, output backpressure failure or broken parent transport also terminates
the child. Hard kill cannot emit cleanup: the parent must synchronously close
its provider transports when the child dies. The extension's native-port loss
withdraws access independently. A fresh child starts Off with no connection,
request replay or consent restoration. Do not reconnect native transports to a
replacement child using cached approval.
Report outstanding dispatched work as unknown after child death; process exit
does not prove that an already-submitted application action had no effect.

The original fixture inlet alone does not establish native caller/owner
admission or installed identity. The production Windows inlet below supplies
that boundary; native packaged acceptance remains a separate qualification gate.

## Profile-aware Windows adoption inlet

The native parent also uses `browser.attach` with its authenticated extension
origin, bounded worker hello/profile metadata and private transport tag;
`operator.configure` with exact profile IDs/scopes and the original remaining
lifetime; `native.state` with native safety/epoch observations; `browser.call`
with an admitted native owner handle and public request; and `provider.retire`
after permanent transport disposal. These remain trusted inherited calls.

`browser.call` supports the ordinary operation vocabulary and profile discovery.
An omitted selector chooses only a single explicitly approved profile, including
its offline refusal; it never fails over. Endpoint tokens and streams use the
same core fences and profile-scoped reservations. `native.check` events require
parent acknowledgements for live owner validation and payload-free CDP audit
intent/results; the child cannot mint native caller ownership.

The private child channel accepts up to 16 MiB for bounded capture/results.
Chrome-directed messages and public request parameters remain at 1 MiB. The
Node WebSocket adapter uses pinned MIT-licensed `ws`; its runtime and LICENSE
are included in Node payloads.

Wire request IDs and extension grant generations include the fresh policy
process namespace as well as connection/approval generations. A worker may
outlive a native transport or child process; an old callback must not match a
new request merely because numeric counters restart. Native parents still
close the old transports and require fresh consent after child death.

`operator.checkpoint` and `operator.restore` preserve an original person's
browser consent while a temporary native grant replaces it. The parent holds
only a one-shot opaque checkpoint ID. The core owns the original deadline and
withdrawal history; the restore call accepts no replacement duration or profile
set. `operator.configure` with no browser scopes ends current browser access
while preserving a saved checkpoint. `operator.stop` invalidates every checkpoint.
Neither method is exposed on an agent or extension transport.

## Surface policy and native channel ownership (v2)

`src/admission.ts` is the only resident surface/admission engine. Its trusted
`access.*` inlet supports `configure`, `notice`, `ready`, `pause`, `resume`,
`input`, `approve`, `start`, `defer`, `deny`, `stop` and `state`. Configuration names one
surface (`desktop` or `browser`), mode (`off`, `ask`, `automatic`), finite
`durationMs` or null until-off lifetime, and exact Browser `profileIds`.
Native facts never supply permission: readiness, notice visibility and pause
are independent of consent. An explicitly ready locked route keeps its impact
reservation while skipping an invisible warning; Ask still requires approval. Unknown native activity blocks Desktop; background Browser work does
not inherit that block. Restart starts both surfaces Off with no owners.

The parent opens each authenticated agent channel through `access.open` using
a private native owner label. The host maps it to an unforgeable runtime-local
owner object. `submit`, `inspect`, `accept`, `authorize`, `cancel` and `close`
require that binding. Native channel EOF calls close. A public session ID,
request ID, profile name or fence cannot open a native channel or impersonate
another owner. This is still same-user coordination, not shell containment.
The Windows public channel and state negotiate
`machine-control-admission-channel/v2` and `machine-control-admission/v2`.
Python remains the client language and maintains the live channel/heartbeat.

A request names required surfaces, exact profiles, bounded wait/use durations,
a reason and an optional narrowed operation set. The trusted native operation
router derives human interference; callers cannot assert a safe/background
flag. Known noninterfering browser observations skip the warning. Unrestricted
browser channels, JavaScript/CDP, navigation and mutations conservatively use
the Browser warning. Disruptive tasks atomically reserve the shared human-input
resource in addition to their surface/profile resources. Blocked compound work
holds no partial reservation. Notice deferrals bind the required resources,
including shared human input, so another client/surface cannot bypass them. A
deliberate takeover starts a fixed human-input cooldown while independent
background work remains eligible. Native dialogs/input require Desktop admission;
there is no browser-to-native fallback.

An ordinary `browser.call` also carries the parent's trusted `ownerSession` and
`ownerProfileIds`, derived from authenticated native ownership. Profile names
resolve in the shared profile registry, then must belong to that exact owner.
Returned semantic references include the owner-session namespace as well as
process, provider and consent generations. A new task/owner cannot reuse old
references. This avoids revoking unrelated profiles merely to retire one owner.
Streaming CDP retains its original native owner checks and audit acknowledgements.

Production scheduling considers both engines' next deadlines. The native
adapter retains transport bindings and readiness facts, not a translated queue,
approval engine or countdown. Child failure closes streams, retires native
owners and projects an unavailable/off state with working Stop. The fixture-only
`testing/admission-host.ts` supplies a manual clock for native contract tests;
it is excluded from production payloads, which copy only `src/` and `node/`.

The outer recovery channel remains explicitly version 1 under its separate
borrowed-claim contract. It cannot serve as fallback for the v2 resident UI or
client. Its convergence/removal belongs to the platform migration accounting.

The private state retains bounded complete queue data. Windows operator state
prioritizes warnings/approvals and limits detailed requests to sixteen while
reporting complete counts and a truncation flag, keeping the native operator
frame below its 1 MiB bound even with maximal profile selections. This is a
presentation bound, never a second admission decision.

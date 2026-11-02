# Private native host inlet

Status: **implemented for qualification; not an installed or agent API**.
The language/deployment decision and migration gates live in
[the shared-core topic](../topics/shared-resident-core.md) and
[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md).

## Placement and trust

The native resident launches `node/main.ts` as a private child using the
packaged executable and inherited anonymous stdin/stdout. It clears interpreter
environment overrides. There is no TCP listener, approval URL or reusable
approval bearer. Each direction uses the bounded framing in `node/framing.ts`:
four-byte little-endian UTF-8 JSON length, maximum 1 MiB per object and 2 MiB
write backlog. Diagnostics must never share stdout.

The parent authenticates operator decisions and provider peers before invoking
this inlet. It must not forward arbitrary agent method names or frame objects.
The methods below convey trusted decisions: they are deliberately unavailable
on the public agent transport. This adds no containment against a same-user
agent with unrestricted shell access.

## Messages and correlation

Every parent call has a bounded string `id` and one `method`. The first call is
`hello` with `protocolVersion: 1`. The reply is
`{type:"reply", id, ok:true, data:{protocolVersion:1, bootId}}`.
`bootId` changes on each process creation. IDs and generations are diagnostic
selectors, never public authority. The host never deserializes a core handle.

| Method | Fields and result |
| --- | --- |
| `provider.connect` | Authenticated `profileId`; returns `connectionId` and generation. Identity remains fixture-assigned until the production profile handshake is adopted. |
| `provider.frame` | `connectionId` and worker `frame`; returns whether an exact pending completion applied. |
| `provider.disconnect` | `connectionId`; fences that route. Retains bounded correlation only while already-dispatched work is unsettled. |
| `operator.approve` | Exact `connectionIds` and finite `durationMs`; returns authorization generation. No future profile wildcard. |
| `operator.stop` | Revokes approval before emitting cancellation and inactive grant projections. |
| `request` | `connectionId`, expected `authorizationGeneration`, public `requestId`, `timeoutMs`, typed `operation`; returns submission acknowledgement separately from terminal result. |
| `state` | Returns bounded policy state, process epoch and self-reported runtime/RSS diagnostics. No page data. |

The current request subset is `browser.tabs`, `browser.snapshot` with `tabId`,
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
remain retained until exact completion. Long-term quiescence/reclamation is
an explicit production migration gate, not an invented timeout-based success.

## Scheduling and failure

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

The production integration still needs native caller/owner admission,
profile-aware handshake, full ordinary operations, DevTools streams,
indefinite operator lifetimes and installed identity/signature qualification.
This protocol subset must not be advertised as a complete Windows migration.

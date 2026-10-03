# Resumable access admission

The admission v1 arbiter separates authorization from availability and finite
ownership. Current desktop channels use the existing target-wide workstation
grant and bind ownership to one live same-user transport. Caller labels are
informative; hostile same-user containment and YA-attested delegation are not
claimed. Tactical 071 owns stronger caller integration.

## Standalone use

Select the target, run doctor and acquire its normal attributed claim where
required. Existing `claim acquire` remains fail-fast v0; admission does not
silently replace a legitimate VM claim or renew one the caller no longer owns.
Carry the claim on control operations as on ordinary desktop operations.

```sh
machine-control --target host --claim CLAIM_ID control call \
  '{"operation":"snapshot"}' --reason 'Inspect the current screen' \
  --scope observe --scope control --wait 5m --duration 2m
```

The client waits for current authorization, resource availability and the
operator's notice. It explicitly accepts a short offer, executes once with the
returned fresh session and complete resource generations, then cancels and
closes the owning transport. Ctrl-C, parent exit or transport loss releases
ownership; watchdog expiry is the backstop. An uncertain input is never
replayed automatically. Grant clocks continue while paused.

The Python SDK's `ControlSession(target, reason=..., scopes=..., wait=...,
duration=...)` is a context manager over an already resolved common-client
target. `wait()` accepts a current offer, `status()` observes without renewing,
`call(request)` dispatches once, and `cancel()` ends only this connection's
intent. A background keepalive owns liveness and checks the existing selected
claim. After interruption, inspect status and wait for a **new** session before
issuing new work. Closing the context releases promptly; no session or queue
position is restored after reconnect.

## Live wire

An adapter's `channel` command is a byte transport. The client sends one bounded
JSON line and waits for its reply before sending subsequent frames. The first
frame has operation `control.open`, schema `machine-control-admission/v1`,
requestId, reason, scopes, durationSeconds (1–900) and waitSeconds (1–14400).
The adapter chooses resources and derives ownership from the actual connection;
public labels cannot set either. No public operation can operator-Resume.

Subsequent frames have unique bounded requestId and one of:

| Operation | Additional fields | Effect |
| --- | --- | --- |
| `control.status` | none | Observe; never renew |
| `control.heartbeat` | none | Renew a still-live waiting/active lease |
| `control.accept` | offerGeneration | Accept a current unexpired offer |
| `control.cancel` | none | Cancel this connection's intent, idempotently |
| `control.dispatch` | sessionId, resourceGenerations, request | Recheck current ownership, scopes, pause and provider generation before dispatch |

Replies use `machine-control-admission-channel/v1`, requestId, accepted,
errorCode and data. State projections use the admission v1 schema. Dispatch
data retains the native resident operation envelope: request acceptance,
delivery, independently observed effect and uncertainty remain separate.
Only one effect request may be in flight per channel; heartbeat and cancellation
remain available while an asynchronous browser effect is pending. Interrupted
in-flight delivery is reported as uncertain, with unsafe replay.

Waiting lease: 60 seconds; activation offer: 15 seconds; active heartbeat:
5 seconds. Status polling does not supply liveness. The client runtime sends
keepalives only while its context/parent is alive. Late heartbeats and offers
cannot resurrect terminal work. Storage and frames are bounded.

## Scope and current limits

Mac desktop and Windows desktop workstation profiles expose the new live
channel. Mac inner adapters relay the same resident transport without touching
the controller desktop. Windows appliance/protected-service admission and
other providers must refuse until their corresponding owner channel is adopted.
Do not infer support from an ordinary v0 control endpoint. Mac physical activity
uses existing input permission, waits for 30 seconds of quiet and fails closed
on unknown observations; its covered guardian/root relock remain independent.

Operator notice UI, persistent consent, shared host/VM outer resource admission,
YA-attested integration and signed native acceptance are subsequent parts of
[Tactical 074](tactical/074-access-admission-and-pause.md). Current source/fixture
capabilities are not release or physical acceptance.

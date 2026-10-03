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
claim. Adapters also check the exact claim before every incoming frame and
periodically without client polling; expiry/release/replacement closes the
transport without acquiring or renewing a claim. After interruption, inspect status and wait for a **new** session before
issuing new work. Closing the context releases promptly; no session or queue
position is restored after reconnect.

## Live wire

Exact target claims have a separate, additive queue. Explicitly inspect
`claim capabilities --version 1`, then use `run --wait 5m` with the normal
attribution and a local task. The existing task runner owns child selection,
explicit claim renewal, cancellation and finally-style cleanup; queued workspace
derivation is refused. Without `--wait`, runs retain fail-fast v0 acquisition.
The Python `ClaimSession` context exposes `wait()`, `status()`, `cancel()`,
explicit `renew()`, and `bound_target()` for ordinary calls or `ControlSession`.
Never independently acquire another claim for an already-owned valid VM.

The exact-target adapter's `claim-channel` starts with `claim.open` and schema
`machine-control-claim-admission/v1`. Supply reason, claimantAuthority,
claimantId, waitSeconds, optional durationSeconds/useClass/metadata/sessionId/
label, and a bounded requestId. The adapter supplies exact identity. Subsequent
`claim.status`, `claim.heartbeat`, `claim.accept` (offerGeneration) and
`claim.cancel` operate only on this connection. Replies use
`machine-control-claim-channel/v1`; status uses the claim admission schema and
returns the existing v0 claim descriptor only after active acceptance.

The claim SDK sends strictly increasing requestSequence values in actual write
order. Sequence replay/gaps close the owner; memory does not grow with a long
claim. Unsequenced diagnostic clients have a 4096-ID budget. Frames are at most
64 KiB, byte queues are bounded, and stalled output closes ownership. Waiting
heartbeat/offer/active heartbeat are 60/15/5 seconds. None renew the underlying
claim; useful wait and authority expiry remain independent. Self-asserted
claimant labels authenticate nothing. See [Tactical 082](tactical/082-queued-target-claims.md).

## Desktop wire

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

Mac native notices and shared desktop pause controls are implemented. Mac local
consent and manual pause/deferral persist within the same console session and
boot; live grants, queue positions and sessions never do. Stop clears consent,
and restoration rechecks identity, existing permissions and readiness. Windows
approval remains timed and memory-only. Shared host/VM outer resource admission,
YA-attested integration and further signed native acceptance remain parts of
[Tactical 074](tactical/074-access-admission-and-pause.md). Current source/fixture
capabilities are not release or physical acceptance.

### Long-lived frame ordering

A native desktop channel advertises `requestSequencing: "strict"` in its intent
views when it supports ordered frames. After reading the opening reply, new
SDK clients send `requestSequence` starting at one and increment it for each
complete frame. Sequence replay, a gap, overflow or an unsequenced frame after
switching ends the connection and its ownership. Repeated request labels are
safe in ordered mode because the live sequence distinguishes frames. This
uses constant replay memory throughout a bounded four-hour wait.

Older providers omit this field and newer clients retain their legacy framing.
Older unsequenced clients keep the bounded 4,096-ID connection budget. Ordered
framing does not renew authority, extend useful deadlines or replay an action.

### Controller-local outer recovery

`OuterSession` opens a host desktop channel with the adapter-derived
[private borrowed-claim binding](../contracts/outer-borrow-v1.schema.json).
The native intent must negotiate `outerRecovery: "borrowed_exact_claim/v1"`;
an older provider cannot silently fall back to global host input. `prepare()`
discovers a finite window/geometry reference, `begin()` requests focus, and
`step()` sends one typed key/click/drag primitive. Interrupted input is never
replayed and a resumed session requires fresh discovery.

The native arbiter reserves the host desktop, while the existing exact VM lease
remains borrowed under its own deadline. Activation and each native input effect
validate that lease under the claim store's operation lock; failed activation
leaves the existing VM holder intact. All direct physical host use and global
VM input through this controller contend on that desktop. Inner VM control and
VM-directed/capture-only outer routes keep their narrower resources. Existing
absolute route prohibitions, disruptive class and attendance checks still apply.

This is cooperative controller-local coordination, not authenticated session
admission or a distributed transaction. Credential input and diagnostic
Control/Option/Fn chords are unsupported by this bridge. See
[Tactical 084](tactical/084-native-outer-desktop-admission.md) for the measured
fixture boundary and outstanding live acceptance.

# Admission contract and controller arbiter

Status: complete (contract slice); production integration remains in the parent.

Owning topic: [access admission and pause](../../topics/access-admission-and-pause.md).
Parent: [Tactical 074](074-access-admission-and-pause.md), step 1.

## Objective and boundaries

Implement a bounded, single-controller admission model beside the owned
Windows resident contract. Separate authorization callbacks, composed resource
pauses, waiting liveness, activation offers and finite active sessions.
Public identifiers do not authenticate callers. This slice does not expose
production queue capabilities, change VM claim v0, or claim hardware evidence.

## Work and completion conditions

1. Define a versioned status/intent schema with reasons, deadlines and fencing.
2. Admit complete resource sets; aliases must be resolved by the owning adapter
   before submission. Waiting on one unavailable resource holds no partial set.
3. Require offer acceptance and renew live waiting/active owners separately.
4. Preserve pause reasons independently; interrupting active control yields its
   position and requires a new session and resource generations on resume.
5. Bind mutation to an in-process admitted owner, not request metadata.
6. Bound live intent, terminal and event history; reject malformed intervals.

## Validation

The standalone .NET contract runner uses a monotonic fake clock and resource
effect/fencing checks. It exercises multi-VM/host contention, disjoint work,
pause composition, queue/offer/usefulness expiry, stale ownership, cancellation,
notice invalidation, authorization loss and parallel contention. Runtime builds
must also pass format verification and Windows ARM64/x64 publishes.

## Result

The deterministic runner and existing Windows desktop contracts pass. Format
verification and Windows ARM64/x64 publishes pass. The runner executes with
the available .NET runtime through major-version roll-forward; actual Windows
execution remains a later native acceptance gate.

The next slice wires resident enforcement and native
operator controls to this model; no production queue or physical activity
capability is advertised by this execution record.

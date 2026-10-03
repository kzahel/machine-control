# Live queued target-use claims

Status: completed for the cooperative exact-resource v1 claim profile.
Shared outer desktop transactions and authenticated caller grants remain separate.

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md)
and [target-use claims](../../topics/target-use-claims.md).

## Objective

Let an attributed live caller wait fairly for an exact target, cancel promptly,
and explicitly accept a short offer without changing legacy fail-fast claims.
The existing private claim authority owns arbitration; no coordinator-specific
queue or second VM holder is introduced.

## Completion conditions and boundaries

- Explicit v1 capabilities and live adapter transport; unchanged v0 capability
  validation, acquire, renew and release behavior.
- Bounded FIFO waiters, disjoint-resource progress, readonly status, useful
  deadline, waiting liveness, short offer and stale-accept refusal.
- Active connection expiry fences the exact claim before ordinary dispatch.
  Keepalive never renews authority. Cancellation/disconnect releases only the
  matching claim, never a successor's reservation.
- Crash between activation writes has a recoverable private intent record.
  Slow output and parent loss cannot hold a forgotten claim indefinitely.
- CLI task cleanup and SDK contexts work against the authoritative VM adapters;
  native remote effect and stale-reference checks accompany fixture results.
- This is same-user coordination with self-asserted attribution. It neither
  authenticates YA sessions nor grants desktop/protected/outer permission.
  Queued workspace acquisition and distributed transactions remain unsupported.

## Ordered work

### 1 — negotiate waiting without changing v0

Add `claim capabilities --version 1` and a private `claim-channel` transport.
The authoritative adapter supplies provider, exact identity and store locator;
caller frames cannot replace them. One connection owns one intent. Duplicate
submission with changed parameters is refused; reconnect is a new owner.

Keep the original exclusive claim descriptor and fencing generation. Legacy
acquire remains fail-fast and cannot jump past a live queued activation offer.
Waiting does not create a claim. Accept commits the next claim under the same
store lock used by legacy acquisition.

### 2 — fence liveness, expiry and interrupted activation

Use a 60-second waiting heartbeat, 15-second offer and five-second active
heartbeat, distinct from useful wait and claim authority deadlines. Inspect
never extends them. Late heartbeat/accept cannot restore a terminal entry.
Bound storage to 256 entries, compact terminal history and bounded byte queues.

Write a private activation intent before the claim record, flush records before
replacement, and retain the exact generated claim selector for crash cleanup.
Every claim check sweeps expired queued ownership before authorizing use. A
replacement claim cannot match the old intent and is preserved.

Watch parent/input/output independently. Strict ordered connection sequences
provide bounded replay rejection without accumulating IDs for a four-hour
claim. Legacy unsequenced clients retain a finite request-ID budget. An output
stall ends the owner and bypasses a blocked interpreter stream flush.

### 3 — connect standalone clients and prove native handoff

Add `ClaimSession` with explicit accept, status, cancel, renewal and a bound
target for ordinary calls or `ControlSession`. Its heartbeat preserves liveness,
not authority. Add `run --wait DURATION`; existing runs remain fail-fast. Keep
scoped child selection, process-tree cleanup, signals and exact claim release.
Refuse a queued workspace intent before mutation rather than independently
claiming its returned VM again.

Exercise Mac, Windows and Linux adapter routing through fixture identities.
On a claimed, ready Mac VM, serialize two owners, perform one native AX effect,
observe its independent counter, and hand off to a higher claim generation.
Keep the fixture alive while checking that its prior reference is stale and
does not change the counter. Release both contexts and restore the task's
ordinary coordination claim for continuing work.

## Validation and final result

**Current:** 33 claim/adapter tests cover arbitration, alias/disjoint behavior,
deadlines, no authority renewal, crash commit recovery, stale owners, bounds,
version compatibility and the three VM entry points. Ten live SDK/CLI tests
cover handoff, explicit renewal, EOF, heartbeat expiry, sequence replay,
backpressure, scoped child execution and cancellation. The full 170-test common
client suite passes; Windows host adapter checks pass.

**Current, bounded native Mac VM evidence:** two queued owners serialized;
native AX produced counter delta one. Handoff increased the exact claim's
fencing generation. With the same fixture still running, its old reference
returned `stale_reference` and the counter stayed unchanged. Cleanup reaped
the fixture, released queue owners and restored the continuing task claim.
Raw records and concrete target details remain private.

This completes exact-target queueing under the existing cooperative profile.
It does not complete Tactical 074's shared outer reservation, stronger caller
admission, protected resumption or unavailable native Windows acceptance gates.

# Resumable access admission

The [unified permissions contract](../topics/access-admission-and-pause.md)
separates surface consent, temporary availability, a waiting task and finite
active ownership. The shared TypeScript policy implements resident admission
v2; Windows, macOS and Linux now have native adapters over that shared policy.
[Tactical 153](tactical/153-unified-permissions-and-handoff.md) owns current
qualification. Older resident v1 channels cannot silently satisfy v2 requests.

Configure Desktop and Browser independently as Off, Ask first or Automatic.
Browser includes supported CDP and page JavaScript, with exact selected profile
IDs. Ask approval belongs to one waiting task; public caller labels never
supply operator authority. Same-user shell containment and YA-attested
delegation are not claimed.

## Standalone use

Select the target, run doctor and acquire its attributed claim where required.
Admission neither replaces the exact-target claim nor renews it implicitly.
Carry that claim through ordinary control operations.

```sh
machine-control --target host --claim CLAIM_ID control call \
  '{"operation":"snapshot"}' --reason 'Inspect the current screen' \
  --surface desktop --wait 5m --duration 2m
```

The client keeps one live wait, accepts an unexpired offer, dispatches once with
fresh ownership and complete resource generations, then closes. Off and denial
are terminal refusals; temporary pause/busy states remain waiting. Consent
clocks continue while paused. An uncertain application effect is never replayed.

For related observations and actions, retain a connection:

```sh
machine-control --target host --claim CLAIM_ID control stream \
  --reason 'Inspect and operate the application' \
  --surface desktop --wait 5m --duration 5m
```

Write one common request per line and read one compact result per line. Results
flush before the next action. Empty input acquires nothing. References from a
completed owner cannot be reused by another session. A refusal, unknown delivery
or unknown/partial effect ends the stream without dispatching later input.
Confirmed delivery with an explicitly unverifiable effect permits a subsequent
observation; it does not authorize automatic replay.

The Python SDK remains `ControlSession(target, reason=..., surfaces=...,
profile_ids=..., operations=..., wait=..., duration=...)`. Browser tasks must
name exact enabled/approved profile IDs. An optional operation whitelist lets
the server classify a strictly observational Browser task as background work;
unrestricted Browser/CDP tasks conservatively require a disruptive handoff.
The public scope-based v1 constructor/CLI contract is retired explicitly.

`wait()` accepts a current offer, `status()` observes without renewing liveness,
`call(request)` dispatches once, and `cancel()` ends this connection's intent.
The background heartbeat keeps the live context useful and checks its claim.
By default the SDK also negotiates typed renewal of the same active owner:
`duration` selects a finite lease interval (15–900 seconds for automatic renewal),
not a total task cutoff. A healthy retained task may continue past fifteen
minutes without re-acquiring ownership or requesting fresh approval. Renewal
never extends the original consent. After interruption,
wait for a fresh owner and observe again before further actions. Closing the
context releases promptly; reconnect restores no owner, stream or queue position.
A caller must close stream stdin when finished; a CLI blocked on stdin may
remain alive after its owner expires, but cannot dispatch further input.

Use `renew=False` in the SDK or CLI `--no-renew` for an intentionally finite
owner. `renew=True` / `--renew` requires negotiated provider support rather
than accepting a finite fallback. The default (`renew=None`) renews supporting
providers automatically; unsupported providers and intervals below 15 seconds
retain finite behavior. Keep the target claim renewed separately, or use a
[scoped run](scoped-runs.md). Losing the claim ends automatic renewal.

Ordinary Windows v2 owners support same-connection `renew()`, retaining their
session/generation fence under the original consent.
Only renewal can extend the finite task deadline; heartbeat and resumption
cannot. Prepared Windows owners advertise renewal only once their native
guardian reports support. Each extension is acknowledged by the protected
service and guardian before it commits (Tactical 160). The Mac adapter supports protected
renewal when its actual helper acknowledges it. Earlier Mac v1 sustained
renewal evidence is in [Tactical 144](tactical/144-renewable-control-owners.md);
v2 native adoption and its qualification limits are in
[Tactical 154](tactical/154-macos-shared-surface-adoption.md).

## Ordinary one-shot negotiation

The Windows desktop product requires owner context for native observation,
application/input and Browser work. A direct call first declares
`control_session_required` with v2 surface metadata, even during temporary
activity/cooldown/pause. The common client negotiates only when the refusal
proves delivery/effect were refused, uncertainty is `none` and replay safety is
`safe_not_dispatched`. It preserves and dispatches the original operation once.
Transport loss or uncertain effects never trigger fallback/replay.

Metadata and the private operator channel retain their own native checks.
Headless/dedicated-appliance and outer recovery routes remain distinct; an
ordinary endpoint does not imply protected or outer authority. Explicit raw
parity probes retain their route instead of silently opening another channel.
Raw Browser endpoint export is not a substitute for owner-bound typed streaming.

## Resident desktop/Browser wire (v2)

An adapter's `channel` command transports bounded newline JSON. Open with
`control.open`, schema `machine-control-admission/v2`, requestId, reason,
surfaces, exact profileIds for Browser, optional operations, durationSeconds
(1–900) and waitSeconds (1–14400). The adapter derives native owner identity;
the private host supplies an unforgeable owner handle. Public IDs are labels.

| Operation | Additional fields | Effect |
| --- | --- | --- |
| `control.status` | none | Observe without renewing |
| `control.heartbeat` | none | Refresh liveness without extending consent/task duration |
| `control.accept` | offerGeneration | Accept the current offer |
| `control.cancel` | none | End this connection's task |
| `control.renew` | sessionId, resourceGenerations, durationSeconds | Extend a live ordinary owner only under remaining consent; requires advertised renewal |
| `control.dispatch` | sessionId, resourceGenerations, request | Recheck owner, surfaces/profiles, operation whitelist, native safety and generations |

Replies use `machine-control-admission-channel/v2`; state uses the admission v2
schema. Only one effect dispatch can be in flight per channel; heartbeat and
cancellation remain available during asynchronous work. Native result envelopes
keep acceptance, delivery, independently observed effect and uncertainty distinct.

SDK frames send strictly increasing requestSequence values in write order
after open. Replay, gaps, overflow and invalid framing close ownership. Bounded
unsequenced diagnostic clients retain a 4,096-ID budget; once sequencing starts,
unsequenced frames close the connection. Waiting lease,
activation offer and active heartbeat are 60/15/5 seconds. Status supplies no
liveness, and late frames cannot resurrect terminal work. Native adapters also
validate the selected claim periodically without client polling.

## Handoff and native boundaries

Automatic disruptive work announces for ten seconds while ordinary typing can
continue. Native presentation remains independent of Settings and preserves
focus. Start now acknowledges its own interaction; deliberate key/button/scroll
input after activation yields to a fixed minute of cooldown and a fresh warning.
Movement alone does not interrupt. Timed or indefinite operator deferral, denial
and Stop have distinct effects. Global pauses override both surfaces; background
Browser observation does not reserve the whole desktop. Compound native effects
must satisfy Desktop's mode before dispatch, without an implicit fallback.

Native identity, session readiness, OS permissions, hooks, cover/lock/relock,
protected credentials and effect evidence remain native constraints. A countdown
cannot supply missing safety. Restart remembers form choices without restoring
consent, task approvals, active ownership or queued work. See the owning topic
for platform and live-evidence limits.

## Exact-target claim wire

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


## Controller-local outer recovery (separate v1 route)

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

## Retired desktop delegation field

The macOS-only `desktopDelegation` open field and its trusted YepAnywhere
proxy were removed by
[Tactical 161](tactical/161-verified-callers.md). A frame that still carries
the field refuses with `desktop_delegation_retired` and never becomes a plain
owner. [Tactical 086](tactical/086-native-desktop-delegation.md) records the
retired design.

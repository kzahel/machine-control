# Target-Use Claims

Topic: `target-use-claims`

Status: implemented for accepted Windows, macOS, and Linux VM adapters.

## Scope

This topic owns exclusive-use coordination for a machine-control target. A
target-use claim lets one cooperative caller reserve an exact VM or derived
workspace for a bounded interval, identify the work and claimant, renew while
work remains active, and release when finished.

A target-use claim is distinct from:

- a logical target or workspace handle, which selects a resource;
- a workspace receipt, which proves adapter ownership for safe cleanup;
- an authorization lease, which grants a protected capability; and
- authentication or hostile-user containment.

The first implementation covers the accepted Windows, macOS, and Linux VM
adapters. The contract is provider-neutral and may later cover contended
physical devices without pretending that every target has the same lifecycle.

## Decision

**Decision:** meaningful use of an accepted VM target requires one live
exclusive claim. Machine Control owns resource arbitration, expiry, renewal,
release, exact-identity binding, and fencing. It has no dependency on a
particular agent coordinator.

Any environment may supply bounded claimant attribution:

```text
authority   caller-chosen identity namespace
claimantId  caller identity within that namespace
sessionId   optional task or session identity
label       optional human-readable description
metadata    optional bounded string map
reason      required explanation of the work
```

Caller-supplied values are `self_asserted`. A future authenticated transport
or external broker may provide `transport_authenticated` or `broker_attested`
identity, but merely spelling an authority name never raises assurance.
Attribution is visible coordination information and must contain no secret,
credential, private endpoint, or concrete provider identity.

## Public surface

The common surface is additive beside target lifecycle and workspaces:

```text
machine-control --target <alias> claim capabilities
machine-control --target <alias> claim status
machine-control --target <alias> claim acquire \
  --duration 30m --reason <text> \
  --claimant-authority <namespace> --claimant-id <id>
machine-control --target <alias> claim renew <claim-id> --duration 30m
machine-control --target <alias> claim release <claim-id>

machine-control --target <alias> --claim <claim-id> target ensure-ready
machine-control --target <alias> --claim <claim-id> desktop snapshot
```

The claim identifier is an opaque selector, not bearer authority. In the
current same-user CLI profile, claims coordinate cooperating processes and do
not claim isolation from another process with the same shell and filesystem
authority.

`claim capabilities`, `claim status`, target `status`, target `doctor`, target
`capabilities`, workspace `capabilities`, workspace `inventory`, and dry-run
workspace garbage collection remain claim-free. Other target use requires a
live claim, including lifecycle mutation, maintenance audit or mutation,
desktop and application observation, capture, input, administration, outer
recovery, and workspace release.

An operation without a required claim returns `claim_required`. A mismatched,
expired, or stale claim returns a distinct typed refusal before the requested
target operation is dispatched.

## Lease and fencing policy

**Decision:** every claim is exclusive, expiring, renewable, and bound to the
adapter's exact private resource identity. The initial portable policy is:

- 30-minute default duration;
- 60-second minimum duration;
- four-hour maximum requested duration and continuous lifetime;
- explicit renewal by the current claim identifier;
- idempotent release when no newer holder exists; and
- no queueing or stealing of an unexpired claim.

Provider policy may tighten these bounds and reports the effective values
through claim capabilities. Expiry is the reliable forgotten-release
backstop; callers should still release promptly. An agent coordinator may
renew during active work and release on completion without Machine Control
knowing which coordinator it is.

Each successful acquisition increments a private per-resource fencing
generation. Every validation result binds the claim identifier and generation
to the exact resource. A former holder cannot validate after expiry and
reacquisition. The initial CLI boundary checks immediately before dispatch;
future independently reachable resident transports must carry and enforce the
same claim assertion rather than creating a second lease authority.

## Authority and storage

**Decision:** the authoritative platform adapter is the arbitration endpoint.
It resolves the logical target or workspace handle to a concrete provider
identity before atomically acquiring or checking a claim. Two aliases that
resolve to the same provider object therefore contend on one resource.

Private claim state lives beside the authoritative adapter, not in the public
target registry or coordinator. Records are mode `0600` inside a mode `0700`
directory on POSIX hosts and contain the exact provider identity, current
generation, claimant attribution, reason, and timestamps. Public results omit
the concrete identity and private state location.

If claim state is unreadable, identity cannot be resolved, or time validity is
uncertain, effectful use fails closed. Status and doctor remain available for
diagnosis. Claim operations return `claim_identity_unavailable` with an
inventory-repair and doctor remediation when the adapter lacks an exact pin.

## Workspace interaction

**Decision:** workspace allocation and usage claiming are related but not the
same ownership fact.

- Workspace acquisition atomically claims the selected or newly derived VM
  before returning it for use.
- Persistent acquisition refuses while another claim holds the development
  VM instead of returning its shared handle; the refusal includes the same
  public holder attribution and reason as claim status.
- Isolated and candidate acquisition returns both the workspace handle and
  its claim descriptor.
- Workspace release requires the matching live claim. It relinquishes the
  claim after the adapter has safely retained or discarded the workspace.
- Releasing a target-use claim alone never deletes, stops, or reverts a VM.
- A bounded caller that starts an initially off or suspended persistent target
  owns its routine clean shutdown before claim release unless the task declares
  that it should remain running. A caller that inherits a running target does
  not silently stop it. Failed cleanup is reported and leaves the target for
  diagnosis rather than escalating to a materially different transition.
- Claim expiry releases exclusivity but does not guess whether a temporary VM
  is safe to destroy. Receipt-bound cleanup remains explicit or pending.

## Enforcement boundary

The common client provides discoverability and typed refusals, while the
authoritative adapter rechecks the claim against exact private identity. A
client-side flag alone is insufficient. Platform-native escape hatches also
require a claim for effectful commands when claim policy is enabled.

Arbitrary direct use of a hypervisor CLI, an unrestricted shell, or a resident
binary outside the governed interface is not prevented. Stronger separation
requires a different OS identity, sandbox, or authorization service outside
the agent's authority.

## Current implementation

**Current:** `bin/machine-control` projects claim policy in target inventory,
exposes capabilities/status/acquire/check/renew/release, accepts generic
self-asserted caller metadata, and requires `--claim` before meaningful VM
operations. `claim --help` and `workspace --help` expose the full workflow
without assuming a particular coordinator.

**Current:** the Windows and Linux UTM adapters and macOS Tart adapter bind the
shared claim authority to their existing exact private UUID/name pins. Private
records live beneath platform workspace state by default. The adapter checks
the selected claim again immediately before dispatch, so bypassing the common
client does not accidentally bypass cooperative coordination.

**Current:** persistent and isolated workspace acquisition claims the selected
resource before it starts. Candidate derivation temporarily claims its stopped
source, claims the exact derivative before starting it, then returns the
derivative's public claim descriptor. Release checks the receipt's exact target
before retain/discard work and releases the claim afterward.

**Current:** claim-free target status and doctor preserve inventory repair and
readiness diagnosis. The Windows native `target-id` and `pin-target` commands
also remain available for initial private identity bootstrap; ordinary use
must wait for an exact pin and live claim, with `ensure-ready` providing the
explicit path from an off target to a passing doctor. Physical-device adapters
remain outside the initial policy pending target-specific contention decisions.

## Validation requirements

Conformance must prove:

- two simultaneous acquisitions yield exactly one holder;
- aliases and workspace handles bind to the exact resource identity;
- holder information, reason, assurance, and remaining time are visible;
- renewal cannot exceed policy and a stale claim cannot renew;
- expiry permits a new generation and rejects the former holder;
- release is idempotent without releasing a newer holder;
- required operations refuse before target dispatch without a live claim;
- claim-free diagnostics remain read-only and available; and
- workspace acquisition, use, and release preserve separate cleanup
  ownership.

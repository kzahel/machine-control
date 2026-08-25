# Target-Use Claim Store

This provider-neutral helper owns private, atomic, expiring exclusive-use
claims for exact machine-control resources. Authoritative platform adapters
resolve a logical alias or workspace handle to a concrete provider identity
before calling it.

The store keeps one private record per exact resource. Each record retains the
fencing generation after release or expiry so a later claimant receives a
higher generation. Public results expose claimant attribution, reason, timing,
and generation without exposing the provider identity or state path.

Claims coordinate cooperative callers. Self-asserted authority, claimant,
session, label, and metadata fields are attribution rather than authentication.
An unrestricted process with the same shell or direct provider access remains
outside this coordination boundary.

Every claim also records a use class. `ordinary` is the safe default for
lifecycle, administration, and target-native control. Callers must acquire
with `--disruptive` before an authoritative VM adapter will dispatch
host-visible capture or host-injected input. This class remains separate from
the claim's exclusive mode. Legacy active records load as ordinary.

See [`target-use-claims.md`](../../topics/target-use-claims.md) for the common
contract and enforcement policy.

Callers normally use `bin/machine-control`, not this helper. The accepted VM
adapters expose the shared `claim-capabilities`, `claim-status`,
`claim-acquire`, `claim-check`, `claim-renew`, and `claim-release` commands and
bind them to their exact private UTM or Tart identity. Claim state defaults to
a private `claims` directory beneath platform workspace state; ignored local
configuration may move it without changing the public target contract.

The common client provides a typed preflight for known outer commands, and the
Windows, Linux, and macOS VM wrappers perform the authoritative class-aware
check again. An ordinary holder receives `disruptive_claim_required` before
the outer provider is dispatched. An adapter's absolute outer-UI prohibition
remains stronger than a disruptive claim.

Workspace providers use the same authority. Acquisition temporarily protects
a derivation source when necessary, claims the exact returned workspace before
starting it, and includes the public claim descriptor in the workspace result.
Release checks the receipt target against the selected claim before any
retain/discard action and releases the claim only after that action is safe.

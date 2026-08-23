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

See [`target-use-claims.md`](../../topics/target-use-claims.md) for the common
contract and enforcement policy.

# Durable target claim and command history

Status: completed for the controller source slice.
Owning topics: [target operation audit](../../topics/target-operation-audit.md),
[target-use claims](../../topics/target-use-claims.md) and
[desktop audit](../../topics/desktop-audit-and-diagnostics.md).

## Objective and completion conditions

The user asked who claimed and used a VM, what commands ran, and why existing
logging could not answer across later agent sessions. A past retirement record
was mistaken for a complete recent history. Add a durable joined timeline that
survives release, replacement and target retirement, without logging secrets.

Complete the controller slice when source tests prove exact-resource/alias and
replacement correlation, retained claimant attribution, command outcomes,
restart/pagination, privacy, concurrency, retention and safe logging failures.
Package the module for the installed CLI and prove a read-only local journal
round trip. Do not claim retroactive history or signed app update acceptance.

## Boundaries and ordered work

1. Keep ownership/fencing in the existing shared claim authority. Journal its
   state transitions, including live queue terminal reasons, independently of
   mutable pins. Preserve cleanup during journal failures.
2. Record common CLI intent before dispatch and result afterward, with bounded
   known grammar only. Persist scoped task summaries and retain delivery,
   effect and uncertainty separately from process exit. Never replay a result
   whose logging failed.
3. Add offline history queries and a bounded private store, claimant/claim/target
   filters, pagination and explicit coverage limitations. Resolve retired
   aliases from journal rows rather than current inventory.
4. Qualify source fixtures and packaging; run a read-only source CLI round trip.
   Record historical uncertainty honestly and leave independent resident,
   provider, direct shell and remote-controller history distinguished.

## Validation and result

**Current:** 194 client tests, 35 claim tests and 6 CLI packaging tests pass.
The client suite includes 14 focused history checks: multi-process writers,
restart/pagination, target/claim/claimant correlation, alias and replacement
identity, release/renewal, payload omissions, private storage/link refusals,
retention, unpaired intent, unavailable intent and result-write failure without
replay. Claim fixtures additionally verify observed expiry and queued owner's
actual heartbeat termination reason. Existing fencing and transport tests pass.

The complete `bin/check --portable` passes, including platform/provider fixtures,
tracked JSON and Bash syntax, indicator lifecycle and whitespace. Test runners
and affected fixtures select isolated private journals rather than polluting
operator history. A read-only source CLI capability call writes intent/result;
a separate offline query reads them and reports incomplete coverage. The retained
signed application's bundled Python runtime also passes a SQLite journal write
and read round trip using the source module in an isolated directory. The new history
schema validates both the actual read-only source output and fixture claim
lifecycle/command correlation with local contract references.

No VM creation, password change, identity repair or lifecycle mutation occurs.
The installed payload source list includes the module. This does not qualify a
signed updated application, every controller filesystem or Windows live runtime,
authenticated agent identity, all direct shell/provider use or retrospective
history. Existing resident and provider audit evidence remains separate.

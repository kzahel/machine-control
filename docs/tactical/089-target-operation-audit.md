# Durable target claim and command history

Status: implementation and validation in progress.
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

Pending final source and local read-only validation. No VM creation, password
change, identity repair or lifecycle mutation is required for this slice.

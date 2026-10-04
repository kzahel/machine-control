# Target operation audit

Topic: `target-operation-audit`

Status: controller journal implemented and source validated; read-only local
and bundled-runtime round trips pass. Signed installed adoption is not qualified.

## Scope and current gap

This topic owns durable attribution and operation history for cooperative
target claims and the common CLI. It complements
[desktop audit](desktop-audit-and-diagnostics.md), which records resident
operations and grants, and [target-use claims](target-use-claims.md), which owns
arbitration. Provider diagnostics own their provider's subprocess failures.

**Current:** Before this slice, released claim records retained a fencing
generation but not the former claimant or command history. Scoped runs emitted
minimized records to stderr; retaining the calling agent's transcript was the
only way to recover them later. Desktop and provider history did not form a
joined target-use timeline. Finding one historical retirement cannot prove
that no later agent created or used a replacement target.

## Decision and implemented contract

**Decision:** Keep a private controller-local journal, independent of mutable
target pins and installation directories. Record authoritative claim state
transitions and common CLI command intent/results. Join by claim ID and an
opaque digest of the exact provider/resource identity; aliases do not create
different resources, while a replacement VM does. Preserve claimant namespace,
ID, optional session/label, reason, use class and generation after release.

**Current:** The shared claim writer journals acquire, renew, release and
observed expiry, including queue-owned terminal reasons. The common CLI records
known command grammar, target alias, claim selector, controller PID, correlation,
duration, exit status and available acceptance/delivery/effect/uncertainty.
Scoped run acquisition and final cleanup summaries are persisted too.

**Decision:** Attribute a command to the selected claim holder without claiming
that its self-asserted agent label authenticates the process that ran it. The
controller PID is an observation; neither PID nor a claim ID proves an agent's
authenticated identity. Do not log command arguments, shell/program bodies,
typed text, paths to secrets, stdin, environment, output or request payloads.
Caller attribution and reasons must themselves contain no secrets, as required
by the claim contract.

**Current:** `audit history` reads offline, including after a target's inventory
pin is removed. Filters select logical target, claim, claimant and UTC start;
bounded pages expose the next cursor and coverage/retention limits. Missing
results have unknown outcome. New common CLI work refuses if intent cannot be
persisted. Release, shutdown and revocation continue with visible best-effort
logging. Result persistence failure returns nonzero without replay. Claim store
state transitions continue with a warning if the journal fails: logging must
never strand ownership or alter fencing.

## Evidence and limits

[Tactical 089](../docs/tactical/089-target-operation-audit.md) owns validation.
[The operator guide](../docs/target-operation-audit.md) owns locations, query
examples and privacy. The installed CLI payload includes the journal module;
an already installed older bundle needs an ordinary update to participate.

**Open:** Historical transcript reconstruction is not authoritative runtime
history. This journal cannot recreate activity before its introduction. Direct
provider or unrestricted shell calls outside the common CLI are not captured
as common command events; shared claim transitions still participate. SDK/live
resident primitives retain their separate resident history rather than claiming
one row per primitive here. Remote controllers have their own local journals.
Same-user edits, deletion, retention and write failures can create coverage
gaps; the query never asserts completeness. Resident/provider correlation,
operator UI integration and authenticated agent identity remain separate work.

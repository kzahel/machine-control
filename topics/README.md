# Topics

Focused, living records of continuing machine-control concerns live here.

Prefer the smallest coherent topic whose status, decisions, evidence, gaps, and
next direction benefit from continuity across sessions or commits. Split topics
when their decisions or next work can evolve independently. Do not create a
topic for every small standalone change.

Documentation roles:

- Root architecture and reference documents own the durable project shape,
  vocabulary, ownership boundaries, and North Star.
- Topic documents own current truth, decisions, evidence, gaps, and direction
  for a focused continuing concern.
- Tactical documents under [`docs/tactical/`](../docs/tactical/README.md) own
  bounded implementation slices and their execution records.
- [`machine-control-spike`](../../machine-control-spike/README.md) owns exact
  experiment evidence and third-party source pins.

New topics should normally begin with a crisp scope, a `Topic: <slug>` line,
and an honest status. Add only the sections the concern needs, such as current
state, decisions, invariants, evidence, gaps, or recommended next work. When a
commit series implements the same concern, normally reuse the document slug in
its `Topic:` trailers.

## Current topics

- [`architecture.md`](architecture.md): target-native component, trust,
  deployment-profile, facade, and failure-boundary decisions.
- [`capabilities-and-results.md`](capabilities-and-results.md): common
  capability, observation, action, uncertainty, and conformance vocabulary.
- [`delegation-and-agent-placement.md`](delegation-and-agent-placement.md): YA
  coordination and the separation between agent placement and control target.
- [`inner-first-routing.md`](inner-first-routing.md): ordinary resident routes,
  explicit outer recovery, and host-interference policy.
- [`platform-notes.md`](platform-notes.md): current native foundations and gaps
  across desktop, mobile, headset, VM, and physical targets.
- [`windows-resident-control.md`](windows-resident-control.md): current Windows
  proving-ground decisions, unresolved boundaries, and next implementation
  direction.

## Update policy

- Read the relevant topic before changing the concern it governs.
- Update it when work changes current status, a decision, evidence, validation,
  a known gap, or the recommended direction.
- Keep the main text as current truth rather than an append-only diary. Git and
  motivation-preserving commit bodies retain history.
- Keep per-step execution detail in `docs/tactical/` and topics concise enough
  to scan.
- Link authoritative repositories and evidence rather than copying their
  detailed logs into this repository.
- Create a sibling topic rather than broadening an existing one into a
  catch-all.

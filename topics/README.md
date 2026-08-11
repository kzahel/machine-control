# Topics

Focused, living records of continuing machine-control concerns live here.

Prefer the smallest coherent topic whose status, decisions, evidence, gaps, and
next direction benefit from continuity across sessions or commits. Split topics
when their decisions or next work can evolve independently. Do not create a
topic for every small standalone change.

Documentation roles:

- Root architecture and reference documents own the durable project shape,
  vocabulary, ownership boundaries, and North Star.
- [`research/`](../research/README.md) owns the two-axis evidence corpus:
  provider dossiers for architectural breadth and platform reports for
  operating-system depth.
- Topic documents own current truth, decisions, evidence, gaps, and direction
  for a focused continuing concern. They link to research rather than
  duplicating provider or platform dossiers.
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

- [`architecture.md`](architecture.md): target-native component, provisional
  provider composition, fork/replacement gates, trust, deployment-profile,
  facade, and failure-boundary decisions.
- [`android-family-control.md`](android-family-control.md): shared ADB provider
  primitives, distinct Android-handheld and Quest profiles, protected phone
  unlock, evidence, and remaining semantic/profile work.
- [`capabilities-and-results.md`](capabilities-and-results.md): common
  capability, observation, action, uncertainty, and conformance vocabulary.
- [`cross-platform-coordinator.md`](cross-platform-coordinator.md): portable
  macOS/Linux/Windows coordination, controller-route eligibility, launchers,
  and target-native validation.
- [`delegation-and-agent-placement.md`](delegation-and-agent-placement.md): YA
  coordination and the separation between agent placement and control target.
- [`inner-first-routing.md`](inner-first-routing.md): ordinary resident routes,
  explicit outer recovery, and host-interference policy.
- [`ios-device-control.md`](ios-device-control.md): adopted CoreDevice/XCTest
  physical-device control, common readiness, protected-authentication
  boundaries, and unattended reboot evidence.
- [`linux-resident-control.md`](linux-resident-control.md): accepted Ubuntu
  GNOME Wayland logged-in appliance and remaining compositor, portal,
  protected-plane, and physical-hardware profiles.
- [`macos-resident-control.md`](macos-resident-control.md): current macOS
  resident implementation and the active full logged-in Aqua Tart
  software-testing milestone with outer UI prohibited.
- [`platform-notes.md`](platform-notes.md): current decisions across desktop,
  mobile, headset, VM, and physical targets.
- [`provider-landscape.md`](provider-landscape.md): cross-provider decisions,
  common-spine direction, exact-window requirements, and validation shortlist.
- [`repository-consolidation-and-publication.md`](repository-consolidation-and-publication.md):
  canonical public implementation, private inventory, history-preserving
  platform imports, atomic cutover, and optional generated testbed
  distributions.
- [`target-lifecycle-and-readiness.md`](target-lifecycle-and-readiness.md):
  common target selection, lifecycle verbs, machine-readable doctor state, and
  authoritative-testbed boundaries.
- [`unified-desktop-client.md`](unified-desktop-client.md): common resident
  entry points, transports, artifacts, operation translation, conformance, and
  explicit platform escape hatches.
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
- Update a provider dossier or platform report before changing a topic when new
  evidence is what changed the decision.
- Create a sibling topic rather than broadening an existing one into a
  catch-all.

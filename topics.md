# Commit Topics

Registry of topic strings used in `Topic:` commit trailers. This is not an
index of [`topics/`](topics/README.md), although a series normally reuses the
owning topic document's slug.

Append a topic when its first commit is created. Keep the string exact across
the series so `git log --grep "Topic: ..."` finds the whole chain. Standalone
commits with no expected follow-up do not need a trailer or registry entry.

- `architecture` — target-native component boundaries, provisional provider
  composition, trust, deployment profiles, facade ownership, and replacement
  gates.
- `windows-resident-control` — Windows target-resident facade, system-shell
  acceptance, local/remote parity, recovery, and reproducible appliance proof.
- `macos-resident-control` — macOS target-resident facade, native provider
  composition, local/remote parity, TCC identity, and Tart appliance proof.
- `linux-resident-control` — Ubuntu GNOME Wayland resident facade, target-local
  capture/input, and logged-in software-testing coverage.
- `capabilities-and-results` — common capability, route, delivery, effect,
  uncertainty, reference, lease, and lifecycle result vocabulary.
- `provider-landscape` — common-provider versus platform-depth decisions,
  exact-window requirements, fixture design, and evidence-driven selection.
- `target-lifecycle-and-readiness` — logical target selection, portable
  lifecycle verbs, normalized doctor state, and authoritative testbed adapters.
- `target-use-claims` — coordinator-neutral exclusive target-use leases,
  claimant attribution, expiry, renewal, exact-resource binding, and fencing.
- `vm-workspaces-and-storage-policy` — persistent, isolated, and candidate VM
  workspace intent; provider-selected derivation; storage budgets; and safe
  receipt-bound cleanup.
- `unified-desktop-client` — common desktop entry points, operation
  translation, bounded artifacts, conformance, and explicit escape hatches.
- `repository-consolidation-and-publication` — canonical public platform
  sources, private inventory, history-preserving imports, atomic cutover, and
  optional generated testbed distributions.
- `cross-platform-coordinator` — macOS/Linux/Windows common-client portability,
  controller-route eligibility, portable launchers, and target-native CI.
- `android-family-control` — shared ADB provider primitives, Android-handheld
  profile and protected credential operation, and distinct Quest policy.
- `ios-device-control` — CoreDevice/XCTest common readiness, lifecycle,
  protected-authentication boundaries, and unattended recovery evidence.

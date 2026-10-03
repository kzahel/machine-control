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
- `inner-first-routing` — ordinary target-native control, explicit disruptive
  outer recovery, host-interference policy, and route authorization.
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
- `platform-notes` — current platform-specific control routes, readiness
  posture, limitations, and next integration direction.
- `native-distribution` — optional native packages, publisher signing,
  independent package authenticity, release CI, and consumer integration.
- `windows-protected-unlock` — optional Windows unlock service, elevated
  administrator arming, controller authorization and credential transport.
- `operational-workflow-automation` — staged agent-driven setup, recovery,
  claims, validation, and release workflows that replace prose-only decisions.
- `host-control` — physical and personal hosts, deployment presets, grant
  broker and approvers, menu bar application, and attended-away operation.
- `browser-control` — user-browser control through a Machine Control
  extension, native messaging, and grant-scoped CDP.
- `windows-desktop` — shared Tauri Windows operator, resident grants,
  companion supervision, signed installers, and installed acceptance.
- `linux-desktop` — ordinary-user Linux Tauri app, portal consent, grants,
  native approvals, packages, and installed GNOME acceptance.

- `native-sudo` — native per-command macOS authentication, helper packaging and YA opt-in.

- `installed-agent-cli` — bundled Python client, offline instructions and verified desktop consumers.

- `desktop-audit-and-diagnostics` — durable desktop history, private diagnostics,
  failure handling, operator inspection, and cross-platform validation.

- `caller-authorization` — authenticated callers, trusted integration grants,
  session revocation and native identity validation.

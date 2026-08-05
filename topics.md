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
- `provider-landscape` — common-provider versus platform-depth decisions,
  exact-window requirements, fixture design, and evidence-driven selection.

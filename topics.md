# Commit Topics

Registry of topic strings used in `Topic:` commit trailers. This is not an
index of [`topics/`](topics/README.md), although a series normally reuses the
owning topic document's slug.

Append a topic when its first commit is created. Keep the string exact across
the series so `git log --grep "Topic: ..."` finds the whole chain. Standalone
commits with no expected follow-up do not need a trailer or registry entry.

- `windows-resident-control` — Windows target-resident facade, system-shell
  acceptance, local/remote parity, recovery, and reproducible appliance proof.

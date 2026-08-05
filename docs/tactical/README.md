# Implementation Tacticals

Bounded implementation plans and execution records live here.

Tacticals are selected from current [`topics/`](../../topics/README.md) and
should link the relevant [provider/platform research](../../research/README.md)
rather than embedding another candidate survey or experiment log.

Use zero-padded numeric prefixes for new tactical documents, such as
`000-topic.md` and `001-next-topic.md`. Keep one coherent implementation slice
per document. A coordinating parent tactical is acceptable when it makes the
ordering of several independently reviewable slices explicit.

Every tactical should identify:

- status: `proposed`, `active`, `blocked`, `complete`, or `superseded`;
- the owning topic or topics;
- objective and observable completion conditions;
- boundaries and explicit non-goals;
- named implementation steps in recommended order;
- validation and evidence requirements; and
- the result, deviations, and remaining work when execution ends.

Name steps for the product surface or work they cover, using headings such as
`### 3 — prove remote direct control`. Do not invent letter-and-number lane
codes that require a separate lookup table. If a step is difficult to name,
its boundary probably needs more work.

Completed tacticals remain as execution records. Continuing guidance belongs
in the owning topic and architecture documents; if they disagree with an old
tactical, update the tactical's status or add a short supersession note rather
than treating its historical plan as current truth.

When a tactical produces a related commit series, use the owning topic slug in
the commits' `Topic:` trailers and register that exact string in
[`topics.md`](../../topics.md) when the first commit is created.

## Tactical index

| Tactical | Status | Scope |
| --- | --- | --- |
| [`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md) | active | First complete local-and-remote Windows proof of the target-native contract |
| [`001-windows-system-shell-acceptance.md`](001-windows-system-shell-acceptance.md) | active | Cua-first acceptance run across the real Windows system shell |

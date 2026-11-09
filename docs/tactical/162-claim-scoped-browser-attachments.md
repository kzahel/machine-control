# 162 — Claim-scoped browser attachments

Owning topics: [browser-control](../../topics/browser-control.md),
[target-use-claims](../../topics/target-use-claims.md).

Status: **complete; awaiting extension and desktop release.**

## Objective

A browser debugger attachment and its tab marker outlived the agent that
made them. The extension released tabs only on `browser release`, a grant
change, or a native disconnect. Ending a claim told it nothing.

In the incident that prompted this, an agent read a verification code from
one of the operator's own tabs. It then released its claim twice and closed
its own tab, but never ran `browser release`. Chrome kept the debugging bar up and the tab
kept the blue pointer for as long as access stayed on. The resident audit log
recorded only `callerPid`, so finding the agent took a transcript search.

The operator asked to record **exactly enough** to release the debugger
automatically once the claim that attached it has gone away, and to show who
attached a tab. Snapshot references must not go stale more often than they
do today.

## Rejected alternatives

- **Release when a control session ends.** A one-shot CLI command opens and
  closes its own control session within a second. Releasing then would detach
  after every command, bump the tab generation, and flash Chrome's debugging
  bar.
- **A short idle timer in the extension.** It would cut tabs out from under a
  live claim during an agent's pause.

The claim is the right unit. It spans a whole task, it already has an expiry,
and agents already release it at the end.

## Contract

**Decision:** browser requests may carry an `owner` object:

```json
{"claimId": "c-<24 hex>", "leaseSeconds": 1800, "sessionRef": "<agent session>"}
```

- `claimId` is the claim the caller selected and the client verified with
  `claim-check` for this request.
- `leaseSeconds` is that claim's remaining time when the request was sent. It
  is relative so that controller and guest clocks need not agree.
- `sessionRef`, when known, is the caller's own published agent session
  (`AGENTCTL_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`, `CODEX_THREAD_ID`).

The owner is self-asserted attribution plus a lifetime hint. It is not
authority. An absent or null owner keeps today's behavior.

`browser.release` may carry `ownerClaimId`. It then marks that claim ended and
releases only tabs whose current owner is that claim. Observed dialogs on
those tabs are abandoned and reported rather than blocking, because nobody
remains to handle them. A tab still serving a live DevTools stream or an
in-flight request is kept, reported, and released once idle. Without
`ownerClaimId`, release keeps its existing all-tabs behavior.

**Decision:** the extension owns ownership state:

- A tab's owner is the owner of the latest request that attached or reused it.
  A request without an owner clears the owner of a tab it uses.
- Each accepted request carrying an owner refreshes that claim's deadline to
  the time it arrived plus `leaseSeconds`. A request refused before it runs
  refreshes nothing.
  A request that arrived before its claim ended cannot revive the claim.
- Every three seconds, the worker releases tabs of an ended claim once they
  are idle, and tabs whose claim deadline passed more than 30 seconds ago.
  Releasing restores the marker and detaches the debugger, and the panel
  records it. A late attachment by a request already in flight joins its ended
  claim and is released too.
- While a tab is being released, a new request for it is refused before
  dispatch (`browser_tab_releasing`) instead of being detached underneath it.
- `browser.tabs` and other tab results report `controlOwner` (claim, session,
  whether the claim ended, remaining lease) or `null`. The side panel shows
  the claim, the session and when each tab will be released.

**Decision:** the client stamps and cleans up:

- For every `browser.*` request except `browser.profiles`, `browser.release`
  and `browser.endpoint`, the client adds `owner` from the claim it has just
  verified. One-shot
  commands use their per-command check. Control sessions and streams recheck
  the claim before every dispatch and use that result.
- The first owned request in a process records a `browser.owner` event for
  that claim in the controller audit history.
- `claim release`, `workspace release`, scoped `run` cleanup and closing a
  queued `ClaimSession` first send `browser.release` with `ownerClaimId`, but
  only when history shows a `browser.owner` event for that claim. This is best
  effort: a failure is reported in the result and never blocks releasing the
  claim.
- `claim renew`, scoped `run` renewal and `ClaimSession.renew` send one owned
  `browser.tabs` under the same condition, so a renewed lease reaches the tabs
  even when the claim makes no other browser request.
- Housekeeping never waits on a person or another owner. It reads resident
  status first and skips under Ask first. It cancels any intent that is not
  offered or active within three seconds. The result reports why it was
  skipped.

**Decision:** relays carry the fields unchanged. The macOS and Linux relays
already forward request objects intact. The Windows typed request gains
`owner` and `ownerClaimId`. The shared runtime validates both shapes and
refuses malformed values as `invalid_request` before dispatch.

## Boundaries

- No resident journal schema change. The controller history already links
  claim, session and command. The extension's per-tab owner covers live
  attribution.
- No new operation, admission entry or notice. `browser.release` and
  `browser.tabs` are already background operations.
- **Open limit:** housekeeping is skipped under Ask first or while another
  owner, such as the agent's own Browser control stream, holds the profile.
  Then an ended claim's tabs wait for the lease, and a renewed claim that
  makes no browser request before its previous lease lapses loses its tabs 30
  seconds after that lease. The next request reattaches with fresh
  references.
- **Open limit:** status does not report a Browser approval still required
  after an earlier Hold. Housekeeping then opens an intent and cancels it at
  the first check, so the approval prompt can appear for a moment.
- **Open limit:** scoped `run` refreshes the lease inside its monitoring loop.
  A refresh that waits out its three seconds, for example while the run's own
  child holds the profile, delays noticing a child exit by that long.
- A guessed or replayed claim ID can scope a release only to tabs that the
  same claim attached. Like global release, it never grants control.
- The persistent desktop agent session (`mcp`) opens Desktop only and is
  unchanged.
- Existing ten-second page expiry, grant/disconnect cleanup and worker
  recovery stay as they are.

## Ordered work

### 1 — validate and carry the owner through the shared runtime and relays

Validate `owner` and `ownerClaimId` in the policy host. Add both fields to the
Windows request contract. Prove pass-through and refusal.

### 2 — track owners, scoped release and expiry in the extension

Owner bookkeeping, `ownerClaimId` release, expiry sweep, `controlOwner` in tab
results, and the panel owner line.

### 3 — stamp owners and release on claim end in the client

Owner stamping in one-shot and control-session paths, the audit event, the
release hooks in `claim release`, `workspace release`, `run` and
`ClaimSession`, and the renewal hooks.

### 4 — documentation

Extension README contract, extension and desktop changelogs, topic current
truth, and the tactical index.

## Validation

- `python bin/check --portable`, which covers client unit tests, runtime policy
  tests and extension worker tests.
- `pnpm --dir runtime check` for strict TypeScript.
- `dotnet format --verify-no-changes`, Windows ARM64 and x64 builds of the
  resident, and the contract fixture that proves the typed request keeps both
  fields.
- Relay pass-through: the macOS `BrowserRelayTests` shared-call case and
  `tests/desktop/test_linux_browser_deadline.py`.
- An independent read-only review through YepAnywhere before commit.

## Result

Implemented across the client, shared runtime, Windows contract and
extension. macOS and Linux relays needed no change; tests now prove that
they carry both fields. An independent read-only review requested changes on
the first pass: leases deleted under late attachments, retained tabs held to
the full lease, reuse during a release, housekeeping that could prompt or
wait, workspace release and renewal paths, and refresh ordering. The second
pass approved. Its remaining notes are fixed (recovery requests now keep
their tab) or recorded above as open limits.

The behavior ships with the next extension and desktop releases; no live
installed-browser acceptance has run yet.

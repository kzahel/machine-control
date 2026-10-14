# 120 — Person-armed access retention

Status: active. Decision recorded; macOS implementation in progress;
Windows and Linux pending.
Owning topic: [host control](../../topics/host-control.md#person-armed-access-is-the-persons-to-end).

## Objective and completion conditions

A comparison agent ran `grant revoke` at the end of its task, as the host
skill then instructed, and silently disarmed access the operator had turned
on until stopped. On Mac the saved consent was deleted, so the access did not
return. The operator asked that indefinitely armed access be hard to disable
accidentally: only an explicit, clearly intended action by the person should
end it.

Complete when, on Mac, Windows and Linux:

- a caller's revoke leaves person-armed access and its saved state intact and
  reports that it was retained;
- a caller's revoke still ends a timed grant from an approved agent request;
- ending a request grant never deletes the person's saved arming; and
- the person's own Stop still ends everything immediately.

## Boundaries

Grant scopes, approval prompts, durations, locking, pause and policy presets
are unchanged. This does not contain a deliberate same-user agent. Agent
request grants remain target-wide.

## Ordered work

### 1 — macOS resident

- Record `origin` (`person` or `request`) on every grant: app and menu
  arming and restored consent are `person`; approved requests are `request`.
  Report it in grant JSON.
- `grant.revoke` from the socket: for a `person` grant, journal
  `access.revoke_retained` and answer `revoked: false`,
  `retained: "person_armed"`; for a `request` grant, end it with
  `revoked_by_caller`. Never suspend trusted callers from a caller revoke.
- Saved consent is cleared only by the person's Stop reasons or by the end of
  a `person` grant for a reason that already cleared it. Caller revocation and
  the end of a `request` grant keep it, so the person's arming is restored
  on the next reconciliation.
- Swift tests at broker, consent and real-socket server level.

### 2 — Windows resident

Same contract in `UserHost` grants. Windows has no restart persistence, so
the retained in-memory grant is the state to protect.

### 3 — Linux companion

Confirm the revoke path, then apply the same contract.

### 4 — visibility and resident stop

Notify the person when access ends for a non-person reason; refuse
`server.stop` from ordinary socket callers on personal hosts.

## Validation

Per platform: unit/contract tests, then an installed check in which the
person arms until stopped, a CLI `grant revoke` reports retained access,
capture still works, an approved request grant can be revoked, the person's
access returns, and Stop ends it. Mac also checks lock/unlock and restart.

## Final result

Pending.

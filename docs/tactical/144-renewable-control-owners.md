# Renew live control owners under existing approval

Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[Mac locked use](../../topics/macos-locked-use.md).
Parent: [desktop reliability plan](141-desktop-control-reliability-plan.md).

Status: **complete** for the documented Mac VM profile and negotiated clients;
the parent owns composed cold-boot acceptance and release eligibility.

## Objective and policy

**Decision:** a 900-second finite lease need not be a universal task cutoff.
Permit typed renewal of the same live owner under the original authorization.
The selected grant determines the total access lifetime: timed approval does
not restart, and Until I turn it off permits continued authorized work until
Stop, task completion, loss of ownership, or a safety condition ends it.

Capture timed authorization's monotonic ceiling when accepting the owner so a
wall-clock rollback cannot enlarge renewal. Pin the grant identity. Heartbeat,
claim renewal, lease renewal and approval remain distinct. An ended owner is
never reopened or replayed automatically.

## Completion conditions and boundaries

- Renewal binds the live connection, session and resource generations.
- All protected layers acknowledge a finite extension before admission commits.
  Missing/late acknowledgement ends control and preserves relock/watchdogs.
- Stop, Pause, grant replacement/expiry, takeover, disconnect and helper loss
  cannot be overcome by renewal. Root never revives an expired deadline.
- Only a supporting provider advertises owner-connection renewal. Delegated
  trust, outer routes, older helpers and other native platforms retain their
  existing contracts. Legacy finite `desktop session control` stays bounded.
- A packaged same-owner task crosses the old fifteen-minute task boundary,
  with independent effects, multiple root acknowledgements and final relock.

No new standing authorization, arbitrary privileged dispatch, automatic fresh
approval, or unbounded exposed-desktop unlock is introduced.

## Ordered work

### 1 — bind and negotiate renewal

Add `control.renew` with owner/session/generation fences and a 1–900-second
interval. Recheck approval and total deadline, journal intent/result, and
terminate on an uncertain protected handshake. Keep ordinary status passive.

### 2 — extend every protected deadline

Renew the resident lease, guardian and root deadline over existing private
channels. Root checks the old deadline, heartbeat, installation and guardian
before acknowledging; its independent watchdog remains finite. Advertise
covered renewal only when the actual helper supports it.

### 3 — expose and qualify supported clients

Provide explicit SDK renewal and opt-in `control stream --renew`. The persistent
agent facade may renew an advertised live owner under current approval; legacy
providers still expire locally. Failures close ownership, never retry input.
Run deterministic stale-owner, refusal, expiry, clock and cleanup tests, then
exact-package VM full-duration and multi-interval acceptance.

## Validation and current result

Focused native/channel tests pass connection/generation binding, Stop, timed
approval clamping, wall-clock rollback, late/failed acknowledgement and no
resurrection. An added concurrency regression first reproduced renewal being
refused during the same owner's pending provider action, then passed after
allowing that finite extension without a second dispatch or generation change.
Root inbox fixtures and native ARM64 helper build pass. Common
client tests pass typed renewal, refusal cleanup and legacy expiry. Live
protected renewal was then exercised in the full campaign below.

The first sustained packaged trial reached thirteen root acknowledgements
under unchanged ownership, then a native press was correctly refused after its
snapshot generation changed. Investigation reproduced renewal incrementing the
general admission revision, which the broker incorrectly treated as an
availability change and used to invalidate native work. A separate availability
revision now excludes successful timing-only renewal; its observable event/
revision remains. The regression fails before the fix and passes afterward,
including preserved provider epoch and a still-effective Pause fence. All 265
native tests passed at that step; the rebuilt candidate was qualified below.

## Final bounded VM result

The exact locally signed ARM64 development app passes 960 seconds of active
control under the same SDK, admission and covered owner, with unchanged
resource generations, 47 root-acknowledged renewals and independent effect
samples spanning 949.795 seconds. Clean context completion independently
relocks. A succeeding owner renews twice, then loss of its owned byte relay
fences control and independently relocks without reopening or replaying work.

The same 200-check campaign separately passes an actual 900-second finite
owner, Stop, protected watchdog/fault recovery and five planned restarts. Its
one-display Tart profile has SIP disabled; physical and SIP-enabled qualification
remain separate. Legacy finite commands and unsupported providers retain their
existing limits. No production package was published or primary app replaced.

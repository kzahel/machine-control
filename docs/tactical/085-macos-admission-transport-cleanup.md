# Mac admission transport cleanup

Status: completed for bounded cleanup, polling and protected task acceptance.
Owning topic: [access admission and pause](../../topics/access-admission-and-pause.md).

## Objective and completion conditions

Preserve standing consent when a healthy resident loses an agent connection,
while retaining independent guardian/root failure recovery. Queue polling must
not multiply expensive OS probes by waiter count. Interrupted pointer actions
must release the button they pressed before returning.

## Boundaries and ordered work

1. Distinguish admission client loss from resident/guardian heartbeat loss.
2. Keep status/heartbeat/cancel bounded; revalidate native availability before
   activation and every provider dispatch.
3. Observe permission/helper readiness once per status projection.
4. Preallocate pointer sequences and release owned buttons on cancellation.
5. Qualify fresh covered tasks and abrupt client loss with an independent
   fixture counter and native OS lock probe on an immutable signed candidate.

No password transport, protected policy, new OS permission or watchdog timing
is changed. A clean client ending still requires relock before covers are
removed. Same-user cooperation remains the advertised caller boundary.

## Validation and result

**Current:** all 126 Swift tests pass, including the client/guardian distinction.
Mac static smoke and source-native deployment/doctor pass. Admission inspections
still enforce their own clock/authority expiry. Activation/dispatch retain fresh
native checks; this is not a cache authorizing provider effects.

**Current, bounded physical trial:** an independent native probe observed the
initial programmatic lock. The prior installed candidate lost the first queue
response before delivering a fixture action. The resident later reported locked,
ready, healthy, no active session and no manual-recovery fault. Runtime sampling
showed repeated synchronous helper/permission probes in presentation and queue
polling. This is failure evidence, not covered-task acceptance.

**Current, bounded physical acceptance:** the immutable Developer ID signed
candidate installed at the existing test location after graceful native Quit.
The helper updated automatically, with readiness granted/healthy and no Repair
or additional OS consent. Two successive covered tasks each produced one
independent fixture increment, then independently observed OS relock, zero
covers and retained until-stopped consent. Two further tasks abruptly terminated
their own byte adapter and passed the same cleanup/consent checks. Every
activation used a distinct session. Snapshot/status measurements in the accepted
runs were 1.57–2.40 seconds. No password or personal browser was used.

**Limits:** one earlier attempt on the new candidate became stale after its
snapshot; the next traced and disconnect trials passed. These four successful
tasks are bounded evidence, not a claim of sustained-load acceptance. Actual
hardware takeover/local-use resumption and guardian/watchdog failure remain
separate gates in the parent plan. The opt-in runner never arms or installs
access and requires an independent native session probe and isolated fixture.

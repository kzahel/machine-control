# Mac locked quiet resumption

Status: source and policy fixtures complete; signed physical acceptance pending.
Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[Mac locked use](../../topics/macos-locked-use.md).

## Objective

Preserve valid consent after physical takeover while permitting a fresh task
when the same console is locked and quiet. An owner unlocking to work remains
protected. Keep watchdog failures distinct from ordinary pauses.

## Completion conditions and boundaries

Root owns the durable pause reason and independent quiet decision. Eligibility
requires exact console/boot/user identity, an independently observed lock,
healthy helper installation, at least 30 seconds since takeover and at least
30 seconds of HID idle. Unknown timing or idle fails closed. No existing finite
session, offer or unlock grant is restored. Existing awake/open-lid limits apply.
Operator Resume is a typed signed-resident operation absent from the public
resident JSON router; it clears only known physical/local-use pauses.
Same-user shell containment is not claimed.

## Ordered work and validation

1. Persist root pause reason and monotonic timestamp before relock.
2. Hold local-use episodes through owner unlock; clear only after re-lock/quiet
   or explicit operator Resume. Fault recovery retains its observed unlock rule.
3. Expose the reason and retain ordinary access across a known physical pause,
   including resident restart, without restoring an active session.
4. Compile helpers for both Mac architectures, exercise exact quiet boundaries,
   unknown/reversed clocks, missing observations and fault classification, and
   run the resident suites. Qualify a frozen signed physical candidate later.

## Result

**Current:** root policy fixtures pass; 99 resident tests pass on ARM64.
Both helper architectures compile. No helper was installed or physical lock
performed in this slice. The HID registry observation is conservative: synthetic
activity can delay quiet; it cannot establish physical takeover. The covered
HID event guard still supplies the takeover signal. Physical and distribution
acceptance remain pending under Tactical 074.

# Wake an idle display for covered Mac task startup

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: complete within the awake, open-lid physical acceptance scope.

## Objective

The physical idle-lock test retained the original ordinary approval, but the
next task failed with `unlock_display_unavailable`: locking had made the display
inactive while the OS and resident remained awake. A brief explicit native wake
restored readiness with the console still locked. Integrate that readiness step
into authorized task startup so idle display sleep needs no human wake action.

## Completion conditions

- Wake an inactive display only during approved covered-task startup.
- Bind wake and readiness to the same locked current-user console and open lid.
- Cancel on physical takeover, console change, closed lid or task deadline.
- Bound readiness wait and release the temporary assertion on every outcome.
- Preserve cover-before-unlock, input guard, root watchdog and Access checks.
- Prove an idle lock followed by successive tasks without external wake commands.

## Boundaries

No persistent power configuration, synthetic input, new OS permission, initial
helper setup, fresh login, system-sleep wake, closed-lid support or standing
sleep-prevention assertion. Status and doctor remain read-only. Failure retains
the existing Access-revocation policy; maintenance cannot regrant Access.

## Ordered work

### 1 — establish the physical readiness gap

Use the claimed native lock runner with one fixture whose process matches its
independent oracle. Verify the original approval survives idle lock. Observe
the refused task, then use an explicit short native display wake and observe
readiness while the OS remains locked. Stop the owned fixture and release the
claim before awaiting manual recovery.

### 2 — wake within authorized guardian startup

The signed guardian validates its inherited parent and bounded task request,
starts and arms its hardware guard, then uses
[`IOPMAssertionDeclareUserActivity`](https://developer.apple.com/documentation/iokit/1557127-iopmassertiondeclareuseractivity)
with remote activity. Active displays need no assertion. An inactive display
gets one assertion and at most three seconds for readiness, bounded further by
the task deadline. Every readiness check revalidates console identity, lock,
own UID, lid and cancellation. Release the assertion before installing covers
and arming the existing protected unlock flow. Do not renew it during tasks.

### 3 — validate and deploy

Exercise readiness, timeout, expiry, invalid console, closed lid, takeover,
console change and declaration failure with injected native dependencies.
Build ARM64 and Intel frameworks and sign the test candidate. Install only on
the unlocked idle console; the already approved helper should maintain itself
without Repair and preserve the now-enabled checkbox. Native Access re-enabling
remains necessary after app replacement. Run Tactical 070's repeated-task and
hardware-takeover cells with no external display-wake command.

## Validation and current result

**Current:** idle lock retained the original approval. The first already-locked
task refused with `unlock_display_unavailable`, leaving the OS locked, no active
task/covers and the helper healthy. Failure revoked Access. An explicit short
native display wake restored active/ready without unlocking; a subsequent
runner correctly refused the absent Access grant. No repeated-task success is
claimed from those trials. All 91 Swift tests pass, including nine wake tests.
ARM64 and Intel framework builds and deep strict verification of the signed
candidate pass. Python compilation and whitespace checks pass.
The runner now reports an owner that ends before startup immediately instead of
waiting for an unobservable session ID.

**Current:** after manual unlock, the signed candidate replaced the idle test
bundle. The existing approved helper refreshed automatically through installing
to idle/ready, with caller eligibility allowed, no setup error and the existing
enabled checkbox preserved. No native Repair click or new OS approval occurred;
ordinary Access remained off after app replacement.

**Current:** the installed revision completed two consecutive already-locked
tasks using the original ordinary approval, with no manual unlock, new approval
or external wake command between them. The first started with an inactive
display and unavailable unlock readiness; guardian startup restored the display
and reached covered control. Each cell required exactly one fixture, matching
semantic PID and independent file oracle, AX/pointer/keyboard effects, native
capture, independent IOKit relock, zero remaining covers and no manual-unlock
pause. Visual inspection of a private native capture showed the fixture beneath
the excluded covers. The initial completion run exposed a runner key mismatch
(`id` versus `grantId`); direct status proved approval had survived, and the
corrected runner then passed both cells without human recovery.

**Open:** Tactical 070's hardware takeover, additional OS versions, multiple
displays and distribution. Idle display wake is not full system-sleep support.

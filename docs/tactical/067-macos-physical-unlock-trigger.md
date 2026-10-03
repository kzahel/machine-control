# Physical Mac unlock trigger iteration

Owning topic: [macOS locked use](../../topics/macos-locked-use.md).

Status: bounded integrated completion trial passed; further acceptance in 070.

## Objective

Continue the physical trial without requiring the person to perform every
starting lock. Diagnose automatic covered unlock on a SIP-enabled Mac while
reusing the existing native helper approval and preserving manual recovery.

## Completion conditions

- Establish lock programmatically and independently observe the OS state.
- Retain typed broker arming, covers, hardware cancellation, bounded ownership,
  and ordinary password fallback while repairing the unlock trigger.
- Exercise covered native fixture effects and capture, then observe relock.
- Distinguish diagnostic trigger evidence from integrated product acceptance.
- Keep private identity, authentication logs, and captures outside the repository.

## Boundaries

Awake physical ARM64 macOS 26.6.2 with SIP enabled and an open lid. No password
read or submission, agent-side approval path, protection-policy weakening,
primary-browser test profile, or process-failure injection. The person owns
manual recovery and native operator controls. Doctor and exclusive claims
reserve the target; existing ordinary access separately authorizes control.

## Ordered work

### 1 — establish lock without an operator proxy

Add an explicit native test runner using the watchdog's measured lock primitive.
Bind the current user's console and poll IOKit for observed lock. Local live
acceptance accepts this runner through `--session-lock`; manual-lock mode stays
available. The programmatic physical lock succeeded. The original global Return
trigger still ended with `covered_unlock_not_observed`.

### 2 — identify and target the login process

Read-only diagnostics found that loginwindow was absent from NSWorkspace's
running-application inventory, despite a kernel-observed process and AX window.
The Touch ID entry view initially exposed no password field. Global Return did
not reveal one; Return posted to the verified loginwindow PID did.

The source revision resolves window owners and verifies the canonical system
executable, current UID, and process birth time. It posts only to that PID,
reveals the panel if needed, then requires one enabled focused password field
with the expected role and identifier before submitting Return. It reads only
identity/focus metadata, never the secure field's value. Every stage rechecks
the console, process identity, lock state, and hardware cancellation.

A bounded diagnostic used this trigger alongside the existing signed guardian
and its root broker. The diagnostic verified matching live signed parent/child
code and the guardian's cover before supplying input; it did not create or
extend unlock authority. OS logs recorded authorization plug-in evaluation and
an unlocked-session notification. The session immediately ended with
`display_changed` and relocked, before covered fixture/capture checks.

### 3 — distinguish notifications from display changes

The resident and guardian previously ended control on every AppKit screen
parameter notification. The source now compares display identity, bounds, and
scale instead. The guardian also requires every cover to remain visible and
opaque, and its periodic safety check still ends use on an actual layout or
cover-health mismatch. The integrated completion result is recorded below.

### 4 — prepare the integrated signed candidate

Compile the updated resident framework and sign the candidate without replacing
the running installation during a locked trial. Native Permissions Repair can
refresh an already approved daemon when a signed update changes the pinned
caller generation, then perform the existing fixed preparation. It does not
accept a caller-selected payload or manufacture macOS approval.

## Validation and current result

**Current:** programmatic physical lock passed. The targeted diagnostic trigger
caused plug-in evaluation and OS unlock, followed by immediate guard relock.
No covered application effect or capture was reached in that trial. The ending
state was locked with no control owner or covers, revoked access, and manual
unlock pause. Existing helper approval and the preference remained in place.

All 61 existing Swift tests passed after the source changes. The ARM64 framework
built, the Intel framework cross-build passed, and the staged Developer ID
candidate passed deep strict signature verification. The native lock runner
compiled; Python compilation, CLI help,
and whitespace checks passed. These build checks alone did not prove integrated
physical behavior or Intel execution.

The updated signed candidate was subsequently installed at the same test app
location after manual recovery. Accessibility and capture stayed ready, and
macOS helper approval remained granted. The old broker receipt rejected the new
caller generation, so native Permissions Repair is required before use.

The first native Repair attempt unregistered the helper but failed registration
with `Operation not permitted`. OS logs showed registration immediately after
unregistration. The synchronous API does not wait for the daemon to be reaped;
the repair path now waits for the asynchronous completion and a main-loop turn.
It retries only ServiceManagement's EPERM during that repair transition, at
half-second intervals for at most five seconds. Other errors and a required
operator approval are surfaced without retrying. Cancellation invalidates
pending callbacks. See [Apple's lifecycle explanation and acknowledged timing
issue](https://developer.apple.com/forums/thread/783539).

Seven lifecycle tests cover ordering, bounded transition retries, unrelated
failures, and cancellation. All 68 Swift tests passed. ARM64 and Intel framework
builds passed for the repair revision. Its signed candidate passed deep strict
verification and replaced the running test bundle while the console was
unlocked and no control session or covers were active. The person then used
native Set up successfully. Read-only status confirmed helper approval granted,
healthy installation, allowed caller generation, completed capture preparation,
and no setup error. Ordinary access was separately enabled. The repair leaves
the locked-use preference off until the person enables it again.

After the person enabled the preference and ordinary access, the integrated
physical completion runner passed: programmatic OS lock, automatic covered
unlock, AX button effect, pointer effect, keyboard effect, filtered PNG capture,
and completion relock confirmed through an independent IOKit probe. Ending
status reported `completed`, no owner or covers, healthy helper, and no manual
unlock pause. This used the product trigger and guardian without the external
diagnostic trigger.

The runner's independent fixture file recorded the expected counter/key effects.
Cleanup found two task-owned fixture processes. The next runner revision requires
exactly one fixture and pins both semantic control and its oracle to that PID;
repeat effects under that stronger attribution check before conformance promotion.

Ordinary approval was revoked on clean relock despite the retained opt-in. Idle
locking without a task has the same gap. [Tactical
070](070-macos-locked-access-retention.md) owns approval retention, repeated
tasks starting locked, and hardware takeover. This one completion cell does not
qualify those cells, multiple displays, Intel execution or distribution.

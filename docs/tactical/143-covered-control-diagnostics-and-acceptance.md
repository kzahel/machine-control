# Diagnose and qualify covered desktop control

Owning topics: [Mac locked use](../../topics/macos-locked-use.md),
[Mac resident control](../../topics/macos-resident-control.md),
[desktop diagnostics](../../topics/desktop-audit-and-diagnostics.md).
Parent: [desktop reliability plan](141-desktop-control-reliability-plan.md).

Status: **complete** for the bounded protected Mac VM campaign. The parent owns
composed boot/cleanup qualification; the original intermittent physical-Mac
guardian failure remains unexplained.

## Objective and completion conditions

Separate intended expiry, guardian health faults, input delivery, AX readback,
rendered presentation and application-model persistence. Qualify these through
repeatable owned fixtures, rather than repeated manual mouse checks or personal
publishing dashboards. Preserve fail-closed behavior and uncertain-write rules.

## Boundaries

Keep raw evidence private. Log closed predicates and timings, never console
identities, browser bearer endpoints, credentials, clipboard contents or personal
UI text. VM results name their actual security/display profile; they cannot
certify physical displays, lid behavior or hardware takeover.

## Ordered work

### 1 — attribute termination before relock

Retain typed guardian console/lock, cover, input-guard, lid, parent-liveness,
probe-failure and monotonic deadline evidence. Preserve simultaneous failures
and existing external-reason precedence. Carry diagnostics to final receipts,
status and the bounded private journal without weakening cleanup.

### 2 — compare ordinary and covered effects

Use native text/editor/event oracles and a browser form with independent HTTP
model/save/reload evidence. Include realistic long Unicode descriptions and
synthetic hover. Never retry a write to make an assertion pass. Correct fixture
preconditions separately from provider defects.

### 3 — qualify presentation and sustained control

Extend the existing packaged runner with independent unfiltered display
sampling/OCR, actual configured-duration expiry, and the existing fault/recovery
matrix. Keep owner/generation assertions and independent relock. Add the
renewable-owner cells from [Tactical 144](144-renewable-control-owners.md).
Inventory an independent native VM takeover route; do not relabel synthetic
agent input or a manual-wait case as physical conformance.

## Validation and current result

Focused native tests pass health-predicate attribution, simultaneous expiry,
closed diagnostic decoding and consent invariants. Ordinary Chrome native
input, model events, Save and reload have bounded packaged VM evidence.

An initially failing AppKit replacement test was isolated outside covered
control: all characters arrived with change events and no retained modifiers,
but the bare fixture lacked the Edit menu needed for Command-A. Standard Edit
commands were added to the fixture; this was not an input-provider repair.
Harness fixes also distinguish incomplete pre-panel observations from absence,
reopen minimal-profile Settings after restart, and wait for the existing
physical-quiet guard. These findings do not resolve the original real-use gap.

The larger ordinary browser test exposed a separate runtime defect: every
non-newline Unicode character arrived, but all 36 line breaks were absent in
AX, DOM/model and HTTP. Literal LF on a virtual A-key event was ignored by
Chrome. Native text now delivers LF, CR and CRLF as one unmodified Return;
the exact multiline model/save/reload fixture is its live regression.

**Current, bounded packaged VM evidence:** ordinary and covered AppKit
replacement and two-point hover pass. One-point mouseMoved alone was an
insufficient fixture oracle. Native Chrome input, model events, Save and full
reload now pass under the repaired cover, alongside independent unfiltered
cover OCR/pixels (570 of 576 background samples) and visual inspection.
Clean completion retains consent without a delayed or duplicate browser write.
The full sustained/fault result is recorded below.

One later ordinary new-tab trial refused `Command-A` with `operation_failed`;
the original trace omitted its native message. Earlier and subsequent trials
pass, which does not explain that refusal. Private operation traces now retain
failure message/delivery/uncertainty metadata while excluding request text and
response data. The refused action was not retried. Keep this isolated finding
open unless the richer trace supports a cause and regression.

The first SDK admission after covered completion ended with
`desktop_locked_browser_only` before renewal began. A later observation showed
desktop scope ready again. The harness now waits for fresh desktop availability
before creating a new intent; it never reopens an ended intent or replays input.
Renewable active duration is measured after activation, with independent effect
samples required to span more than 900 seconds in the full qualification.

A subsequent SDK activation exposed the resident's synchronous guardian-start
wait: it could hold the main loop for up to twelve seconds while the client
expected heartbeat replies within five. The client disconnected and relocked;
guardian diagnostics retained healthy predicates and remaining time. Startup
now waits off the main loop, then drains owner EOF/heartbeats and rechecks the
exact live lease, phase and authority before adopting the result. Stop or a
replaced lease rejects a late result. Pre-arm root observations are not treated
as proof that an already active root session ended. The startup timeout and
watchdog limits are unchanged. Main-queue responsiveness and timeout regressions
passed at that step. The rebuilt bundle's live result is recorded below.

The asynchronous short probe then passed native/browser effects, independent
concealment and 120 seconds of same-owner renewal with five root
acknowledgements and completion relock. A succeeding task exposed a relock/
display-sleep handoff: a sleep notification ended an already-locked startup
that was about to perform its bounded wake preparation. That startup now
continues only if it originally started locked, remains in the waiting/unlocking
phase and an independent fresh observation still reports locked. Active control,
unknown/unlocked state, ordinary tasks, system sleep and physical takeover
retain their existing endings. The phase/state regression and all 268 native
tests pass; protected disconnect and sustained acceptance then passed below.

## Final bounded VM result

The exact locally signed development app passes 200 checks, 19 browser cycles
and five planned restarts on ARM64 Tart, macOS 26.6.2, Chrome for Testing 155,
one virtual display and SIP disabled. Ordinary/covered text, two-point synthetic
hover, browser model/Save/reload, independent unfiltered cover sampling and
visual inspection, completion, disconnect and Stop pass. No delayed/duplicate
fixture writes or new resident/guardian/root OS crash reports appear.

The finite owner ends `duration_expired`: guardian elapsed time is 900.002
seconds, with only `duration_expired` in its failed predicates and all health
checks true. Owner wall time including startup/cleanup is 905.388 seconds.
The same-owner 960-second renewal result is owned by
[Tactical 144](144-renewable-control-owners.md).

Injected first/repeated guardian crashes relock in 0.297/0.288 seconds with
30/60-second cooldowns. Stalled-guardian and root-only relock pass, including
both resident and guardian suspended (4.910 seconds from injection to lock).
A hung root loses authority at the bounded liveness limit. Resident death
restores browser scopes first, then desktop scopes after healthy/quiet recovery,
without rewriting saved consent. Fresh tasks and final operator Stop/relaunch
pass. Exact common-run receipts verify completed execution and disposal.

The independent kernel-post route reports permission granted but refuses the
actual post. It qualifies no takeover. The diagnostic now reports
`unavailable_post_refused`; the original raw result remains private. Physical
mouse/keyboard, lid/wake, multiple displays and SIP-enabled operation remain
open, alongside the original intermittent guardian fault and the isolated
unexplained ordinary shortcut refusal described above.

The first model mismatch was a harness targeting mistake: existing-tab
navigation does not select the tab, and the observed page remained unfocused
and hidden even after fresh admission. The test now explicitly presents its
owned tab, clears virtual focus and verifies actual focus before writing.
An equivalent new-tab native trial passes uncovered, while covered AX still
lacks a WebArea after a bounded readiness wait. A Chromium-only, once-per-launch
platform activation experiment produced enabled readback but did not repair
the covered tree, so it was removed. Negative checks for delayed/duplicate text
after completion and app restart remain in the fixture.

**Decision, bounded live regression passed:** use an alpha-composited window
with full alpha-1 opaque content paint, avoiding the opaque-window optimization
hint. Require matching full-frame geometry and completed opaque paint before
arming; refuse hidden/translucent/unpainted surfaces. A guest-only drawing
probe found `window.display()` did not paint the new content view, while an
explicit content display did; startup now flushes that paint before unlock.
Independent unfiltered presentation and covered browser effects pass together.
Lock, input guard, takeover and protected watchdogs are unchanged. This repairs
the owned regression, not every retrospectively reported real-site symptom.

## Remaining physical qualification matrix

| Capability | Unattended VM evidence | Separate physical qualification |
| --- | --- | --- |
| Synthetic hover, keys, Unicode text | Own AppKit event/file and browser model/save/reload oracles | Repeat on the intended physical configuration |
| Cover presentation | Independent full-display capture, sampled pixels and OCR | Multiple displays, mirroring, hotplug and lid transitions |
| Takeover | Independent kernel-posted pointer diagnostic reports actual production classification, or an explicit unavailable result | Actual mouse movement/click and keyboard; assert input swallowed, relock and owner ended |
| Faults and ownership | Guest/root watchdog, connection loss, expiry, renewal and Stop, each independently observed | Repeat bounded fault cells on intended hardware before claiming physical conformance |
| Wake/lid | Only the guest's actual virtual-display behavior | Display sleep/wake, closed lid and power transitions |

The existing interactive physical cell remains opt-in. No fabricated event
origin or internal interruption call substitutes for hardware evidence.
Instrumentation is automatic; any physical operator step is named and bounded.
Future releases from 0.6.11 require the composed controller runner and verified
workspace disposal before the exact-candidate receipt is eligible; see the
[release guide](../../release/desktop.md).

For development diagnosis, the existing packaged runner supports
`--covered-probe --covered-renewal-seconds 120 --repeat 1 --soak-seconds 0`
inside its required claimed disposable scope. This checks startup, effects,
short renewal, disconnect and Stop before the longer campaign. It requires
`--development`; it neither qualifies fifteen-minute operation nor emits a
release-eligible receipt. Full qualification uses the composed runner.

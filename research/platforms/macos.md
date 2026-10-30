# macOS Control Research

Status: full logged-in Aqua software-testing composition is adopted and
live-tested in a prepared Tart appliance; login and preboot planes remain open.

## Native foundation

**Current (2026-10-25), bounded `live-tested` placement finding:** direct
`SACLockScreenImmediate` from a root system-bootstrap probe produced no
IOKit-observed lock within five seconds. The same primitive from the console
user's GUI bootstrap produced lock in about 0.10 seconds. This comparison
changes bootstrap and UID together; it does not prove a UID drop is necessary.
Earlier composed watchdog cells left a user-session component responsive and
therefore did not establish independent root relock. The unreleased repair
uses a pinned root-owned lock-only runner, fixed user-bootstrap placement,
irreversible credential drop and original-console revalidation. Root observes
lock independently. [Tactical 138](../../docs/tactical/138-remote-arming-recovery.md)
owns qualification with both resident and guardian suspended; multiple
displays, SIP-enabled execution and other OS revisions remain separate.
The final signed development assembly passes 81 composed checks. With both
user-session control processes suspended, lock is independently observed
4.858 seconds after injection and 0.156 seconds after root fault detection;
root dispatch, child exit and IOKit readback logs corroborate that cell. This
is one awake display on a SIP-disabled macOS 26.6.2 VM, not physical or
distribution qualification. Saved consent survives the fault campaign, and
native Stop still revokes it.

**Current (2026-10-03), `built` and bounded `live-tested`:** the owned resident
now has a separate experimental covered locked-use workstation profile. Native
operator setup, short authorization grants, a signed cover/input companion,
root watchdog, filtered ScreenCaptureKit capture, and typed task ownership
are implemented. [Tactical 064](../../docs/tactical/064-macos-locked-use.md)
owns the exact acceptance matrix; the [current topic](../../topics/macos-locked-use.md)
owns direction. One SIP-enabled physical completion cell is also live-tested
below. This does not broaden Cua's locked-session evidence, qualify multiple
displays or distribution, or add sleep/closed-lid/preboot support.

The ordinary target-native plane combines Accessibility (`AXUIElement`),
WindowServer/ScreenCaptureKit capture, application/window APIs, semantic
actions, and target-local input. Stable application identity and TCC consent
are deployment requirements. Login window, FileVault/preboot, credentials, and
some protected surfaces are separate authority domains.

**Current (2026-10-14), comparison `source-reviewed`, static only:** the
[Sky dossier's lock-screen review](../providers/sky-computer-use.md#lock-screen-authorization-boundary)
found an optional password-free SecurityAgent mechanism whose peer check
compared Team ID and signing identifier, with no observed strict code-validity,
designated-requirement, or exact-artifact check in the plug-in path. This was
not installed or dynamically exercised and is not a demonstrated exploit.
Machine Control instead strictly validates the live resident and pins its
exact installer-recorded CDHash before its root broker can arm a short,
one-use, console- and generation-bound grant. Keep that stronger boundary;
publisher metadata alone is not protected-unlock authority.

## Browser control with the console locked

**Current (2026-10-17), bounded `live-tested`:** in an exclusively claimed Tart
guest running macOS 26.6.2 and Chrome for Testing 155.0.8059.79, the owned
extension/native-messaging route remains usable while the actual console is
locked. The existing resident uses standing appliance authority, with covered
locked use disabled and no unlock helper installed. No workstation grant policy
was changed. Independent IOKit lock readback and resident state both report
locked; no covered-control session is created.

The [guest-only probe](../../tests/browser/locked-macos-live.py) passes tab
enumeration, page AX snapshot, semantic click, Unicode typing, tab PNG capture,
navigation and release/reattachment while locked. The fixture HTTP server
independently observes exactly one click, the expected text and navigation;
the captured PNG is visually checked against the fixture. The test browser and
its fresh profile are reaped/removed, and the experiment VM is returned to its
initial powered-off state. Raw receipts and the fixture image remain private.

This establishes feasibility for this awake VM/browser/appliance route only.
It does not qualify physical Macs, sleep, closed lids, other OS/browser
versions, browser permission dialogs, passkeys or browser-root streaming.
Workstation source now adds a separate, default-off browser-only retention
preference; [Tactical 130](../../docs/tactical/130-macos-browser-while-locked.md)
owns its validation. The [browser topic](../../topics/browser-control.md#open)
owns current policy and remaining qualification. The [provider dossier](../providers/chrome-extension.md)
owns the route comparison.

**Current (2026-10-17), source-native workstation `live-tested`:** a separate
workstation runtime compiled from the implementation passes 26 guest checks
using the same macOS/Chrome fixture above. The independent appliance resident
presses the real native approval dialog. With the local preference enabled,
the mixed approval keeps its original ID and expiry through lock; desktop
capture/input and new DevTools approval refuse. A browser-only admission owner
starts and enumerates tabs without covered unlock. Independent click/text/
navigation effects, page capture, reattachment, Pause/Resume and disabling pass
while IOKit continues to report locked. The fixture uses the existing source
appliance's ad-hoc designated requirement to retain its VM TCC permissions;
its policy and preferences are isolated, and no root policy is changed.
ARM64 and x86_64 fixture builds, 222 Swift tests, the Mac static smoke suite,
TypeScript and the unsigned ARM64 desktop bundle pass. This is not signed
installed Settings acceptance, physical-Mac or streamed DevTools evidence.

## Keyboard layouts and modifier remappings

**Current (2026-10-24), owned native provider `built` and bounded
`live-tested` in the packaged app:** installed signed desktop 0.6.8 crashes on
the first download-location `dialog.choose` in two independent fresh launches
under workstation approval. The OS stacks match the reported HIToolbox
input-source property dispatch assertion. A standalone appliance baseline
passes, exposing a gap in that earlier validation. The source fix copies
layout properties on the main queue, retaining worker-side AX/input and
per-request verification. A locally Developer ID signed 0.6.8-based package
with the repaired embedded framework passes 62 checks across three successful
runs with sixteen download/upload cycles, layout changes, Settings recreation
and a fresh app launch, without a within-run PID/generation change or new OS
report. [Tactical 135](../../docs/tactical/135-browser-file-dialog-crash.md)
owns the execution record. The corrected package is not notarized/published;
physical and Intel execution remain open. This is owned-provider evidence,
not new upstream Cua evidence.

**Current (2026-10-15), `built` and bounded `live-tested`, unreleased owned
native provider:** the real ARM64 Tart resident passes an AppKit/WebKit
keyboard matrix for U.S., Dvorak and Dvorak–QWERTY Command, with default
modifiers and with both Command/Option pairs swapped plus Caps→Control.
The same resident remains running across configuration changes. Menu/editing
effects, exact Unicode text, shifted punctuation, logical Control/Option,
clean modifier state and a subsequent unmodified pointer effect are observed
independently. Chrome for Testing additionally passes address-bar navigation,
text, clipboard and new/close-tab effects under Dvorak/remapped modifiers.
Native Terminal/readline and a standalone pinned Electron editor also pass all
six configurations: exact edited PTY lines and Terminal tab actions; Electron
Unicode text, clipboard/undo and native Save/Find accelerators with independent
state. This qualifies the tested fixtures, not arbitrary application keymaps.

The production credential planner/emitter passes a fixed public dummy in the
fixture's secure field through session and process routes. A separate six-cell
real SecurityAgent matrix also passes canonical stored-credential submission,
strict requester/field discovery, dialog dismissal and an independently
confirmed root-command effect. Wrong-requester and single-use refusals pass;
no failed credential is retried. This qualifies the owner-process authorization
profile, not System Settings' session route or login/unlock under alternate
layouts. The real appliance password does not qualify every character. The
candidate requires the full printable-ASCII alphabet before requesting secret bytes,
rejects composition input methods/dead-key-only characters and stale layout
selections, and resolves the whole value before any field clearing or input.
No unqualified ASCII-layout fallback is adopted. Both Mac architectures build;
GUI evidence remains ARM64. The installed workstation and public release have
not been upgraded by this acceptance.

[Tactical 126](../../docs/tactical/126-macos-keyboard-layout-input.md) owns the
runner, alternate guest profile, recovery/cleanup evidence and remaining
framework, layout, login-window and outer-recovery coverage.

## Resident responsiveness

**Current (2026-10-11), `source-reviewed` and bounded `live-tested`:** two
samples of an installed 0.5.8 desktop process caught its main UI thread in
`ResidentService.unlockStatus()` waiting in socket reads, through resident
polling and operator state reads. This is consistent with temporary menu-bar
unresponsiveness; sampling after visible recovery does not establish the exact
duration or cause of the original stall.

Source review finds a main-queue 250 ms resident timer, synchronous session
probe execution and helper status IPC, a 12-second helper socket timeout, and
a 10-second operator-command receiver timeout. The shared frontend also polls
state every second without an in-flight guard. A receiver timeout does not
cancel the scheduled native task. These are specific owned-runtime execution
gaps, not limitations of AX or Tauri's ability to host background work.

**Current, unreleased candidate:** bounded helper/session observations and
serialized native provider work now execute outside the main UI thread.
Deterministic stalled-dependency, expiry, cancellation, slow-reader and Stop
fixtures pass. An exact signed ARM64 candidate on an isolated physical-host
endpoint opened Settings in 127 ms during status work; its main-thread sample
showed the ordinary AppKit/CF event loop. The installed host app, policy and
helper configuration were unchanged. This bounded observation does not measure
all possible dependency delays or prove the original helper healthy.

**Current, follow-up hardening, `source-reviewed` and bounded signed ARM64
`live-tested`:** asynchronous Resume, preflight deadlines/generation fences and
reply admission bounds pass deterministic fault/load fixtures. Signed host load
exposed main-thread audit writes from read-only delegation discovery; classifying
that query as discovery removes the write path, and the exact candidate passes
concurrent discovery, handshake overload and same-runtime Settings recovery.
[Tactical 109](../../docs/tactical/109-macos-runtime-hardening.md) owns source,
numeric resource/latency evidence, cleanup and Windows handoff.

[Runtime and presentation](../../topics/runtime-and-presentation.md) owns the
execution boundary; [Tactical 108](../../docs/tactical/108-macos-runtime-presentation.md)
owns exact signed profile, fixture, browser and restoration evidence. Both Mac
bundle architectures build and pass local signing verification; GUI execution
is ARM64 only. Exact process samples remain private.

**Current, combined-source qualification, `built` and bounded signed ARM64
`live-tested`:** the shared implementation now repeats all three profiles in
Tart, native approval/notices, independent semantic/input/capture effects,
local/outside CLI parity, recovery, restart and standing-policy preservation.
All 21 native ARM Chrome for Testing browser checks pass with Settings absent.
Mac corrections `7fd99a3` and `bc1220b` restore the asynchronous operator's
update-state projection and native log-folder recovery; the final Finder effect
and owned-window cleanup pass. Both optimized Mac architectures rebuild and
verify under local Developer ID signing. Intel remains build/signature-only.
[Tactical 113](../../docs/tactical/113-arm64-runtime-presentation-qualification.md)
owns exact source, artifact identities, restoration and distribution limits;
[112](../../docs/tactical/112-runtime-presentation-acceptance-review.md) remains
the preceding build-only review. This does not add production installation or
updater replacement evidence.

**Open:** why the original helper replied slowly and the exact displayed error.
Protected setup/repair/removal, covered startup, some durable file operations
and update installation retain synchronous native lifecycle paths. Resume's
helper wait is now asynchronous and fenced. Full protected/physical
recertification and broader responsiveness soak remain separate.

## Covered startup observation ordering

**Current (2026-10-29), bounded `live-tested` evidence on a locally
Developer ID signed development package, ARM64 Tart/macOS 26.6.2, SIP disabled,
one display:** the owned ordinary Chrome long Unicode/multiline form passes
native input, independent HTTP model, Save and full reload after the LF/Return
repair. Ordinary AppKit replacement/hover and clean/crash all-scope indefinite
consent restoration pass. A controlled new-tab trial passed uncovered but
lacked native AX WebArea under the earlier opaque-window cover despite correct
tab selection/focus. With alpha-composited cover windows and full opaque
alpha-1 content paint, covered native Chrome AX/input/model/Save/reload pass.
Independent unfiltered capture shows the cover title and 570/576 dark
background samples; visual inspection also confirms concealment. AppKit text,
two-point hover, button/key effects and filtered capture pass, and completion
has no delayed/duplicate model write. The subsequent 200-check campaign passes
actual 900-second expiry, 960 seconds under one renewed owner, protected fault
recovery, Stop and restart. Its independent kernel-posted takeover probe refuses
the actual post, so hardware takeover remains unqualified.
[Tactical 143](../../docs/tactical/143-covered-control-diagnostics-and-acceptance.md)
owns the campaign, fixture corrections and evidence limits. No physical, SIP-enabled or
notarized-release qualification follows from these development trials.

**Current, `source-reviewed` activation mechanism; negative live experiment:**
Chromium's [accessibility design](https://www.chromium.org/developers/design-documents/accessibility/)
describes lazy platform accessibility activation. Its
[Mac application implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/browser/chrome_browser_application_mac.mm)
handles `AXEnhancedUserInterface` from assistive clients, with delayed activation
and a request counter. A native adapter experiment requested it only for
recognized Chromium frameworks, once per exact process launch, and observed
enabled readback. Covered AX still lacked the WebArea, so the change was
rejected and removed; it is not the repair for this fixture.
An upstream [screenpipe report](https://github.com/screenpipe/screenpipe/issues/3884)
describes duplicate input on assistive-client disconnect; it is a reported
related risk, not proof of this project's original symptom. The owned fixture
checks unchanged saved models and native event/text state across teardown
and resident restart. The adopted cover repair above retains full opaque pixel
fill, alpha 1, full-frame paint/geometry health checks and independent
unfiltered capture; no compositor workaround that reduces pixel opacity is used.

**Current (2026-10-13), bounded `live-tested` failure on installed ARM64
desktop 0.6.0 / macOS 26.6.2:** two covered-control attempts ended during
startup. The retry began with all four ordinary scopes approved, locked-use
ready, a healthy approved helper and no recovery pause. It ended after about
two seconds with `desktop_locked`, cleared access and required manual unlock.
The first attempt also returned `control_generation_changed` during concurrent
status preflight; resident history recorded `console_session_changed`.
Independent OS observations after cleanup were locked. Ordinary native desktop
and foreground browser effects passed after manual recovery. These observations
do not establish whether the screen briefly unlocked or isolate every possible
protected-provider failure.

**Current, `source-reviewed` and deterministic regression evidence:** the
runtime/presentation refactor gives the resident a background session cache,
but newer direct observations did not supersede its cached or in-flight reads.
Covered guardian readiness also omitted its independently verified unlocked
session from the parent handoff. Two regressions reproduced a fresh unlocked
observation being rolled back to a pre-unlock locked result. This is consistent
with the observed immediate cancellation and revocation, without requiring a
permission failure. The source repair preserves observation ordering and binds
guardian activation to the original console; it retains expiry, worker bounds,
unknown-state refusal and unlocked-origin restrictions. [Tactical
115](../../docs/tactical/115-macos-covered-observation-ordering.md) records
validation. A subsequent explicitly authorized local ARM64 installation uses
the existing 0.6.0 desktop/CLI with the repaired native framework, signed by the
same Developer ID publisher and carrying a sealed local-patch identity.
Isolated startup, installed byte identity, native permission retention and
automatic maintenance of the already approved helper pass. The disabled
locked-use choice is preserved and the console remains unlocked. This local
candidate is not newly notarized or published.

**Current, bounded physical completion `conformance-tested` on this signed
ARM64 candidate:** after explicit operator opt-in and manual lock, the native
OS probe observes covered unlock on one display. An exact owned fixture's file
oracle confirms AX button, pointer and keyboard effects. Native display capture
reports covers excluded, yields a valid PNG, and visual inspection shows the
fixture's resulting counter and text beneath the cover. Explicit completion
produces independently observed OS relock, no remaining covers/session, no
manual-recovery pause and the unchanged original approval. All 16 bounded
checks pass; fixture and target claim cleanup pass. This qualifies one clean
completion cycle, not expiry, takeover, repeated tasks, multiple displays or
public-package distribution. Physical cover appearance was not separately
confirmed by an operator or an external capture oracle.

## Covered unlock password-panel investigation

**Current (2026-10-16), bounded `live-tested`:** signed ARM64 desktop 0.6.1
on a one-display macOS 26.6.2 VM reaches actual covered activation from lock.
Independent IOKit readback observes unlock and subsequent completion relock;
the native fixture oracle confirms AX, pointer and keyboard effects. Filtered
capture, zero remaining covers/owner and retained ordinary approval pass. A
preceding trial ends with the distinct `disabled` reason, followed by a helper
disconnect pause and revoked access. Its cause remains unisolated.

This does not reproduce the reported physical password-panel failure or qualify
Touch ID entry and multiple displays. Installed 0.6.1 declares revision
`de253841f10c9df1da457dc5cd4780d20c9bfd68`; its trigger matches the reviewed
source. Added Python bytecode caches invalidate strict bundle resource checks;
removing only those added files in VM staging restores verification. No causal
relationship to the reported unlock failure is established.

**Current, `source-reviewed` and deterministic regression evidence:** fixed
diagnostic suffixes separate unavailable/ambiguous login windows, AX failures,
traversal exhaustion and field absence/ambiguity/disabled/focus conditions.
No password value or arbitrary lock-screen text is read. Unexpected AX failures
refuse; process identity, strict field matching, PID-targeted Return and the
retry duration remain. Tests and both architecture builds pass; live acceptance
of the modified trigger remains open. [Tactical
129](../../docs/tactical/129-macos-unlock-panel-diagnostics.md) owns execution.

## Resumable admission

**Current, `built` and bounded `live-tested`:** the owned admission channel
queues live same-user owners, uses finite offers and sessions, and fences
scoped actions. Consent/manual pause persistence and nonactivating notice
presentation compile in both Mac app shells. A normally deployed Tart resident
passed doctor, remote inner window observation and one native AX fixture action
whose independent counter increased exactly once. A large snapshot exposed
socket backpressure; bounded asynchronous replies passed the regression fixture
and the repeated native effect trial. [Tactical 079](../../docs/tactical/079-consent-and-control-notices.md)
owns this slice; [access admission](../../topics/access-admission-and-pause.md)
owns current direction. Physical locked-quiet/restart, notice focus and assisted
navigation acceptance remain open. Caller assurance is cooperative same-user,
not authenticated YA session delegation.

## Caller authentication gap

**Current, bounded `live-tested`:** native MC trust, authenticated signed YA
origin, installed CLI routing and the full signed MC operator app pass ordinary
independent effects, Pause/fresh Resume, Stop/restart and caller/lifecycle
refusals. Owned protocol providers start no LLM. Positive protected-consent
composition, signed replacement and sustained-load qualification remain open.
Native capture/input and a bounded 32-effect busy owner pass with independent
oracles and the unchanged watchdog. See [caller authorization](../../topics/caller-authorization.md) and
[Tactical 086](../../docs/tactical/086-native-desktop-delegation.md); a signed
interpreter or public session label still provides no origin authority.

**Current, `source-reviewed`:** the owned resident's ordinary local socket is
mode `0600`; [grant dispatch](../../platforms/macos/resident/Sources/macui/Grants.swift)
checks active scopes rather than binding them to a requester. Grants report
`target_wide`. YA's verification of the installed MC package does not
authenticate the original caller to this resident. This is source evidence,
not a new hostile-caller conformance test.

**Open:** compare authenticated IPC, kernel peer/code identity, connection-bound
grants and minimal credential checks, including their same-user limitations.
The [Sky Computer Use review](../providers/sky-computer-use.md) reconstructs
native peer-signing/parent checks and a separate trusted-service worker behind
the native runtime broker. Owned-endpoint testing confirms the socket owner.
Live rejection of ordinary callers coexists with a measured admission limit:
a chain of signed Node interpreters running owned scripts receives a version
reply even below a detached controller without a Codex ancestor. This does
not establish desktop-action permission, session binding or comprehensive
isolation. No short-lived client credential exchange was found in the
inspected admission path. A later external MCP host passed the normal app-policy
workflow and verified TextEdit menu/input effects from a saved file after
resolving a native-service Codex CLI launch dependency. This uses existing
consent; native approval-bypass resistance and fresh installation remain open.
The dossier and linked spike own the details.
[Caller authorization](../../topics/caller-authorization.md) owns the
high-priority investigation and required evidence.

**Current, bounded `live-tested`:** the owned
[caller identity experiment](../../tests/macos/caller-authorization/README.md)
checks kernel peer audit tokens and strict code validity against a designated
requirement. A publisher-signed native fixture passed; different identifiers,
ordinary Python and an ad-hoc identity impostor were refused. YA's signed Bun
running an unrelated script passed a publisher-only policy and failed the
native Desktop identity requirement. This supports a specific native broker
identity rather than blanket publisher admission. It does not establish real
YA session delegation, grants or hostile same-user containment; [Tactical
071](../../docs/tactical/071-desktop-caller-authorization.md) owns the result.


## Candidate matrix

| Candidate | Evidence | Depth | Current use |
| --- | --- | --- | --- |
| [Cua Driver](../providers/cua-driver.md) | `adopted` for default text insertion and the measured Electron semantic route; `conformance-tested` more broadly | Exact-window state, AX, capture, background/foreground routes, sessions, effects, fixtures | Replaceable adapter behind the resident facade |
| [Open Computer Use](../providers/open-computer-use.md) | `source-reviewed` | Compact Computer Use facade, AX/ScreenCaptureKit, app-post and explicit SkyLight background route | First common-provider comparison set |
| [Peekaboo](../providers/peekaboo.md) | `source-reviewed` | Deepest macOS exact-window/system-surface implementation and native fixture found | Platform depth benchmark |
| [Touchpoint](../providers/touchpoint.md) | `source-reviewed` | Small AX/CGEvent/CDP facade; crop-based capture caveat | Common-provider alternative |
| [Agent Device](../providers/agent-device.md) | `source-reviewed` on macOS | Frontmost-app/desktop/menu-bar semantics; display capture | Device workflow reference, not exact-window proof |
| [agent-desktop](../providers/agent-desktop.md) | `source-reviewed` | Strong compact contract and implemented macOS adapter | Contract reference |
| [native-devtools-mcp](../providers/native-devtools-mcp.md) | `source-reviewed` | Exact capture, AX refs/actions, OCR, CDP | Capture/AX reference |
| Existing macVM helper | `adopted` for the ordinary resident plane | Persistent AX/Workspace/Quartz/CoreGraphics facade with stable TCC identity | Current native default and recovery-aware testbed integration |
| [Sky Computer Use](../providers/sky-computer-use.md) | JS/native static review; bounded live admission and TextEdit input | Socket transport, process identity and separate app approvals; full isolation unverified | Supplement/benchmark only |
| Appium Mac2 Driver | `upstream-claimed` with exact pin | XCTest/Appium automation | Adjacent platform candidate pending focused review |

## Completed evidence

The [macOS Cua findings](../../../machine-control-spike/docs/macos-findings.md)
record high-fidelity window capture, AppKit/Electron semantics, background
input, exact effects, permission identity, restart/reconnect, revocation, and
lock behavior. They recommend Cua as the normal-user core with small truthful
extensions, not a wholesale replacement of the macVM testbed.

Peekaboo contributes the best source-reviewed patterns for `CGWindow`/AX
identity reconciliation, renderable-window filtering, target validation,
background process routing, menus/menu-bar/Dock/dialog/Space surfaces, and an
application-owned fixture oracle.

[`Tactical 008`](../../docs/tactical/008-macos-ordinary-session-resident-control.md)
added live native/Cua differential evidence behind the owned facade. Identical
compact snapshot, semantic press, independent fixture effect, and exact-window
capture cells passed through both providers. Native AX reached Dock and the
complete open Control Center surface where Cua returned a typed no-fallback
gap. Native CoreGraphics text events reached the focused AppKit fixture but did
not change its value; Cua did, so that one operation is now an adopted Cua
route. Normal Accessibility and Screen Recording consent survived rebuild and
full guest reboot under the stable application identity.

[`Tactical 009`](../../docs/tactical/009-macos-administrator-sheet-control.md)
adds `adopted` live evidence for normal Aqua `SecurityAgent` administrator
sheets. Native AX exposed an exact window, requester and prompt text, one
secure field, and unique Cancel and OK buttons. The existing non-root resident
could cancel and submit the sheet with target-local input; a fixture file
oracle distinguished cancellation, a wrong credential with no effect, and a
correct credential followed by read-only privileged command completion. Lease
expiry, reuse, sheet change, resident restart, full reboot, and cleanup also
passed without outer input. This surface did not require a privileged broker.

Live inspection of the dedicated prepared appliance also confirmed an enabled
SSH service and unrestricted passwordless `sudo` for its test administrator:
noninteractive `sudo` returned UID 0, and the effective rule reported
`NOPASSWD: ALL`. This is adopted test-appliance administration reach, not a
bounded privilege model for less-trusted machines. The ordinary host transport
remains Tart's guest agent rather than SSH.

[`Tactical 010`](../../docs/tactical/010-macos-full-aqua-software-testing.md)
adds adopted live evidence for the complete prepared-Tart software-testing
plane. Native AX and target-local pixels/input covered privacy settings,
panels, modal sheets, notifications, Safari downloads, DMGs, Gatekeeper,
Installer, AppKit, SwiftUI, browser/web, and custom-rendered UI. Exact
SecurityAgent, Installer, System Settings, and LocalAuthentication fingerprints
kept credential submission bounded. Full reboot and post-reboot replay passed
with outer UI prohibited, followed by complete fixture/artifact cleanup and a
normal stop.

[`Tactical 011`](../../docs/tactical/011-macos-java-electron-framework-coverage.md)
adds adopted live evidence for deterministic Java Swing and Electron software.
The appliance retains checksum-pinned ARM64 Temurin 21 LTS, Node 24 LTS, and
Electron runtimes. Compact local and remote Swing semantics passed through
native AX at roughly 1 KB per observation. Electron's Chromium controls were
semantically visible to native AX, but native `AXPress` acknowledgement did not
change the file oracle. Explicit Cua semantics produced the effect after guest
activation and bounded tree-readiness polling, at roughly 1.6 KB per compact
observation. Both paths and all exact-window captures passed again after full
guest reboot with outer UI prohibited and no host-oracle change.

The remaining environment omissions are separate: SIP is disabled so
protected-data enforcement cannot be measured, and Tart exposes no virtual
camera or microphone. The corpus will not reinterpret those facts as successful
application effects.

## Screen-lock investigation

**Current (2026-09-10), `live-tested`, native macOS provider in Tart:**
Guest administration and the resident survived lock. Fixture AX controls
became unavailable, a pre-lock AX action failed without a counter effect, and
global input addressed to the fixture instead reached loginwindow. Full-display
capture showed the lock screen while exact-window capture retained readable
fixture pixels. A separate no-active-display state prevented display capture
and coordinate input until a bounded guest wake assertion restored the display.
One normal dummy-credential unlock restored AX and keyboard fixture effects
without a resident restart. Local and outside calls shared the observed limits.

The resident and doctor falsely reported unlocked/ready throughout lock.
The [authoritative investigation record](../../platforms/macos/docs/lock-screen-investigation.md)
owns method, operation results, contract gaps, cleanup, and the documented
Codex locked-use comparison. Cua was unavailable and was not tested in this
run. SIP was disabled and FileVault off; physical-Mac and protected-profile
claims remain open. This evidence does not promote login control to adopted
or conformance-tested status.

## Owned resident unlock implementation

**Current (2026-09-10), `conformance-tested`, explicitly opted-in Tart appliance:**
[Tactical 034](../../docs/tactical/034-macos-session-state-and-unlock.md) promotes
the original MIT prototype into the owned resident, native session probe,
authenticated root broker, and conflict-aware installer. It fixes the earlier
false unlocked reports and guards ordinary input during known lock/unknown
state. Local and remote native unlock, independent application effects,
restarts/reboot, grant rejection/revocation, policy drift, and password fallback
were exercised with SIP, authenticated-root protection, and Gatekeeper enabled.
The [implementation](../../platforms/macos/guests/macos/unlock/README.md) owns the
trust boundary and the tactical owns the precise validation/omission matrix.

The installed provider still advertises `experimental`: the callback consumes
session-wide authority rather than an agent-authenticated token, and the policy
composition and OS observer are version-sensitive. Locally ad-hoc-signed VM
acceptance is separate from physical hardware and notarized distribution.
No proprietary Computer Use implementation or AsyncVNC code is a dependency.

**Current (2026-10-03), `live-tested`, native workstation helper setup in Tart:**
[Tactical 065](../../docs/tactical/065-macos-helper-permission.md) exercises the
app-bundled SMAppService daemon, native Login Items approval, typed root setup,
preference toggles without a new grant, covered completion, and conflict-aware
Permissions removal. Existing Accessibility/Screen Recording grants were reused;
helper approval was handled by macOS. This one-display macOS 26.6.2 run had SIP
disabled. Physical and SIP-enabled covered acceptance remain open; the earlier
appliance acceptance above has its separate protection profile and evidence.

**Current (2026-10-03), negative `live-tested` evidence, native workstation
provider on physical ARM64 macOS 26.6.2 with SIP enabled:**
[Tactical 066](../../docs/tactical/066-macos-physical-locked-use.md) records
successful native helper preparation and preference enablement, followed by a
manually established lock and failed automatic covered unlock
(`covered_unlock_not_observed`). The session ended with no remaining covers or
control owner, ordinary access revoked, and manual-unlock pause set. Manual
recovery cleared the pause. OS logs showed authorization plug-in evaluation
during manual recovery, but none was observed during the automatic attempt.
The log difference did not prove the cause. That initial trial did not reach
covered effects, capture, completion relock or hardware takeover; it does not
promote VM evidence to physical conformance.

**Current (2026-10-03), bounded native diagnostic `live-tested` evidence on the
same physical protection profile:**
[Tactical 067](../../docs/tactical/067-macos-physical-unlock-trigger.md) records
programmatic lock and a process-targeted trigger that revealed the password
panel, invoked the installed plug-in, and produced an OS unlock notification.
The existing guardian then ended with `display_changed` and relocked before
application/capture checks. Kernel-bound input and actual display-layout checks
were then integrated into a signed candidate.

**Current (2026-10-03), bounded integrated `live-tested` evidence on that same
physical profile:** native helper repair succeeded after correcting its
re-registration lifecycle. The product then passed programmatic lock, automatic
covered unlock, independently recorded fixture AX/pointer/keyboard effects,
filtered PNG capture, and IOKit-confirmed completion relock without a pause.
This completion cell is separate from the earlier external diagnostic trigger.
Fixture cleanup found duplicate task-owned processes, so the next runner requires
one fixture with explicit PID/oracle agreement before conformance promotion.
Ordinary approval was lost in that initial completion; [Tactical
070](../../docs/tactical/070-macos-locked-access-retention.md) owns the subsequent
retention revision and stronger physical acceptance below. Multiple displays,
other OS revisions, Intel execution and distribution remain unqualified.

**Current — bounded physical maintenance evidence:** after a signed test update,
the native app refreshed its existing OS-approved managed helper without a Repair
click. Caller eligibility and readiness recovered, the helper generation changed,
the stored checkbox value remained unchanged, and no ordinary access was granted.
A same-build relaunch kept the helper generation unchanged and returned ready
without Repair. [Tactical
072](../../docs/tactical/072-macos-helper-update-maintenance.md) owns the exact
boundaries and result. This does not prove initial consent, revoked-permission
recovery, additional OS versions or distribution qualification.

**Current — bounded physical `live-tested` retention and display wake:** the
installed revision passed idle-lock retention, two consecutive already-locked
tasks and a bounded task-expiry cell with the original approval unchanged.
Inactive-display startup reached covered control using the guardian's temporary
native assertion, without an external wake command. Each cell required one
fixture, semantic PID/file-oracle agreement, independent AX/pointer/keyboard
effects, native capture and IOKit relock with no remaining covers or pause.
Private capture inspection confirmed the underlying fixture was visible to the
agent. No manual unlock or new approval occurred between cells. [Tactical
070](../../docs/tactical/070-macos-locked-access-retention.md) owns retention and
the takeover evidence below; [Tactical
073](../../docs/tactical/073-macos-locked-display-wake.md) owns the earlier
readiness failure and bounded guardian-startup wake fix. This evidence does not
extend to full system sleep, additional OS versions, multiple displays or
notarized distribution.

**Current — bounded physical `live-tested` takeover/recovery:** physical input
raced the runner's stable-active startup check, but IOKit-backed resident status
recorded `physical_presence`, lock, Access revocation, zero remaining covers or
owner, and a manual-unlock pause. The operator confirmed takeover worked. A
subsequent native probe observed the console already unlocked; fresh status
showed the pause cleared and Access still absent, and a new control request
refused with `approval_required`. The full scripted takeover cell is unpassed:
its external probe missed the locked interval, and its extra fixture/capture
checks were not reached in that trial. Tactical 070 records the timing caveat;
the earlier completion/expiry cells supply independent effects and lock readback.

## Operator desktop packaging

**Current (2026-09-30), `live-tested`, operator packaging in Tart:** the new
Tauri desktop shell embeds the same Swift resident in its native process.
A Developer ID signed, notarized, stapled CI bundle rendered correctly
and exercised visible denial/narrowed approval, prompt pausing, self-interface
and protected-operation refusal, Stop, restart, and an independently observed
AppKit fixture effect. This changes packaging and operator presentation rather
than the underlying provider composition. Both architecture packages are
authenticated; ARM64 installed upgrade retained permissions and ended active
access. Intel runtime execution remains open. Precise acceptance is tracked in
[tactical 051](../../docs/tactical/051-tauri-macos-desktop.md). Subsequent public
update testing found an automatic relaunch failure in the legacy sender.
A signed repair fixture now passes native Permissions Restart and automatic
production-feed installation, retaining permissions and ending access.
Released 0.3.5 also passes native Restart and operator/tray acceptance after a
public 0.3.3 production-feed installation with one legacy reopen.
[Tactical 052](../../docs/tactical/052-macos-production-updates.md) owns exact
release/update evidence. Physical-host and Intel runtime acceptance remain
separate gates.

**Current (2026-10-02), `live-tested`, native provider on physical ARM64 macOS:**
The public signed Tauri `0.4.8` has partial physical smoke evidence for visible
consent/approval, native semantics and independently observed fixture action,
window capture, input delivery, and revocation. The
[host topic](../../topics/host-control.md) owns the bounded result and omissions;
full physical product acceptance remains open.

**Current (2026-10-02), `live-tested`, signed ARM64 operator in Tart:** Public
`0.4.9` adds manual until-stopped access. Its exact signed package passes visible
lifetime selection, null expiry/countdown, selected scopes, independent AppKit
counter effect, visible Stop with dispatch refusal, Permissions Restart with a
new generation and retained TCC, and bounded public agent approval. The original
appliance and policy are restored, power is parked, and the claim is released.
[Tactical 057](../../docs/tactical/057-macos-until-stopped-release.md) owns exact
package/publication evidence. This does not add signed lock/recovery, Intel, or
full physical product acceptance.

## Owned authorization unlock prototype

**Current (2026-09-10), `built` and `live-tested`:** An original Apple
authorization plug-in unlocked an already logged-in Tart session without
reading or typing the account password. A root-owned, short-lived grant was
bound to the locked console user's session UUID and boot epoch and consumed
once. An experimental authorization branch preceded the preserved stock
password branch. An empty guest-native Return caused loginwindow to evaluate
the grant and unlock; independent OS observation and AppKit fixture effects
proved two successful cycles through outside and local resident calls.

Missing, expired, wrong-session, and consumed grants were denied by the
mechanism. Unarmed and expired attempts left the desktop locked, with normal
password fallback working. Restoring the original policy and removing the
plug-in preserved normal password unlock. A successful direct evaluation of
the experimental right alone did not unlock the desktop.

The [prototype source](../../platforms/macos/experiments/authorization-unlock/README.md)
is original repository MIT code using Apple SDK interfaces; no proprietary
Computer Use implementation was copied. The
[execution record](../../docs/tactical/032-macos-authorization-unlock-investigation.md)
owns the initial method, test matrix, and restoration evidence. That image
had SIP disabled; the enabled-SIP follow-up below resolves that loading gap.
Caller authentication beyond root arming and
integration with the common resident remain unproved. Screen covering and
local-input protection were explicitly deferred; the desktop stays exposed
and unlocked after successful authorization.

**Current (2026-09-10), source-reviewed:** The SIP-disabled environment is not
a demonstrated Tart restriction. Cirrus explicitly disables SIP in its base
image build; its published vanilla template is a candidate for an enabled-SIP
guest, but also disables Gatekeeper. The platform
[image-security notes](../../platforms/macos/docs/bootstrap.md#image-security-posture)
own those upstream sources and bootstrap distinctions. The
[SIP-enabled guest procedure](../../platforms/macos/experiments/authorization-unlock/README.md#sip-enabled-guest-test)
records protection state separately from image labels.

**Current (2026-09-10), `built` and `live-tested`, SIP-enabled follow-up:**
The unchanged ad-hoc-signed plug-in loaded and unlocked twice on macOS 26.6.2
with SIP, authenticated-root protection, and Gatekeeper enabled. Missing,
expired, wrong-session, and consumed grants were denied. Native AX actions
after each password-free unlock advanced an independent fixture counter.
Normal password fallback and stock behavior after complete removal passed;
the guest was then discarded. The
[execution record](../../docs/tactical/033-macos-sip-authorization-unlock.md)
owns the full matrix and cleanup. No Developer ID signature or SIP change was
needed for that locally built artifact. Notarized/downloaded distribution,
physical hardware, and protected-provider conformance remain untested.

The same run also proved a useful bootstrap route: a headless
[AsyncVNC client](../providers/asyncvnc.md) reached the guest's existing native
Screen Sharing service to grant normal resident consent without host desktop
interaction. The client was disconnected before the integrated unlock tests;
native capture, AX, and input then used the ordinary resident over SSH.

## Fresh Tart bootstrap route

**Current (2026-09-28), `live-tested`, host outer bootstrap and native guest
control:** A fresh Apple IPSW guest completed Setup Assistant, guest-agent and
resident installation, visible TCC consent, and a ready doctor. Its claimed
stage report marked every bootstrap stage complete; the development audit and
Mac smoke suite passed. This confirms the first-boot path separately from the
prepared-image route; it does not add a new claim about login or protected
desktop control.

On the tested host, Tart's resizable window scaled the guest display. A fixed
title-bar crop and scaled click coordinates restored observed menu and consent
targets. The original synthetic Shift and Command events reached the guest without their
modifiers even with system-key capture enabled. The outer route therefore used
unshifted setup input and a separately verified lowercase-and-digit initial
credential. This is a measured host/guest combination, not a general Tart
keyboard guarantee. The [bootstrap record](../../docs/tactical/044-macos-tart-bootstrap-stages.md)
and [guide](../../platforms/macos/docs/bootstrap.md) own the setup and
recovery details.

**Current (2026-09-28), `live-tested`, corrected Tart outer Shift/Command:**
The original guest-file oracle received `abc12z` for `AbC!@Z`, despite general
Shift flags in the host stream. A controlled follow-up isolated a sufficient
sender correction: include the matching left-side device modifier flags.
Changing only the event type still failed; adding device flags restored exact
text and actual Command/Shift–Command menu actions. The adopted sender also
uses explicit `flagsChanged` transitions. Repetition, release, refusal, and a
dummy secure-field oracle are covered by the
[platform experiment and acceptance runner](../../platforms/macos/experiments/outer-keyboard/README.md).
Control, Option, and Fn remain guarded. This evidence is from a prepared guest,
not a new Setup Assistant/account run, and does not prove the exact private
Tart/Virtualization.framework mechanism. The input path needs no guest agent;
the test uses one only for setup and independent observation.

## Owned resident lifetime reliability

**Current (2026-09-29), source-reviewed and live-tested in Tart:** The owned
resident's idle session observer retained a pipe read descriptor on each
refresh outside its request autorelease pool. The unchanged guest gained
272 numeric pipe FDs in 91 seconds without capture, AX, or input operations.
Isolated process-limit reproduction caused unknown session state while the
probe's independent unlocked observation remained valid. This is an owned
resident lifetime defect, not evidence of a Cua or RSTorrent leak or TCC
revocation. Separate guest testing reproduced the Darwin spawn file-action
ceiling at FD 10,240 despite a 65,536 process limit: both the observer and a
plain Foundation subprocess launch returned EBADF. The
[fix and validation record](../../docs/tactical/047-macos-resident-resource-reliability.md)
separates confirmed mechanism from the two historical incidents whose raw
logs are unavailable, and tracks fixed workload/recovery evidence.

**Current (2026-10-02), `live-tested`, signed ARM64 browser provider in Tart:**
The exact desktop `0.4.10` package passes controlled-tab favicon/group lifecycle
and browser fixture effects through its embedded resident under the appliance
policy. Native capture confirms tab-strip presentation. Workstation browser
approval UX, physical execution, and Intel execution stay separate.
[Tactical 058](../../docs/tactical/058-browser-tab-indicators.md) owns the
bounded evidence and release; the
[provider dossier](../providers/chrome-extension.md) owns route facts and gaps.

## Native efficiency and background effects

**Current (2026-10-14), bounded `live-tested`:** the
[Sky native study](../providers/sky-computer-use.md#deterministic-native-behavior-study-2026-10-14)
compared an original AppKit fixture through Sky and the claimed MC CLI in a
disposable ARM64 guest. MC semantic buttons and sheets produced independent
effects without disturbing a focused sentinel. MC pointer/text operations
produced their effects but disturbed sentinel focus/cursor in all five repeats.
Five accepted MC menu-item actions did not change the fixture counter; Sky did
in all five. These are fixture-specific results, not a general app-compatibility
ranking. Controller-host input was not used.

**Current:** unchanged compact MC snapshots at 20/100/300 rows had median CLI
round trips of 477/584/840 ms, versus resident-reported medians of 52/86/169 ms.
The remaining interval includes client/adapter startup, claims, audit,
serialization and transport; this does not isolate each component. Compact
JSON still measured about 35/58/116 kB per result, whereas the Sky unchanged
projection was 414 bytes. The representations and enforcement differ.
[Tactical 124](../../docs/tactical/124-native-behavior-and-efficiency.md) owns
controls, limits and the resulting implementation order.

**Decision:** measure retained claimed dispatch and compact/diff presentation
before a broad accessibility-cache rewrite. Separately qualify window-addressed
input and background menu effects. Automatic observation needs bounded waits
and explicit effect checks; a quiet tree is not an application completion oracle.

**Current (2026-10-15), bounded `live-tested`:** the owned
[AX identity probe](../../tests/experiments/native-identity/README.md) completed
ten unchanged reads, twenty same-presentation replacements, insertion,
reordering, removal, window recreation and process restart in an isolated
ARM64 guest. Across 13,391 comparisons, including 1,982 surviving-incarnation
pairs, no survivor inequality or cross-incarnation equality was observed.
All current actions had their intended independent fixture effects; all
replacement controls preserved label, identifier and frame. Both owned child
processes were reaped.

Twenty-five distinct destruction callbacks were observed. The nonzero
registration responses were duplicate registrations, not failed installation;
every distinct scoped incarnation had a successful registration. No recorded
control deallocation lacked a callback in this run. One raw stale control
proxy press after window recreation invoked a still-live retired control, with
no effect on a current incarnation; its destruction callback arrived later.
Retention, a successful AX role read, and awaiting destruction therefore cannot
establish current tree membership. These results support investigating
bounded stable observation identity with fresh action references and current
membership validation. They do not prove never-reused native tokens, general
application coverage, PID-reuse safety or a production performance gain.
[Tactical 128](../../docs/tactical/128-control-efficiency-campaign.md) owns
implementation and further acceptance; raw receipts remain private.

### Production native identity acceptance

**Current (2026-10-15), bounded `live-tested`:** the resident now separates
stable observation keys from latest-snapshot action references. Observation
continuity uses CFEqual against the preceding qualified native tree; hashes
only bucket candidates. It retains one application's last complete tree,
at most 2,000 objects and 64 windows, with a 30-second maximum observation gap.
PID plus kernel start seconds/microseconds from SDK-declared `sysctl` identifies
the process incarnation. Unavailable metadata refuses qualification; there is
no PID-only fallback. Unchanged native window membership, complete reads and
unambiguous matching are required. Cross-process observation reuse remains
unqualified. Removed identities are not resurrected.

Before native dispatch, the latest reference must still belong to that process
and each observed ancestor edge must occur exactly once in fresh AXChildren.
The process stamp is checked again after membership validation. Missing edges
refuse stale references; unreadable, ambiguous or oversized parent lists refuse
unverifiable membership. Unrelated incomplete branches do not prohibit an
otherwise proven current action. Observation keys never enter action lookup.
Claim, admission and audit behavior remain in place.

The production fixture completed 29 ordinary observations (including three
warmup reads), two explicit incomplete reads and one partial-read action case.
Ten measured unchanged reads retained Python numbers and observation IDs while
refreshing action references. All 21 stale actions refused before dispatch with
unchanged independent fixture effects. Eleven ordinary current actions plus the
partial-read action produced exact incarnation-bound effects through native AX.
The resident envelopes leave these effects unverifiable; independent fixture
callbacks provide the stronger acceptance evidence.
Coverage includes insertion, geometric reordering, five observation-first
replacements, an immediate replacement refusal, removal, retired-window
refusal, and both refusal-first and observation-first window/process resets.
All three fixture children were reaped; an independent process check found no
owned fixture child, and the guest claim returned to available.

Three prior failed acceptance attempts remain retained: AppKit launchDate was
absent for a fully launched directly started app, initial window chrome gained
one group, and a test incorrectly assumed geometry reordering changes native
AX enumeration. The fixes use kernel process metadata, bounded observed setup
settling, and independent native/oracle geometry checks respectively. No
production observation changes were hidden to force a no-change result.

For the same ten retained unchanged observations, Python's compact semantic
projection measured 66 UTF-8 bytes per diff versus 638 bytes for the full
projection; serialized native envelopes had a 34,794-byte median. These are
representation measurements on an owned fixture, not tokens, task latency or
pixel-state reconstruction. Geometry is omitted and menus are hidden by default;
current bounds and references still refresh even when semantic rows do not change.

Representative compatibility also passed: a query-filtered System Settings
Appearance menu and radio actions changed an independently read preference
Automatic → Always → Automatic; native AX opened TextEdit Format and resident Escape dismissed it, changing
independent on-screen window counts 1 → 2 → 1 with fixture bytes intact;
Control Center native menu-bar actions produced counts 5 → 6 → 5. These qualify
those real surfaces, not arbitrary foreign-process AX subtrees or background
non-interference. TextEdit's open-menu read was incomplete (`native_read_failed`)
and withheld observation identity; this does not qualify stable identity through
transient menus or dispatch of Make Plain Text. Finder's 100-node smoke read
was intentionally truncated. Resident capture, artifact retrieval, Finder inventory/tree
and doctor checks passed. The legacy smoke's outer screenshot was replaced
with resident capture; the static suite passed unchanged.

The full Swift suite passed 211 tests; ARM64 and x86_64 builds passed. This
bounded acceptance does not prove never-reused AX tokens, exec-generation
identity, arbitrary app reach, long-run leak freedom or atomic validation and
dispatch. New model trials are needed to establish end-to-end efficiency gains.
[Tactical 128](../../docs/tactical/128-control-efficiency-campaign.md) owns
execution; exact candidate hashes, failures and raw receipts remain private.

## Current direction

**Decision:** Preserve Cua as a replaceable common-plane adapter and Peekaboo as
the macOS depth benchmark. Keep native macOS providers as the current default
for the accepted ordinary surface, and select Cua only where identical
conformance demonstrates a better effect. Commonality must not erase a
materially better macOS route.

**Open:** Extend evidence to occlusion/minimization, off-Space behavior,
multiple displays, localization, fresh login and broader loginwindow control,
FileVault/preboot, bounded
non-UI administration, a SIP-enabled protected-data image, private-API
fragility, and longer background-interference soak runs.

## Native command authentication

**Current:** signed ARM64 desktop helpers pass native-dialog and root-effect
conformance in a dedicated appliance. The Mac desktop bundles a wrapper over
[system sudo](../providers/sudo.md), distinct from typed resident desktop
control. [Native sudo](../../topics/native-sudo.md) owns the decision and
[Tactical 061](../../docs/tactical/061-native-sudo.md) owns route evidence.

## Desktop audit validation

**Current (2026-10-03), `live-tested`:** source-native desktop audit and
storage-failure acceptance runs on the platform's dedicated VM. The shared
[topic](../../topics/desktop-audit-and-diagnostics.md) owns the contract and
[Tactical 069](../../docs/tactical/069-desktop-audit-and-diagnostics.md) owns
platform/architecture results. This does not broaden provider privilege or
signed-package acceptance.

**Current (2026-10-24), bounded packaged `live-tested`:** a locally Developer ID
signed full application passes native-host reconnection, Stop during a blocked
browser navigation, and a forced app exit with LaunchAgent recovery, access Off,
an unfinished-operation/build-UUID breadcrumb and stale-reference refusal.
The first seeded soak passes 47 checks with nine real download/upload cycles
and Settings recreation; the next full candidate passes 53 checks with ten
cycles and actual operator crash-preview/export. [Tactical 136](../../docs/tactical/136-desktop-crash-hardening.md)
owns final candidate results and limits, including 32 focused checks after the
last marker-ownership fix. This adds owned-provider evidence;
notarized publication, Intel/physical execution and Windows/Linux faults remain
separate.

**Current, bounded physical ARM64 evidence:** the unlocked admission notice
retained independently observed fixture application/key/field focus; one native
AX effect changed the fixture counter once. Two owners serialized, manual pause
fenced both, consent and indefinite manual pause survived restart, and Stop
remained off after restart. The signed candidate retained its existing healthy
helper without Repair or another OS permission. Native menu Quit recorded clean
operator cleanup before its active owner channel closed. See
[Tactical 081](../../docs/tactical/081-macos-admission-physical-acceptance.md);
this does not qualify the revised locked takeover/resumption path.

## Native delegated ordinary control

**Current (2026-10-04), bounded `live-tested`:** a signed YA native launch,
credentialed session origin and installed signed MC CLI reached a conformance
receiver forwarding to the actual native AX provider. Independent fixture
counters proved ordinary effects, unrelated-process refusal, Pause/fresh Resume
and Stop/reconnect refusal. [Tactical 086](../../docs/tactical/086-native-desktop-delegation.md)
owns exact revisions and limits. A subsequent full signed MC app run proved native checkbox enrollment and
operator Pause/Resume/Stop through the same live ordinary route. Signed native
capture/input and bounded busy-owner evidence are recorded in Tactical 088.
Both runs use
an owned protocol provider, not an LLM. Protected composition, hardware takeover
and distribution remain unqualified.

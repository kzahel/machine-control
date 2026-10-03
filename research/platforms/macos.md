# macOS Control Research

Status: full logged-in Aqua software-testing composition is adopted and
live-tested in a prepared Tart appliance; login and preboot planes remain open.

## Native foundation

The ordinary target-native plane combines Accessibility (`AXUIElement`),
WindowServer/ScreenCaptureKit capture, application/window APIs, semantic
actions, and target-local input. Stable application identity and TCC consent
are deployment requirements. Login window, FileVault/preboot, credentials, and
some protected surfaces are separate authority domains.

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
| Computer Use | optional installed-provider route | Strong agent ergonomics | Supplement/benchmark only |
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

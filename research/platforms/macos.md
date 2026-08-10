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

## Current direction

**Decision:** Preserve Cua as a replaceable common-plane adapter and Peekaboo as
the macOS depth benchmark. Keep native macOS providers as the current default
for the accepted ordinary surface, and select Cua only where identical
conformance demonstrates a better effect. Commonality must not erase a
materially better macOS route.

**Open:** Extend evidence to occlusion/minimization, off-Space behavior,
multiple displays, localization, lock/loginwindow, FileVault/preboot, bounded
non-UI administration, a SIP-enabled protected-data image, private-API
fragility, and longer background-interference soak runs.

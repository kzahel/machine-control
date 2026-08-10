# macOS Control Research

Status: ordinary-session resident composition is adopted and live-tested in a
prepared Tart appliance; protected macOS planes remain open.

## Native foundation

The ordinary target-native plane combines Accessibility (`AXUIElement`),
WindowServer/ScreenCaptureKit capture, application/window APIs, semantic
actions, and target-local input. Stable application identity and TCC consent
are deployment requirements. Login window, FileVault/preboot, credentials, and
some protected surfaces are separate authority domains.

## Candidate matrix

| Candidate | Evidence | Depth | Current use |
| --- | --- | --- | --- |
| [Cua Driver](../providers/cua-driver.md) | `adopted` for default text insertion; `conformance-tested` more broadly | Exact-window state, AX, capture, background/foreground routes, sessions, effects, fixtures | Replaceable adapter behind the resident facade |
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

## Current direction

**Decision:** Preserve Cua as a replaceable common-plane adapter and Peekaboo as
the macOS depth benchmark. Keep native macOS providers as the current default
for the accepted ordinary surface, and select Cua only where identical
conformance demonstrates a better effect. Commonality must not erase a
materially better macOS route.

**Open:** Extend evidence to occlusion/minimization, off-Space behavior,
multiple displays, localization, protected authorization, lock/loginwindow,
FileVault/preboot, private-API fragility, and longer background-interference
soak runs.

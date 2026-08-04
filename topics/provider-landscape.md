# Desktop Provider Landscape

Topic: `provider-landscape`

Status: source-reviewed candidate survey as of 2026-08-04; no provider has
yet passed the project acceptance suite on the configured targets.

## Scope

This topic tracks reusable resident desktop-control providers and the design
lessons they contribute to the North Star. It does not select a universal
implementation from README claims alone. Exact source pins, experiment logs,
and reproduced behavior belong in `machine-control-spike` or the authoritative
testbed repository.

The comparison is deliberately narrower than a general computer-use survey. A
serious candidate must be usable by an agent running locally or remotely,
address an exact application or window, combine compact semantics with visual
evidence and input fallbacks, report foreground interference and uncertainty,
and remain useful outside one proprietary agent product.

## Current synthesis

**Current — source review:** No discovered project owns the complete North
Star, which also includes administration, bootstrap, protected authority,
physical devices, ChromeOS, iOS, Android, and outer recovery. The current
[Cua Driver](https://github.com/trycua/cua/tree/main/libs/cua-driver) is,
however, much closer to the desired common desktop plane than the older spike
alone suggests. [Touchpoint](https://github.com/Touchpoint-Labs/touchpoint) is
the closest small, comprehensible alternative facade. For platform depth,
[Peekaboo](https://github.com/openclaw/Peekaboo) is the strongest macOS
reference found, [WinApp](https://github.com/microsoft/winappCli) remains an
important Windows reference, and
[kwin-mcp](https://github.com/isac322/kwin-mcp) demonstrates the strongest
Linux isolated-session pattern.

**Decision:** Keep ownership of the target-oriented contract and conformance
requirements in this project. Treat upstream software as an adapter,
dependency, implementation seed, or benchmark according to observed behavior.
Do not reimplement a provider merely to own every line of code, and do not
delegate lifecycle, authorization, recovery, or truthful capability reporting
to an upstream desktop library that does not own those boundaries.

**Proposal:** Re-evaluate current Cua Driver first on the Windows proving
ground. Compare it with the existing WinApp route using the same shell,
single-window, background-interference, and effect-evidence acceptance cases.
The source review is strong enough to change the priority, but not strong
enough to declare a winner without running it.

## Agent Device, including macOS

**Current — source review:** The project the earlier discussion called
"device-control" is almost certainly
[Callstack Agent Device](https://github.com/callstack/agent-device). It is the
current semantic XCTest provider used by `ios-device-testbed`, and it also
contains a macOS desktop helper.

The current macOS helper exposes three useful semantic surfaces:
`frontmost-app`, `desktop`, and `menubar`. It builds application and window
state from `NSWorkspace`, `CGWindow`, and Accessibility (`AXUIElement`), and it
can include the active application's menu bar and SystemUIServer menu extras.
Actions prefer AX where available and use target-local `CGEvent` input as a
fallback.

It does not currently expose the exact single-window contract the North Star
needs:

- the public semantic target is a surface such as `frontmost-app`, not an
  exact stable window selector;
- desktop snapshots contain window metadata, but that metadata is not an
  end-to-end window-scoped observation/action boundary;
- the current macOS screenshot path captures the main display rather than an
  isolated selected window; and
- coordinate input is target-local but not proven to remain confined to one
  background window without focus consequences.

Agent Device's bundled test application is primarily an Expo/React Native
mobile fixture. It uses unique `testID` and accessibility labels, deterministic
forms, navigation, gestures, alerts, permission flows, and replayable `.ad`
scripts. Those are good device-testing practices. They do not yet constitute a
native multi-window macOS conformance fixture for menus, sheets, popovers,
status items, background delivery, and exact window capture.

**Decision:** Continue using Agent Device where it is already authoritative
for iOS. Keep its compact snapshot/action workflow and recovery behavior as
design input. Do not treat its present macOS backend as proof of exact-window
desktop control or as the common cross-platform provider.

## Leading cross-platform candidates

### Cua Driver

**Current — source review:** Current Cua Driver presents the most complete
match found for the common Windows, macOS, and Linux desktop plane:

- a resident CLI, MCP server, and embeddable SDK share one Rust runtime;
- calls identify an exact native `(pid, window_id)` and `get_window_state`
  returns a window accessibility tree and screenshot together;
- snapshot-bound element indices, window-relative pixels, and desktop scope
  are distinct addressing modes;
- semantic actions use background delivery by default, then explicitly
  escalate through pixel and foreground routes instead of silently changing
  focus posture;
- results distinguish confirmed, suspected no-op, unverifiable, and refused
  outcomes, and the agent is told when to reread fresh state;
- macOS, Windows, X11, and compositor-specific Wayland routes report different
  limits rather than claiming identical behavior; and
- session-scoped capture policy, agent cursors, recordings, bounded manifests,
  and protected browser-profile attachment are explicit parts of the contract.

Its current repository also contains real source-built fixtures for AppKit,
SwiftUI, WKWebView, WPF, WinUI 3, WebView2, GTK, Electron, and Tauri. The shared
catalog varies semantic versus pixel addressing, foreground versus background
delivery, and window versus desktop scope. Independent fixture state, focus,
z-order, physical cursor, leaked-input, accessibility, and pixel oracles decide
whether an operation worked; a successful API return is not enough.

The implementation has real platform-specific capture tradeoffs. For example,
Windows uses Windows Graphics Capture, `PrintWindow`, and guarded screen-region
fallbacks depending on surface behavior, while macOS uses exact WindowServer
window identifiers. Linux per-window capture and raw input vary by X11 or
Wayland compositor. This is precisely why route and fidelity must remain in
capability and result data.

**Open:** The previous spike audited an older bounded state and found important
Windows integrity, secure-desktop, lock-state, signing, provenance, and IPC
gaps. Determine which still apply to current Cua Driver, whether its
background/private-API posture is acceptable for dedicated appliances and
personal machines, how its daemon is exposed remotely, and whether Start,
taskbar, notification-area flyouts, Settings, and elevated windows meet our
acceptance contract.

### Touchpoint

**Current — source review:** Touchpoint offers one compact Python API and MCP
server over macOS AX, Windows UIA/Win32, Linux AT-SPI/X11, and browser CDP. It
supports application, exact-window, element, search, wait, action, and
screenshot operations. Its macOS window IDs prefer `AXWindowNumber`, then AX
identifiers, with a cached fallback; Windows couples UIA with HWND operations.
It also merges browser content from CDP with native browser chrome.

Touchpoint is especially valuable as a small facade and adapter reference. Its
current screenshot implementation generally captures the framebuffer and
crops it to reported bounds, so a `window_id` crop is not necessarily an
occlusion-independent capture of that window's own pixels. Linux raw input is
X11-oriented, and the repository's automated workflow evidence is not yet a
substitute for running the same real-desktop matrix ourselves.

**Proposal:** Keep Touchpoint as the second cross-platform spike candidate and
as a readable source of exact-window identity and compact semantic formatting.
Test crop fidelity, transient surfaces, stale references, background actions,
and shell coverage before adopting it.

### OculOS

**Current — source review:** [OculOS](https://github.com/huseyinstif/oculos)
has a useful resident-daemon shape: REST and MCP, session-scoped references,
accessibility trees, actions, screenshots, and window APIs across nominal
Windows, macOS, and Linux backends. Its current source is much more complete on
Windows than on macOS or Linux. Some advertised per-window and semantic
operations remain unsupported or incomplete in those adapters, and CI largely
establishes buildability rather than live desktop effects.

**Decision:** Use OculOS as a protocol and service-layout reference, not as a
validated common provider.

## Platform-specific depth references

### macOS: Peekaboo

**Current — source review:** Peekaboo has the strongest single-window macOS
implementation reviewed. It reconciles `CGWindow` and AX identities, supports
selection by process, native window ID, title, and index, filters helper and
non-renderable windows, and captures target windows through macOS window and
ScreenCaptureKit routes. Its actions can be process-targeted in the background;
foregrounding is explicit. It includes semantic commands for applications,
windows, elements, menus, menu-bar items, Dock items, dialogs, and Spaces, and
it re-reads window state rather than equating a requested change with success.

Peekaboo's native Swift Playground is also the best desktop fixture model found
in this pass. It supplies dedicated scenarios for clicks, text, keyboard,
scroll, drag, windows, menus, menu-bar items, Dock, dialogs, Spaces, and
capture. Application-owned OSLog counters and state canaries let tests verify
effects independently of the automation response. Its public automation and
window-selection notes are useful implementation references:

- [automation architecture](https://github.com/openclaw/Peekaboo/blob/main/docs/automation.md);
- [window screenshot selection](https://github.com/openclaw/Peekaboo/blob/main/docs/window-screenshot-smart-select.md); and
- [testing tools](https://github.com/openclaw/Peekaboo/blob/main/docs/testing/tools.md).

**Proposal:** Use Peekaboo as the macOS deep reference and fixture seed even if
Cua Driver or another project supplies the common facade.

### macOS contract and capture alternatives

**Current — source review:**
[agent-desktop](https://github.com/lahfir/agent-desktop) has an excellent
compact contract for progressive snapshots, stable window/surface identities,
semantic versus physical action policy, structured errors, traces, and
multi-agent namespaces. Its present Windows and Linux adapters are stubs, so it
is a macOS implementation and cross-platform contract reference, not a working
three-platform provider.

[native-devtools-mcp](https://github.com/sh3ll3x3c/native-devtools-mcp) offers
exact per-window macOS and Windows capture, OCR, CDP, and ADB. Its semantic
reference actions are currently much stronger on macOS; Windows UIA snapshots
do not have equivalent reference-bound actions. It is useful for macOS AX
action quirks and window capture, not semantic parity.

### Windows

**Current — source review:** WinApp remains the existing Windows semantic
route. It provides HWND-scoped UIA snapshots and actions, captures individual
windows and their dialogs, and has an explicit screen-capture mode for popups
and flyouts that cannot be represented by `PrintWindow`. That distinction is
important: an exact application window and a transient desktop-owned surface
are different capture scopes.

[Terminator](https://github.com/mediar-ai/terminator) is a substantial
Windows-only UIA/Rust automation implementation with application/window
management, semantic locators, capture, recording, browser integration, and
MCP/SDK surfaces. Its macOS link does not represent a native macOS backend.
It is a Windows implementation reference, not a cross-platform answer.

### Linux and isolated desktops

**Current — source review:** kwin-mcp launches a private D-Bus session and
virtual KWin compositor, reads AT-SPI semantics, captures through KWin, and
injects input through KWin EIS/libei. This allows a real Wayland application to
run without touching the controller user's desktop and can optionally isolate
the application's home/XDG directories. Its current targeting and screenshot
surface are not yet the complete exact-window facade.

**Decision:** Preserve this distinction in Linux planning: a resident provider
inside a dedicated virtual compositor is still target-native control, not an
outer pixel route. The session appliance can be an important part of
reproducibility and non-interference even when the semantic adapter is shared
with live desktops.

## Fresh-search triage

**Current — search triage:** A broader GitHub and web search did not reveal a
single project with the complete machine, desktop, device, administration,
delegation, and recovery vision. It did surface adjacent implementations worth
remembering without promoting them to the first validation round:

- [Microsoft UFO](https://github.com/microsoft/UFO) is a substantial Windows
  agent framework with UIA/Win32 application control, screenshots, and
  multi-agent orchestration. Its agent hierarchy overlaps YepAnywhere's
  coordination concern and does not supply the cross-platform resident plane.
- [mcp-windows](https://github.com/sbroenne/mcp-windows) and
  [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) are additional
  Windows semantic/computer-use providers. They remain fallback comparison
  candidates if Cua Driver and WinApp expose a material gap.
- [linux-desktop-mcp](https://github.com/BeckhamLabsLLC/linux-desktop-mcp)
  combines AT-SPI with X11 or system-wide synthetic-input tools. It is useful
  implementation context, but kwin-mcp's private compositor session has a
  clearer non-interference boundary for a test appliance.
- [Agent for macOS](https://github.com/macos26/agent) combines AX automation,
  scripting, an agent loop, a user service, and a privileged helper. It is a
  broad macOS agent application rather than a narrow provider that the common
  target facade can adopt directly.

These projects should be revisited when a measured gap calls for them. A long
provider list is not a substitute for running the same conformance cases.

## Single-window contract

**Decision:** "Window control" is not one boolean capability. Conformance must
test the following properties separately:

1. **Identity:** address a native window independently of application or
   process identity, detect recreation, and reject an owner mismatch.
2. **Semantic scope:** derive the tree and element references from that exact
   window, while representing sheets, dialogs, menus, popovers, taskbars, and
   other separately owned surfaces explicitly.
3. **Visual scope:** state whether pixels come from a compositor/window capture
   or a desktop crop, and whether occlusion, minimization, another Space,
   DirectComposition, or protected content changes fidelity.
4. **Action scope:** bind semantic or pixel actions to the same window and
   coordinate epoch used for observation.
5. **Delivery posture:** say whether an action was direct semantic,
   process-targeted background input, foreground input, or desktop-wide input,
   including cursor, focus, z-order, and active-Space effects.
6. **Effect evidence:** independently reread application, semantic, pixel,
   focus, and input-leak state. Delivery success alone is not effect success.

Application or title selection may be a convenient discovery query. It must
resolve to an exact window identity before a bounded action. A provider that
captures the desktop and crops to window bounds must advertise that honestly;
the result is not equivalent to isolated per-window capture.

Transient system UI sometimes has no stable child relationship to the
application window. The common contract therefore needs explicit surface
scopes in addition to exact windows: desktop shell, menu bar, taskbar or Dock,
notification area, popup/menu, dialog or sheet, and secure/protected desktop.

## Conformance fixture direction

**Decision:** Build or adopt deterministic fixtures, but keep fixture success
separate from real system-shell acceptance. A fixture proves action delivery
and observation mechanics; Start, taskbar, System Settings, Dock, menu extras,
desktop portals, and other platform-owned surfaces prove real OS reach.

The desktop fixture family should include:

- native controls plus Electron/Tauri or embedded-web surfaces;
- multiple top-level windows in one process and multiple processes;
- owned and unowned dialogs, sheets, popovers, menus, context menus, tooltips,
  status/menu-bar items, and layered or compositor-backed windows;
- click, value, text, keys, hotkeys, scroll, drag, selection, clipboard, file
  chooser, lifecycle, geometry, minimize, fullscreen, and close behaviors;
- unique accessibility identifiers and labels where the fixture owns them,
  without relying on such ideal metadata for system UI;
- application-owned counters, journals, or state endpoints as independent
  effect oracles;
- foreground sentinels and physical-cursor observers to prove background
  non-interference and detect leaked input; and
- the same scenario catalog through local and remote facade calls.

**Proposal:** Reuse the behavioral shape of Cua Driver's cross-platform
catalog and Peekaboo's macOS Playground rather than inventing an unstructured
demo application. The project acceptance suite should remain ours so the same
cases can compare Cua Driver, WinApp, Touchpoint, Peekaboo, or future adapters.

## Recommended next research

1. Run current Cua Driver and WinApp against the Windows system-shell
   acceptance contract, including background occlusion and elevated-window
   boundaries.
2. Reproduce exact-window identity, capture, semantic scope, and background
   delivery in two windows from the same process and two processes.
3. Run the same fixture through a local caller and an authenticated remote
   caller without granting either route host/hypervisor input.
4. On macOS, compare Cua Driver, Peekaboo, Touchpoint, and Agent Device against
   the same exact-window cases and inspect permission identity and private-API
   requirements.
5. On Linux, combine a common semantic provider with an isolated KWin session,
   then record the X11, XWayland, Sway, GNOME, and KWin capability differences
   rather than claiming generic Wayland support.

**Open:** After the Windows evidence, decide whether the common desktop plane
should directly depend on current Cua Driver, wrap multiple upstream providers,
or extract a smaller resident core. Do not decide that question from API shape
alone.

# WinApp CLI

Upstream: [microsoft/winappCli](https://github.com/microsoft/winappCli)

Declared license: [MIT](https://github.com/microsoft/winappCli/blob/main/LICENSE)
for the repository. Dependency and packaged-tool licenses have not been audited
for redistribution here.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `adopted` | `winvm-testbed` installs WinApp and reaches it through an interactive-session relay. Application and real-shell gap cells have live evidence, but no complete shared provider-wide conformance matrix exists. |
| Other platforms | Unsupported | WinApp is a Windows provider. |

Evidence links:

- [WinVM UI automation](../../../winvm-testbed/docs/ui-automation.md)
- [WinVM architecture](../../../winvm-testbed/docs/architecture.md)
- [WinVM known problems](../../../winvm-testbed/docs/problems.md)
- [Windows shell findings](../../../machine-control-spike/docs/windows-shell-findings.md)
- [upstream UI automation reference](https://github.com/microsoft/winappCli/blob/main/docs/ui-automation.md)

## Architecture and depth

**Current — adopted:** WinApp is a Windows CLI over UI Automation and native
window/capture facilities. It discovers processes and HWNDs, inspects bounded
UIA trees, searches elements, invokes patterns, clicks, focuses, changes
values, launches applications, and captures a selected application, window,
dialog set, or element. A screen-capture option handles popups and overlays
that `PrintWindow`-style capture omits, with different foreground consequences.

WinVM runs WinApp in the logged-in desktop through a non-elevated scheduled
relay because OpenSSH runs in session 0. The same-user named-pipe bridge is a
useful existing resident route. UIPI still prevents it from controlling
higher-integrity or secure-desktop surfaces.

Observed limitations include partial UIA exposure for packaged frames and
embedded WebView2, a semantic InvokePattern acknowledgement that did not cause
the intended application transition, and the need to re-inspect after material
actions. This is concrete evidence for separating dispatch from effect.

The real-shell run also established concrete strengths. WinApp exposed the
otherwise Cua-invisible taskbar and its Start, application, notification,
clock, and desktop controls. Semantic click activated a minimized taskbar
application; pattern-aware invoke changed ordinary maximize, restore,
minimize, and close state. It inspected the semantically rich inner Settings
window after activating the packaged outer frame, and it captured exact HWNDs
that Cua's registry could not address. A focus precondition correctly refused
unsafe synthetic click until the target window was foreground.

## North Star fit

WinApp provides strong Windows semantic and window capture primitives but not
the whole target-controller contract. It lacks the cross-platform session,
authorization, route/effect, conformance-fixture, and remote-carrier structure
already present in Cua. Its narrow Windows focus can also be an advantage when
filling a platform-specific gap.

## Current disposition

**Decision:** Preserve WinApp as the adopted Windows comparison route and a
required component of the Windows shell adapter behind the owned hybrid
facade. Route it only for capabilities it demonstrably supplies; do not rerun
already-settled Cua experiments merely to create symmetry.

**Open:** Measure exact-window capture under occlusion/minimization,
event-aware waits, provider failover rules, and local/remote result
normalization through the proposed facade.

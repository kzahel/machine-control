# WinApp CLI

Upstream: [microsoft/winappCli](https://github.com/microsoft/winappCli)

Declared license: [MIT](https://github.com/microsoft/winappCli/blob/main/LICENSE)
for the repository. Dependency and packaged-tool licenses have not been audited
for redistribution here.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `adopted` | `winvm-testbed` installs WinApp and reaches it through an interactive-session relay for ordinary semantic automation. Specific behaviors have live operational evidence, but no complete shared conformance matrix exists. |
| Other platforms | Unsupported | WinApp is a Windows provider. |

Evidence links:

- [WinVM UI automation](../../../winvm-testbed/docs/ui-automation.md)
- [WinVM architecture](../../../winvm-testbed/docs/architecture.md)
- [WinVM known problems](../../../winvm-testbed/docs/problems.md)
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

## North Star fit

WinApp provides strong Windows semantic and window capture primitives but not
the whole target-controller contract. It lacks the cross-platform session,
authorization, route/effect, conformance-fixture, and remote-carrier structure
already present in Cua. Its narrow Windows focus can also be an advantage when
filling a platform-specific gap.

## Current disposition

**Decision:** Preserve WinApp as the adopted Windows comparison route and a
possible supplemental adapter. Compare it with Cua only on common acceptance
cases or demonstrated gaps; do not rerun already-settled Cua experiments merely
to create symmetry.

**Open:** Measure desktop-root shell coverage, transient-surface behavior,
exact-window capture under occlusion/minimization, event-aware waits, and
local/remote result normalization through the proposed facade.

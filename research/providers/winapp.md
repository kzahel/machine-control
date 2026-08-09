# WinApp CLI

Upstream: [microsoft/winappCli](https://github.com/microsoft/winappCli)

Declared license: [MIT](https://github.com/microsoft/winappCli/blob/main/LICENSE)
for the repository. Dependency and packaged-tool licenses have not been audited
for redistribution here.

Last corpus review: 2026-08-09.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `adopted` | `winvm-testbed` reaches WinApp through an interactive-session relay. It is differential-only for the resident runtime. Application and real-shell cells have live evidence, including a same-surface Tactical 004 differential, but no complete shared provider-wide conformance matrix exists. |
| Other platforms | Unsupported | WinApp is a Windows provider. |

Evidence links:

- [WinVM UI automation](../../../winvm-testbed/docs/ui-automation.md)
- [WinVM architecture](../../../winvm-testbed/docs/architecture.md)
- [WinVM known problems](../../../winvm-testbed/docs/problems.md)
- [Windows shell findings](../../../machine-control-spike/docs/windows-shell-findings.md)
- [Windows provider-composition result](../../docs/tactical/004-windows-provider-composition-and-agent-ergonomics.md)
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

**Current — Tactical 004 differential:** WinApp 0.5.0 was rerun through the
testbed relay against the deterministic fixture, taskbar, Settings, exact
taskbar capture, and maximize behavior after the resident Cua/native facade was
working. It reached the same required fixture and OS effects, but did not
demonstrate greater semantic reach, capture fidelity, effect observability, or
agent ergonomics for any tested operation. The owned native route now covers
the shell/state/capture gaps that previously made WinApp appear required. The
end-to-end WinApp CLI/relay calls also took roughly 5.6–6.8 seconds in those
cells, materially slower than the resident routes; transport/startup and
provider-local timing are not claimed to be identical measurements.

## North Star fit

WinApp provides strong Windows semantic and window capture primitives but not
the whole target-controller contract. It lacks the cross-platform session,
authorization, route/effect, conformance-fixture, and remote-carrier structure
already present in Cua. Its narrow Windows focus can also be an advantage when
filling a platform-specific gap.

## Current disposition

**Decision:** Preserve WinApp as the adopted `winvm-testbed` comparison and
diagnostic route, but do not install or adapt it into the resident runtime
without a newly measured operation-level advantage. The current Windows
platform-depth provider is owned native UIA/Win32. Do not rerun already-settled
Cua experiments merely to create symmetry.

**Open:** Exact-window capture under occlusion/minimization and broader
event-aware behavior could still justify a future WinApp cell. Provider
failover and local/remote normalization are now proven through the resident
Cua/native facade rather than this external route.

# Windows Control Research

Status: first implementation platform; Cua and WinApp have real target
evidence, while other candidates remain source review or search triage.

Current decision topic:
[`windows-resident-control.md`](../../topics/windows-resident-control.md).

Bounded execution plan:
[`Tactical 000`](../../docs/tactical/000-windows-resident-control-vertical-slice.md).

## Platform acceptance surface

Windows depth is not established by controlling one ordinary application. The
resident stack must cover:

- normal, packaged, Electron/WebView, and elevated application windows;
- exact HWND identity, UIA scope, dialogs, popups, and capture fidelity;
- Start, taskbar, notification area, shell flyouts, Settings, and window
  management;
- semantic, native Win32/Shell, and guest-local pixel/input routes;
- background focus, z-order, and physical-cursor non-interference;
- the active interactive session, logout, lock, user switching, RDP/console,
  integrity, UIAccess, and secure-desktop state;
- local and authenticated remote calls through the same logical contract; and
- deterministic fixture effects plus real Windows-shell effects.

## Candidate matrix

| Candidate | Evidence | Demonstrated value | Material gaps or unknowns | Current disposition |
| --- | --- | --- | --- | --- |
| [Cua Driver](../providers/cua-driver.md) | `conformance-tested` for significant normal/elevated/session behavior | Exact-window state, UIA, capture, background actions, action/effect contract, sessions, fixtures | Cross-integrity pipe defect, lock/secure-desktop truth, usable UIAccess forwarding, protected broker, complete shell track | Provisional normal-user core |
| [Open Computer Use](../providers/open-computer-use.md) | `source-reviewed` | Compact agent-neutral Computer Use CLI/MCP over UIA and Win32 messages | No local live test; thinner multi-window/session/effect/remote contract | First common-provider comparison set |
| [WinApp](../providers/winapp.md) | `adopted` by WinVM; selected behaviors live-tested | Mature Windows UIA CLI, HWND targeting, dialogs, application/window screenshots, existing relay | Thinner session/result contract, WebView gaps, invoke without effect, no protected route, incomplete shared matrix | Adopted comparison and supplement |
| Cua plus WinApp/native helpers | `proposal` | Common contract plus best Windows-specific components | Adapter selection, duplicate semantics, route disclosure, stale-reference translation | Most likely practical composition if gaps are measured |
| [Terminator](../providers/terminator.md) | `source-reviewed` | Substantial Windows-only Rust/UIA implementation | No local integrity, shell, lock, effect, or fixture evidence | Second-round candidate |
| [Touchpoint](../providers/touchpoint.md) | `source-reviewed` | Small common facade; UIA/HWND/CDP | No local evidence; framebuffer-crop capture; thinner result/session model | Common-provider alternative |
| [OculOS](../providers/oculos.md) | `source-reviewed` | Resident REST/MCP service shape; Windows is its deepest backend | Live behavior and contract strength unproven | Architecture reference |
| [native-devtools-mcp](../providers/native-devtools-mcp.md) | `source-reviewed` | Exact HWND capture, UIA snapshots, OCR/CDP | Windows semantic ref actions lag macOS | Subsystem reference |
| Computer Use | installed-provider possibility; no independent contract audit here | Token-efficient agent-coupled control | Proprietary, agent-coupled, not an independently addressable resident facade | Optional supplement/benchmark |
| New native controller | design option only | Complete ownership of UIA/WGC/input/session/broker behavior | Highest implementation and maintenance cost; duplicates proven code | Defer unless layering fails |

Search-triage alternatives include Windows-MCP and mcp-windows. Microsoft UFO
has a pinned broad architecture review but not an isolated provider evaluation.
They should advance only when a measured gap or distinct architecture justifies
deeper source review.

## Investigations completed

### Cua Driver

**Current — conformance-tested:** The recent spike audited Cua Driver 0.17.0,
built or installed it in controlled Windows and macOS VMs, and recommended it
as the provisional normal-user evaluation core. This was completed hours—not
an architectural generation—before the wider provider survey.

Windows evidence includes:

- an ordinary Medium-integrity WPF application with a 37-element UIA tree,
  exact-window images, background semantic effect, and no focus theft;
- source-built WinUI/Electron fixture coverage retained as toolkit evidence;
- Medium-to-High enumeration/capture with UIA and input constrained by UIPI;
- successful High-to-High operation, but with authority too broad for a
  personal-machine default;
- an existing but not live-forwarded UIAccess worker;
- UAC consent-desktop capture refusal with insufficient structured state;
- lock-screen capture and continued window enumeration despite an inaccurate
  `desktop_unlocked` policy label;
- terminal revoke behavior while locked; and
- a named-pipe authentication defect when a lower-integrity daemon attempts to
  identify a higher-integrity client.

Authoritative details:

- [fit matrix](../../../machine-control-spike/docs/cua-fit-matrix.md)
- [Windows findings](../../../machine-control-spike/docs/windows-findings.md)
- [phase recommendation](../../../machine-control-spike/docs/phase-1-recommendation.md)

The upstream branch moved after the pin while retaining the same release
version. Some same-day commits harden Windows discovery/input, but the core
exact-window, result, and fixture architecture was already present in the
spike. Review relevant deltas narrowly; do not characterize the spike as an
old product evaluation or rerun it wholesale without a changed question.

### WinApp through WinVM

**Current — adopted:** WinVM installs Microsoft WinApp and invokes it in the
interactive desktop through a same-user named-pipe relay because SSH runs in
session 0. It provides real ordinary UIA inspection and action capability
without focusing the host VM window.

Observed results include:

- application and HWND discovery, bounded UIA inspection and search;
- invoke, semantic click, focus, value changes, launch, and selected-window
  screenshots;
- normal user-token operation with UIPI and secure-desktop limits;
- an InvokePattern acknowledgement that produced no application transition,
  while a semantic click on the same control worked; and
- missing embedded WebView2 controls that required visual/input fallback.

Authoritative details:

- [WinVM UI automation](../../../winvm-testbed/docs/ui-automation.md)
- [WinVM architecture](../../../winvm-testbed/docs/architecture.md)
- [WinVM known problems](../../../winvm-testbed/docs/problems.md)

WinApp has not yet run the complete Cua-style fixture matrix or the system-shell
acceptance track. Its existing operational evidence should be preserved rather
than inflated or dismissed.

## Architecture options

### Cua-centered resident stack

Use Cua at ordinary user integrity for normal semantics, capture, and input.
Add a small Windows session proxy for active-session discovery, reconnect,
authenticated local/remote transport, and truthful input-desktop state. Add a
narrow protected broker later only for explicitly authorized operations that
cannot occur in the user session.

**Decision:** This is the leading path because it reuses the deepest tested
contract and fixture architecture while keeping trust, lifecycle, and recovery
outside Cua.

### Hybrid Cua plus Windows-specific adapters

Keep Cua as the contract/runtime spine but route a measured operation through
WinApp, CDP, Win32/Shell, or another native helper when it demonstrably provides
better semantics or capture. The response must name the actual route and must
not silently change focus, privilege, or fidelity.

**Proposal:** This is likely for shell/transient surfaces, but should emerge
from acceptance failures rather than speculative duplication.

### WinApp-centered facade

Build project sessions, results, verification, remote transport, and capability
metadata around the existing WinVM relay and WinApp operations.

**Open:** This remains credible if Cua's integration or maintenance cost proves
unacceptable. It currently requires more common-contract work and gives up
useful cross-platform reuse.

### New native implementation

Build an owned service, interactive companion, UIA/WGC/Win32 adapters, input
engine, session proxy, and protected broker.

**Decision:** Defer. Implement only narrowly missing Windows components unless
evidence shows that Cua/WinApp cannot be layered or upstreamed coherently.

## Next evidence

1. Use Cua first on the real Windows shell track: Start, taskbar, notification
   area, flyouts, Settings, dialogs, and window management.
2. Run WinApp or a native route on the same case only where it is the current
   adopted baseline or Cua exposes a material gap.
3. Record exact window, semantic, capture, action, delivery, effect, focus,
   z-order, cursor, and route observations separately.
4. Prototype the session proxy before designing the protected broker.
5. Exercise the same logical operation locally and through the authenticated
   outside transport.
6. After the resident stack passes, bootstrap and seal it from a clean image.

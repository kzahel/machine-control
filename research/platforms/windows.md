# Windows Control Research

Status: first implemented platform; the resident Cua/native composition is
adopted and conformance-tested on ARM64 VM and physical x64, WinApp remains a
live external differential, and public-ISO factory paths are accepted on ARM64
UTM/macOS and native x86_64 libvirt/Linux. Other candidates remain source
review or search triage.

Current decision topic:
[`windows-resident-control.md`](../../topics/windows-resident-control.md).

Bounded execution plan:
[`Tactical 000`](../../docs/tactical/000-windows-resident-control-vertical-slice.md).

Completed system-shell acceptance run:
[`Tactical 001`](../../docs/tactical/001-windows-system-shell-acceptance.md).

Completed full-control and provider-composition runs:
[`Tactical 002`](../../docs/tactical/002-windows-full-target-native-control.md)
and
[`Tactical 004`](../../docs/tactical/004-windows-provider-composition-and-agent-ergonomics.md).

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
| [Cua Driver](../providers/cua-driver.md) | `adopted` for ordinary-session semantics/action/capture; broader behavior `conformance-tested` | Exact-window state, UIA, capture, background actions, action/effect contract, sessions, fixtures | Filtered registry omits taskbar and some visible shell HWNDs; selected UIA window-state no-ops; cross-integrity and protected gaps | Installed common-runtime adapter inside owned facade |
| [Open Computer Use](../providers/open-computer-use.md) | `source-reviewed` | Compact agent-neutral Computer Use CLI/MCP over UIA and Win32 messages | No local live test; thinner multi-window/session/effect/remote contract | First common-provider comparison set |
| [WinApp](../providers/winapp.md) | `adopted` by WinVM; application, shell, and Tactical 004 differential live-tested | Mature Windows UIA CLI, taskbar/Settings semantics, HWND targeting, pattern-aware state actions, screenshots, existing relay | Thinner session/result contract, WebView gaps, some invokes without effect, no protected route, high observed CLI/relay latency | Retained external differential; no installed adapter without a measured advantage |
| Cua plus owned native helpers | `adopted` and `conformance-tested` | Common runtime plus deeper Windows-specific shell, state, session, fallback, and protected operations | Production authorization and broader environment coverage remain | Implemented direction |
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

**Current — adopted runtime adapter:** Tactical 004 packages the digest-pinned
0.17.0 release as an unmodified private child of the Medium helper. VM and
physical conformance proved compact snapshot, normalized opaque references,
semantic action with an application-owned marker, exact capture, timeout,
crash/restart, provider absence, stale reference/generation rejection, and
local/remote parity. Cua never runs in the protected LocalSystem plane; the
owned provider handles shell, state, session, fallback, and protected gaps.

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

- [WinVM UI automation](../../platforms/windows/docs/ui-automation.md)
- [WinVM architecture](../../platforms/windows/docs/architecture.md)
- [WinVM known problems](../../platforms/windows/docs/problems.md)

WinApp has not run the complete Cua-style fixture matrix or an independent
duplicate of every shell cell. It did run the adopted-baseline and measured-gap
cells in the system-shell track. Preserve that operational evidence without
inflating it into a full provider-wide conformance result.

**Current — external differential:** Tactical 004 reran WinApp 0.5.0 against
the fixture, taskbar, Settings, exact capture, and maximize cells after the
owned composition was live. It reached the required effects but offered no
tested operation-level advantage over Cua/native. Its roughly 5.6–6.8 second
end-to-end CLI/relay cells were also materially slower than the resident
routes, although those measurements include different transport/startup
costs. WinApp therefore remains installed in the testbed as comparison and
diagnostic evidence, not in the product runtime.

### Real Windows system shell

**Current — conformance-tested composition:** The 2026-08-05 acceptance run
exercised the desktop root, Start/Search, taskbar, notification area and
flyout, Settings, an owned dialog, and ordinary window state. It recorded Cua
delivery separately from independent WinApp/native effect observations and
used no host VM-window route.

The run established that Cua is valuable but not sufficient alone. Cua handled
compact Start/Search and flyout semantics, UIA text and control actions,
generation-scoped references, exact-window capture, dialog control, and
confirmed frame placement. Its filtered registry omitted the taskbar and later
omitted still-visible Search or Settings HWNDs; title-bar UIA clicks were
independently verified no-ops. WinApp/native routes closed the measured gaps
with taskbar semantics and activation, pattern-aware state actions, packaged
Settings inner-window semantics, and exact-window capture.

Authoritative details:

- [Windows shell findings](../../../machine-control-spike/docs/windows-shell-findings.md)
- [repeatable shell probe](../../../machine-control-spike/scripts/windows-shell-cua-probe.ps1)

**Current — installed composition:** Tactical 004 reran the representative
shell suite through the resident facade on ARM64 and physical x64. Cua handled
the deterministic ordinary-window snapshot/action/capture workflow; owned
native UIA/Win32 handled compact shell projections, window state and effect
readback, authorized input fallbacks, sessions, UAC secure desktop, and the
High-integrity fixture. Both local and authenticated remote placements used
the same operations and result vocabulary without outer input.

Tactical 006 extended that evidence to Calculator, Settings, Character Map,
and Notepad in identical 51-call remote and target-local workflows. Windows
`IApplicationActivationManager` plus AppUserModelID window association replaced
Run-dialog launch for registered applications. Native UIA `WindowPattern`
replaced unreliable `ShowWindowAsync` as the primary packaged-window lifecycle
route. Cua remained the richer ordinary-window observer and exact-capture route,
while native UIA supplied deterministic Calculator actions, system semantics,
and independent effects. Compact and digest-matched unchanged projections
materially reduced repeated Calculator and Settings payloads without removing
the full projection.

**Current — public-ISO appliance acceptance:** Tactical 007 created a blank
ARM64 target from Microsoft's public multi-edition ISO and reached unactivated
Windows 11 Pro without routine guest input. The run proved injected drivers,
staged installation/seed-media removal, key-only SSH, target-attested product
installation, UAC, local/remote real applications, pre-login protected control,
stock password login, and disk-only reboot. It also exposed two implementation
facts now incorporated into the adopted stack: fresh OpenSSH host private keys
need a well-known-SID ACL repair, and current packaged apps may require separate
content and application-frame HWNDs for UIA versus capture/lifecycle. The exact
execution record is
[`Tactical 007`](../../docs/tactical/007-windows-iso-factory-acceptance.md).

**Current — native x86_64 Linux-host acceptance:** Tactical 028 created a
separate Windows 11 appliance from an official x64 ISO on a hardware-only
libvirt/QEMU/KVM route. Provider inspection and fixtures reject TCG,
cross-architecture emulators, non-KVM domains, non-Q35 machines, missing
Secure Boot, missing TPM 2.0, and stale identity. The live appliance passed
VirtIO/QEMU-agent bootstrap, hardened OpenSSH, full resident application and
provider-composition conformance, exact-source portable/native certification,
disk-only protected Winlogon control, typed one-shot login, and a discarded
QCOW2-workspace effect. Ordinary control kept outer UI prohibited.

## Architecture options

### Cua-centered resident stack

Use Cua at ordinary user integrity for normal semantics, capture, and input.
Add a small Windows session proxy for active-session discovery, reconnect,
authenticated local/remote transport, and truthful input-desktop state. Add a
narrow protected broker later only for explicitly authorized operations that
cannot occur in the user session.

**Decision:** Cua remains the common runtime adapter, but this option alone is
superseded by the measured hybrid composition below.

### Hybrid Cua plus Windows-specific adapters

Keep Cua as the contract/runtime spine but route a measured operation through
WinApp, CDP, Win32/Shell, or another native helper when it demonstrably provides
better semantics or capture. The response must name the actual route and must
not silently change focus, privilege, or fidelity.

**Decision — implemented:** This is the adopted path. Shell acceptance
measured concrete taskbar, packaged-window, window-state,
registry-visibility, capture, session, and protected gaps. The owned
facade/session proxy routes those operations through its native Windows
adapter, with actual route, provider attempts, delivery, effect, and fallback
disclosed. WinApp remains available externally but is not required by the
installed composition.

### WinApp-centered facade

Build project sessions, results, verification, remote transport, and capability
metadata around the existing WinVM relay and WinApp operations.

**Decision:** Defer unless a future measured gap or Cua maintenance failure
outweighs the now-proven resident composition. It requires more common-contract
work, gives up useful cross-platform reuse, and showed no operation-level
advantage in the Tactical 004 differential.

### New native implementation

Build an owned service, interactive companion, UIA/WGC/Win32 adapters, input
engine, session proxy, and protected broker.

**Decision:** Defer. Implement only narrowly missing Windows components unless
evidence shows that Cua/WinApp cannot be layered or upstreamed coherently.

## Next evidence

1. Extend the proven four-application workflow to remaining toolkits,
   transient surfaces, multi-display, occlusion, and longer soak behavior.
2. Exercise additional Windows builds, hardware, console/RDP, fast-user-switch,
   and policy/localization configurations.
3. Harden endpoint authorization and artifact transfer beyond the current
   dedicated-appliance/local-user boundary.
4. Revisit Cua release provenance and upstream deltas only when a concrete
   reliability, packaging, security, or missing-capability question changes.
5. Repeat the accepted factory lane on another Windows build or x64 appliance
   when that coverage is needed; include the corrected OpenSSH ACL bootstrap
   in the initial seed rather than as an acceptance-run repair.

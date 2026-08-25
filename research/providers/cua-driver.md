# Cua Driver

Upstream: [trycua/cua `libs/cua-driver`](https://github.com/trycua/cua/tree/main/libs/cua-driver)

Declared license: [MIT](https://github.com/trycua/cua/blob/main/LICENSE.md)
for the repository. Upstream documents MIT-0 terms for skill copies published
through ClawHub; treat that as a narrower distribution boundary, not as a
change to the repository license.

Last corpus review: 2026-08-25.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `adopted` | The resident runtime packages Cua 0.17.0 as its Medium-integrity semantics/action/capture adapter. ARM64 VM and physical x64 conformance passed with independent effects, timeout/crash/absence behavior, local/remote parity, and native adapters for shell, state, session, protected, and cross-integrity gaps. |
| macOS | `adopted` for default text insertion and the measured Electron semantic route; `conformance-tested` more broadly | The resident facade selects Cua text insertion because it produced the independent AppKit value effect that native Unicode delivery did not. Cua also produced a deterministic Electron button effect where native AX only acknowledged delivery. Native AX remains deeper for Dock, Control Center, and Swing. |
| Linux | `conformance-tested` on Ubuntu 24.04 GNOME 46 Wayland | GTK and Chromium semantics/actions, foreground portal input, and GNOME Shell helper window capture passed independent effects. Native AT-SPI remained deeper for the measured Qt route, and native clipboard-backed input preserved Unicode that Cua's libei fallback omitted. |
| ChromeOS/iOS/Android | Unsupported as first-class Cua Driver platforms | They require separate provider families or a future adapter. |

Exact source and experiment evidence:

- [Cua fit matrix](../../../machine-control-spike/docs/cua-fit-matrix.md)
- [phase recommendation](../../../machine-control-spike/docs/phase-1-recommendation.md)
- [Windows findings](../../../machine-control-spike/docs/windows-findings.md)
- [Windows shell findings](../../../machine-control-spike/docs/windows-shell-findings.md)
- [macOS findings](../../../machine-control-spike/docs/macos-findings.md)
- [Linux findings](../../../machine-control-spike/docs/linux-findings.md)
- [Windows provider-composition result](../../docs/tactical/004-windows-provider-composition-and-agent-ergonomics.md)

## Architecture

**Current — source-reviewed and live-tested:** A Rust runtime supplies CLI,
MCP, language SDK, daemon/service, embedded, and remote-carrier seams. Native
calls bind process and window identity; combined window state returns semantics
and pixels; element references are snapshot/runtime scoped. Sessions,
authorization ceilings, cancellation, terminal revoke, action routes, delivery,
effect, evidence, escalation, and unknown completion are explicit concepts.

Windows uses UIA, Win32, native input, and several capture routes. macOS uses
AX, WindowServer capture, public event APIs, and private SkyLight routes for
some background behavior. Linux combines AT-SPI with X11 or
compositor-specific Wayland discovery, capture, activation, and input.

Source-built AppKit, SwiftUI, WKWebView, WPF, WinUI 3, WebView2, GTK, Electron,
and Tauri fixtures exercise semantic/pixel addressing, foreground/background
delivery, and window/desktop scope. Independent fixture, focus, z-order,
cursor, leaked-input, accessibility, and pixel oracles are a particularly
strong match for this project's conformance direction.

## Adjacent Cua sandbox scope

**Current — upstream-claimed, not adopted here:** The wider Cua product now
documents local and hosted full-computer sandboxes alongside Cua Driver. A
sandbox combines shell and GUI access in one isolated machine; current docs
describe Linux containers, macOS/Windows/Android VMs, immutable starting
images, reusable warm pools, named pool claims, and claim expiry. See
[How sandboxes work](https://cua.ai/docs/concepts/how-sandboxes-work),
[sandbox pool claims](https://cua.ai/docs/how-to-guides/sandbox/create-pool-with-python),
and [claim expiry](https://cua.ai/docs/how-to-guides/sandbox/expire-pools-and-claims).

This broader service overlaps Machine Control's workspace and claim vocabulary
but does not change the current adoption boundary: the checked-in resident
runtime embeds pinned Cua Driver operations, not Cua Sandbox or Fleet. Machine
Control continues to own heterogeneous existing-target inventory, lifecycle,
provider arbitration, physical-device routes, protected/recovery policy, and
the cross-provider result contract.

## North Star fit

**Current:** The recent spike concluded that Cua is a strong normal-user
desktop-core candidate and recommended provisional adopt-and-extend, not a
fork. A same-version upstream review performed after the spike did not reveal a
new architecture; it reinforced capabilities already present in the audited
revision. Future upstream drift should receive targeted delta review rather
than being mistaken for a fresh product evaluation.

Direct fits include exact-window control, compact semantics, visual grounding,
background-first actions, explicit escalation, session and action-result
contracts, local/embedded execution, and a remote carrier seam.

Tactical 004 closed the Windows integration items with an owned session proxy,
authenticated carrier use, capability/result projection, native shell adapter,
and protected broker. Remaining provider-wide adjacent work includes:

- target/provider capability descriptions with route, coordinate, omission,
  lock-state, and fidelity data on platforms beyond the exercised Windows
  facade;
- first-class ChromeOS and device-provider integration outside the current
  three desktop backends; and
- high-volume image/artifact transfer outside base64-oriented surfaces.

[`Tactical 008`](../../docs/tactical/008-macos-ordinary-session-resident-control.md)
added a macOS resident adapter without forking Cua. Both providers return the
facade's normalized application, window, semantic element, and capture
vocabulary. Cua is the measured default only for `input.text`; native macOS
routes remain the ordinary default for the rest of the accepted surface.
Explicit provider selection fails closed rather than falling back.

[`Tactical 011`](../../docs/tactical/011-macos-java-electron-framework-coverage.md)
adds a live Electron differential cell. Native AX returned the labelled
Chromium button and acknowledged `AXPress` without changing the independent
oracle. Cua returned a compact semantic projection and its background
accessibility action produced the effect. The accepted cell activates the
target and polls Cua's newly frontmost semantic tree boundedly before acting;
an empty projection or action acknowledgement without the file effect fails.

[`Tactical 012`](../../docs/tactical/012-linux-gnome-wayland-resident-control.md)
compared the same pinned 0.17.0 source against the owned resident on GNOME 46
Wayland. Cua produced independently verified GTK and Chromium actions, rich
combined browser semantics, foreground portal/libei input, and arbitrary
target-window capture through its pinned WinRects GNOME Shell helper. The
owned native route remained deeper for Qt/XWayland semantics and reliable
Unicode input. Portal consent was itself controllable inside the target, but
its setup and round-trip cost make the explicitly authorized appliance broker
the better default for this dedicated VM. Cua remains optional and unmodified.

## Current disposition

**Decision — adopted on Windows:** Treat Cua as the common normal-user runtime
adapter and default first route for operations it performs well. The Windows
runtime supervises the unmodified 0.17.0 release as a private
per-helper-generation child, disables telemetry and update checks, and keeps it
out of the LocalSystem protected process. The owned native adapter supplies
measured taskbar, state, registry-visibility, fallback-capture, session, and
protected behavior. Cua does not own provider arbitration, testbed lifecycle,
cross-host coordination, protected authority, outer recovery, or the
project-wide ergonomic contract.

**Decision — optional on Linux GNOME Wayland:** Route ordinary GNOME appliance
control through the owned resident and select Cua explicitly for its measured
combined tree/image or arbitrary target-window strengths. Do not fork Cua for
the accepted profile; preserve the provider boundary and revisit the fork gate
only if broader Linux profiles expose repeated gaps that wrapping cannot
address.

The ARM64 and x64 package manifests pin the evaluated release artifacts by
SHA-256 and include the upstream MIT license. The source review remains pinned
separately because the upstream release binary does not attest which source
commit produced it. Provider crash invalidates facade references, permits one
supervised restart per helper generation, and then uses only an explicitly
reported authorized observation fallback.

**Open:** Longer-running and broader-platform evidence may still reveal a
maintenance or packaging reason for a derivative. The current Windows result
supports continued wrapping; it does not meet the project's fork gate.

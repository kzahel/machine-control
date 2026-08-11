# System Map

This map answers two questions: “which program should do this?” and “where
should a change live?” It describes current ownership, not a deployment
requirement that every component always be present.

## Coordination and inventory

| Component | Current role | Does not own |
| --- | --- | --- |
| [`~/code/yepanywhere`](../yepanywhere/README.md) | Agent provider sessions, user supervision, relay transport, peer identity/grants, and proposed cross-host delegation | VM/device implementation details; generic hypervisor or desktop drivers |
| [`~/code/dotfiles/testbeds`](../dotfiles/testbeds/README.md) | Portable discovery of configured testbeds and read-only availability; link to each authoritative guide | Lifecycle implementation, UI control, recovery, product assertions |
| Consuming application repository | Builds, fixtures, test intent, application-specific assertions, and cross-platform campaign logic | Machine provisioning and generic control transport |

YepAnywhere's delegation direction is documented in
[`cross-host-delegation.md`](../yepanywhere/topics/cross-host-delegation.md).
Delegation creates a normal worker session on a YA peer; it does not turn YA
into a raw proxy for every testbed CLI.

## Target-controller implementation boundary

| Repository | Current role | Does not own |
| --- | --- | --- |
| [`machine-control`](README.md) | Cross-platform architecture/research, the target-selecting common client and contracts, owned resident facades/provider boundaries, Windows service/session implementation, fixtures, and conformance corpus | Testbed lifecycle/bootstrap/recovery, private deployment inventory, YA delegation, or product assertions |

**Current:** The Windows-first runtime establishes the implementation boundary
between authenticated local/remote callers, a Medium interactive-session
companion, replaceable providers, and a typed LocalSystem protected route. Its
physical x64 evidence covers ordinary system-shell control, UAC secure desktop,
elevated applications, lock, logout, and Windows boot recovery. The dual-boot
testbed must explicitly reselect Windows after one-shot EFI `BootNext`; a
generic reboot otherwise returns to its default OS.

**Current:** One common client now selects and validates the Windows, macOS,
and Linux testbed adapters, while each adapter retains its own lifecycle and
guest transport. The three residents pass one guarded common semantic,
effect, capture, artifact, and local/outside parity workflow. This is a shared
contract and entry experience, not one universal resident implementation.
ChromeOS and device providers remain the next adapter families; they must not
move target-specific lifecycle or recovery ownership into this repository.

## Desktop VM testbeds

| Repository | Administration/inner control | Outer control |
| --- | --- | --- |
| [`winvm-testbed`](../winvm-testbed/README.md) | Authoritative UTM lifecycle, minimized doctor, PowerShell/SSH administration, and bounded access to the Windows resident | UTM/QEMU screenshot, keyboard, scan codes, and pointer remain explicit recovery routes |
| [`macvm-testbed`](../macvm-testbed/README.md) | Authoritative Tart lifecycle, minimized doctor, selected guest administration, and bounded access to the macOS resident | Tart screenshot, pointer, and keyboard remain explicit recovery routes |
| [`linuxvm-testbed`](../linuxvm-testbed/README.md) | Authoritative UTM lifecycle, minimized doctor, guest/session execution, and bounded access to the Linux resident | UTM screenshot, keyboard, and pointer remain explicit recovery routes |

These repositories implement the right broad ordering: lifecycle and
administration, then resident semantic/capture/input control, with outer
pixels/input named only for bootstrap and recovery. Their guarded doctor and
common conformance paths now enforce that ordinary control does not reach the
outer route merely because it is convenient.

## Physical and device testbeds

| Repository | Current role | Important boundary |
| --- | --- | --- |
| [`chromeos-testbed`](../chromeos-testbed/README.md) | Root SSH, browser CDP, Chrome desktop accessibility, screenshots, and device-native input on a designated developer-mode Chromebook | Update-sensitive and guest-resident; not an independent physical recovery path |
| [`hardware-kvm-testbed`](../hardware-kvm-testbed/README.md) | Planned HDMI capture and USB HID for externally controlled physical hardware | Pixel/HID only; intended as outer recovery and independent observation, currently in bring-up |
| [`ios-device-testbed`](../ios-device-testbed/README.md) | Explicit physical-iPhone selection, signing, CoreDevice lifecycle, semantic XCTest, screenshots, input, leases, and recovery | The agent runs on the Mac; a stock iPhone cannot host a general YA worker |
| [`quest-testbed`](../quest-testbed/README.md) | Explicit ADB target selection, device state, deployment, leases, and recovery for Quest | Protected headset/account surfaces remain human gates |
| [`steamdeck-testbed`](../steamdeck-testbed/README.md) | Direct device administration and session-aware deployment/control | Physical recovery capability depends on available hardware and session state |
| Android through ADB | Installation, lifecycle, shell, screenshots, input, logs, and optional UIAutomator semantics | Usually controller-hosted rather than an on-device general agent |

## Research and candidate providers

| Component | Use it for | Do not make it |
| --- | --- | --- |
| [Research corpus](research/README.md) | Provider architecture/license/evidence dossiers and per-platform option comparisons | Exact experiment log, source-pin store, decision topic, or implementation |
| [`machine-control-spike`](../machine-control-spike/README.md) | Exact Cua pins, conformance evidence, macOS/Windows behavior, and security findings | The current architecture hub or production implementation |
| [Cua Driver](research/providers/cua-driver.md) | Spike-supported provisional normal-user desktop core; exact-window semantics/capture, explicit delivery/effects, sessions, and strong fixtures | Cross-host coordinator, testbed lifecycle owner, protected-control trust foundation, or owner of the common contract |
| [Open Computer Use](research/providers/open-computer-use.md) | Compact agent-neutral Computer Use CLI/MCP across Windows, macOS, and Linux; first common-provider comparison candidate | Proven session/result/remote core or exact-window equivalent without conformance evidence |
| [WinApp](research/providers/winapp.md) | Adopted WinVM UIA route, Windows comparison provider, and possible gap-filling adapter | Cross-platform core, effect oracle, or protected desktop provider |
| [Touchpoint](research/providers/touchpoint.md) | Small cross-platform AX/UIA/AT-SPI/CDP facade and exact-window identity reference | Proven occlusion-independent capture or Wayland-input solution without target validation |
| [Agent Device](research/providers/agent-device.md) | Current iOS XCTest provider and a source of compact agent-oriented snapshot/action/recovery behavior | Exact-window macOS control, native Windows control, or the overall desktop/control fabric |
| [Peekaboo](research/providers/peekaboo.md) | Deep macOS reference for exact-window capture, background action routing, transient system surfaces, and native fixture design | Cross-platform provider or protected-control boundary |
| [kwin-mcp](research/providers/kwin-mcp.md) | Linux/KWin reference for isolated target-native Wayland sessions, AT-SPI, compositor capture, and libei input | Proven universal Linux desktop or exact-window facade |
| YepAnywhere Device Bridge | Human remote viewing and fast pixel/input backends, especially its iOS Simulator work | Semantic agent control or the cross-platform orchestration contract |
| [RustDesk](research/providers/rustdesk.md) and similar remote desktop projects | AGPL-licensed reference architecture for session services, desktop switching, capture, and input | A wholesale trust boundary imported into the agent-facing system |

Detailed claims and evidence levels live in the
[provider index](research/providers/README.md) and
[platform index](research/platforms/README.md). Cross-provider decisions live
in [`provider-landscape.md`](topics/provider-landscape.md). Being listed here
does not mean a provider has passed on every advertised platform.

## Ownership rule

When adding a capability:

1. Put target-specific lifecycle, bootstrap, and recovery in the authoritative
   testbed.
2. Put reusable resident semantic behavior and provider adapters here; keep a
   target-specific native runner in its authoritative testbed when it is not a
   reusable machine-control component.
3. Put cross-provider capability vocabulary and conformance expectations here
   beside the implementation they govern.
4. Put worker creation, peer authorization, observation, and supervision in
   YepAnywhere coordination.
5. Put product-specific assertions in the consuming application repository.

Do not add the same operation independently to all five layers. Choose one
owner and expose it through adapters.

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

## Desktop VM testbeds

| Repository | Administration/inner control | Outer control |
| --- | --- | --- |
| [`winvm-testbed`](../winvm-testbed/README.md) | PowerShell/SSH administration plus WinApp UI Automation in the interactive Windows session | UTM/QEMU lifecycle, screenshot, keyboard, scan codes, and pointer recovery |
| [`macvm-testbed`](../macvm-testbed/README.md) | `tart exec` plus guest Accessibility helper | Tart lifecycle, screenshot, pointer, and keyboard recovery |
| [`linuxvm-testbed`](../linuxvm-testbed/README.md) | QEMU guest agent, user-session execution, and AT-SPI | UTM lifecycle, normalized screenshot, keyboard, and pointer recovery |

These repositories already implement the right broad ordering: administration,
then semantic desktop control, then outer pixels/input. The main missing
property is enforcement that ordinary worker agents do not reach the outer
route merely because it is convenient.

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
| [`machine-control-spike`](../machine-control-spike/README.md) | Exact Cua pins, conformance evidence, macOS/Windows behavior, and security findings | The current architecture hub or production implementation |
| [Cua](https://github.com/trycua/cua) | Reference contract, optional guest-user provider, and comparison adapter | Cross-host coordinator, testbed lifecycle owner, protected-control trust foundation, or required common core |
| [Agent Device](https://github.com/callstack/agent-device) | Current iOS XCTest provider and a source of agent-oriented snapshot/action/recovery behavior | The overall desktop/control fabric; its desktop backends do not replace the existing testbeds and it lacks native Windows desktop control |
| YepAnywhere Device Bridge | Human remote viewing and fast pixel/input backends, especially its iOS Simulator work | Semantic agent control or the cross-platform orchestration contract |
| RustDesk and similar remote desktop projects | Reference architectures for session services, desktop switching, capture, and input | A wholesale trust boundary imported into the agent-facing system |

## Ownership rule

When adding a capability:

1. Put target-specific lifecycle, bootstrap, and recovery in the authoritative
   testbed.
2. Put native semantic behavior in a guest/device provider owned by that
   testbed or a deliberately selected upstream dependency.
3. Put cross-provider capability vocabulary and conformance expectations here.
4. Put worker creation, peer authorization, observation, and supervision in
   YepAnywhere coordination.
5. Put product-specific assertions in the consuming application repository.

Do not add the same operation independently to all five layers. Choose one
owner and expose it through adapters.

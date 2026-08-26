# System Map

This map answers two questions: “which program should do this?” and “where
should a change live?” It describes current ownership, not a deployment
requirement that every component always be present.

The accepted consolidation direction is recorded in
[`repository-consolidation-and-publication.md`](topics/repository-consolidation-and-publication.md).
The platform testbeds listed below have completed their explicit cutovers, so
their public implementation lives under `machine-control`; private deployment
inventory remains in dotfiles, and any focused external repository is legacy
or generated one-way.

## Coordination and inventory

| Component | Current role | Does not own |
| --- | --- | --- |
| [`~/code/yepanywhere`](../yepanywhere/README.md) | Agent provider sessions, user supervision, relay transport, peer identity/grants, and proposed cross-host delegation | VM/device implementation details; generic hypervisor or desktop drivers |
| [`~/code/dotfiles/testbeds`](../dotfiles/testbeds/README.md) | Private concrete testbed inventory, controller availability, portable discovery, and locators for controller-local credential files; link to each current authoritative guide | Credential values, public lifecycle implementation, UI control, recovery, product assertions |
| Consuming application repository | Builds, fixtures, test intent, application-specific assertions, and cross-platform campaign logic | Machine provisioning and generic control transport |

Machine Control owns exact-resource target-use arbitration. A coordinator may
supply claimant/session metadata and manage renewal around active work, but the
claim contract does not name or require that coordinator. Private inventory
selects claim policy and state placement without becoming the live arbiter.

YepAnywhere's delegation direction is documented in
[`cross-host-delegation.md`](../yepanywhere/topics/cross-host-delegation.md).
Delegation creates a normal worker session on a YA peer; it does not turn YA
into a raw proxy for every testbed CLI.

## Target-controller implementation boundary

| Repository | Current role | Does not own |
| --- | --- | --- |
| [`machine-control`](README.md) | Cross-platform architecture/research, the target-selecting common client and contracts, owned resident facades/provider boundaries, Windows service/session implementation, fixtures, conformance corpus, and post-cutover public platform/testbed implementation | Pre-cutover external testbed implementation, private deployment inventory, YA delegation, or product assertions |

**Current:** The Windows-first runtime establishes the implementation boundary
between authenticated local/remote callers, a Medium interactive-session
companion, replaceable providers, and a typed LocalSystem protected route. Its
physical x64 evidence covers ordinary system-shell control, UAC secure desktop,
elevated applications, lock, logout, and Windows boot recovery. The dual-boot
testbed must explicitly reselect Windows after one-shot EFI `BootNext`; a
generic reboot otherwise returns to its default OS.

**Current:** One common client now selects and validates the Windows, macOS,
and Linux testbed adapters, while each adapter retains its own lifecycle,
workspace/storage policy, and guest transport. The three residents pass one
guarded common semantic, effect, capture, artifact, and local/outside parity
workflow. Workspace callers request persistent, isolated, or candidate intent;
the owning adapter chooses and reports the actual provider mechanism and binds
cleanup to a private exact-identity receipt. This is a shared contract and
entry experience, not one universal resident or hypervisor implementation.
ChromeOS and device providers remain the next families to receive more common
facade coverage. Their target-specific lifecycle and recovery already live in
their authoritative platform directories here; broader facade coverage must
not flatten their platform semantics into one generic implementation.

## Desktop VM testbeds

| Repository | Administration/inner control | Outer control |
| --- | --- | --- |
| [`platforms/windows`](platforms/windows/README.md) | Authoritative UTM/macOS and libvirt/Linux lifecycle/workspace policy, minimized doctor, PowerShell/SSH administration, and bounded access to the Windows resident | UTM or headless QEMU screenshot and input remain explicit recovery routes |
| [`platforms/macos`](platforms/macos/README.md) | Authoritative Tart lifecycle/COW-workspace policy, minimized doctor, selected guest administration, and bounded access to the macOS resident | Tart screenshot, pointer, and keyboard remain explicit recovery routes |
| [`platforms/linux`](platforms/linux/README.md) | Authoritative UTM/macOS and libvirt/Linux lifecycle/workspace policy, minimized doctor, guest/session execution, and bounded access to the Linux resident | UTM or headless QEMU screenshot and input remain explicit recovery routes |

These repositories implement the right broad ordering: lifecycle and
administration, then resident semantic/capture/input control, with outer
pixels/input named only for bootstrap and recovery. Their guarded doctor and
common conformance paths now enforce that ordinary control does not reach the
outer route merely because it is convenient.

## Physical and device testbeds

| Repository | Current role | Important boundary |
| --- | --- | --- |
| [`platforms/chromeos`](platforms/chromeos/README.md) | Root SSH, browser CDP, Chrome desktop accessibility, screenshots, and device-native input on a designated developer-mode Chromebook | Update-sensitive and guest-resident; not an independent physical recovery path |
| [`hardware-kvm-testbed`](../hardware-kvm-testbed/README.md) | Planned HDMI capture and USB HID for externally controlled physical hardware | Pixel/HID only; intended as outer recovery and independent observation, currently in bring-up |
| [`platforms/ios`](platforms/ios/README.md) | Explicit physical-iPhone selection, signing lifetime, typed common iOS operations, CoreDevice lifecycle, semantic XCTest, screenshots, input, leases, and recovery | The agent runs on the Mac; a stock iPhone cannot host a general YA worker |
| [`platforms/android`](platforms/android/README.md) | Explicit physical-handheld selection, common readiness, ADB administration/deployment/capture/input, and guarded one-shot PIN unlock | Phone keyguard policy is not inherited by Quest or every ADB derivative |
| [`platforms/quest`](platforms/quest/README.md) | Explicit ADB target selection, device state, deployment, leases, and recovery for Quest | Protected headset/account surfaces remain human gates |
| [`platforms/steamdeck`](platforms/steamdeck/README.md) | Direct device administration and session-aware deployment/control | Physical recovery capability depends on available hardware and session state |
| Android-family shared ADB provider | Executable discovery, enumeration, exact transport, shell, battery, and wake parsing reused by Android and Quest | Device-profile lifecycle, protected operations, semantics, and safety policy |

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
   platform/testbed source: the external repository before its consolidation
   cutover and its platform directory here afterward.
2. Put reusable resident semantic behavior and provider adapters here; keep a
   target-specific native runner in its authoritative platform/testbed source
   when it is not a reusable machine-control component.
3. Put cross-provider capability vocabulary and conformance expectations here
   beside the implementation they govern.
4. Put worker creation, peer authorization, observation, and supervision in
   YepAnywhere coordination.
5. Put exact-target usage arbitration in Machine Control; let any coordinator
   consume that generic claim surface.
6. Put product-specific assertions in the consuming application repository.

Do not add the same operation independently to all five layers. Choose one
owner and expose it through adapters.

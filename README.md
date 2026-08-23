# Machine Control

**Target-native automation for computers and devices.**

Machine Control gives software agents one target-oriented interface for
operating Windows, macOS, Linux, ChromeOS, iOS, Android, and other devices. It
combines system administration, semantic UI automation, screen capture, input,
application control, lifecycle, and recovery without reducing every platform
to screenshots and coordinates.

The important distinction is where control happens. A Windows VM is driven
through Windows services and UI Automation inside the guest. A Mac uses
Accessibility and native application APIs. A Chromebook exposes its own
desktop accessibility tree. An iPhone uses CoreDevice and XCTest from an
authorized device host. Hypervisor windows and external keyboard/video routes
remain available for bootstrap and recovery, not ordinary application testing.

```bash
mc=bin/machine-control

$mc targets
$mc --target windows target doctor
$mc --target windows desktop applications
$mc --target macos desktop snapshot \
  --target org.example.Application --query Save
$mc --target ios ios application launch Settings --relaunch
```

Machine Control is an active, pre-1.0 project. Windows, macOS, and Linux
already share an exercised desktop contract; ChromeOS and several physical
device families have working native implementations with different levels of
common-facade coverage.

## Why Machine Control?

Most UI automation tools solve one layer or one platform. Remote-desktop tools
usually expose pixels and input. Accessibility tools expose semantics but not
lifecycle, administration, protected desktops, or recovery. Device tools such
as ADB and XCTest are powerful but have unrelated interfaces.

Machine Control puts those capabilities behind one honest target model:

- **Rich native control:** use UIA, AX, AT-SPI, Chrome accessibility, XCTest,
  ADB, and platform services instead of choosing pixels as the universal
  denominator.
- **The same experience locally and remotely:** an agent can run on the target
  or reach the target-native controller through an authenticated transport.
- **No routine host interference:** normal VM testing does not focus a
  hypervisor window, steal the host pointer, or type through the controller's
  desktop.
- **Truthful results:** request acceptance, action delivery, observed effect,
  evidence, and uncertainty remain separate.
- **Recovery without architectural confusion:** outer VM, device-host, and KVM
  routes are explicit when the native route is unavailable.

## North Star

The North Star is simple: an authorized agent should be able to select any
supported computer or device and use the richest practical controls native to
that target, regardless of where the agent itself is running.

```text
control(target=self, ...)
control(target=windows, ...)
control(target=macos, ...)
control(target=chromeos, ...)
control(target=ios, ...)
control(target=android, ...)
```

Changing the target may change transport, latency, available capabilities, or
the evidence an operation can produce. It should not require inventing a new
workflow for every operating system.

This direction has a few durable consequences:

1. **Target-native first.** Administration, semantics, capture, input, and
   application control execute in the target OS whenever the platform permits.
2. **Outside control is first-class.** An authorized outside agent can drive a
   resident controller directly. Spawning another agent inside the target is
   optional and useful for local development context, not a prerequisite.
3. **Devices use their strongest native model.** Stock iOS uses an XCTest
   runner and CoreDevice on an authorized Mac; Android begins with ADB and
   UIAutomator/accessibility. They are not forced into a misleading desktop
   service design.
4. **Outer control is explicit.** Hypervisor consoles, host input, hardware
   KVM, and similar routes are for installation, bootstrap, independent
   diagnosis, and recovery.
5. **The contract belongs to this project.** Cua and platform-specific
   providers are replaceable implementations behind an owned facade and
   conformance corpus.
6. **Capabilities and outcomes are reported honestly.** A successful API call
   is not proof that an application changed state.

Windows is the first complete implementation vertical slice. That is the
project's sequencing strategy, not a limit on its platform scope. ChromeOS is
the current architectural reference for rich remote access to control that
still executes entirely on the target.

## What works today

The project deliberately shares an experience rather than pretending every
platform has the same implementation.

| Platform | Current control surface | Maturity |
| --- | --- | --- |
| Windows | Common desktop facade, administration, UIA/Cua semantics, capture/input, application and session control, UAC/lock/login, lifecycle, workspaces, and appliance maintenance | First complete vertical slice; live ARM64 VM and physical x64 evidence |
| macOS | Common desktop facade using Accessibility, Workspace, Quartz/CoreGraphics, and selected Cua routes; application UI, system surfaces, administrator sheets, capture/input, lifecycle, workspaces, and maintenance | Accepted logged-in Aqua/Tart appliance; lock, preboot, and physical-Mac profiles remain |
| Linux | Common desktop facade using AT-SPI, GNOME capture, target-local input, application lifecycle, workspaces, and maintenance | Accepted Ubuntu 24.04 GNOME 46 Wayland appliance; GDM, lock, other compositors, and physical hardware remain |
| ChromeOS | Target-native administration, desktop accessibility, per-page CDP, capture/input, readiness, and guarded runtime maintenance | Working physical reference implementation; broader common desktop projection remains |
| iOS | CoreDevice lifecycle and deployment plus semantic XCTest snapshots/actions, screenshots, input, leases, and recovery | Working physical-device route with explicit protected-authentication limits |
| Android | Guarded ADB discovery, administration, deployment, lifecycle, capture, input, logs, and shared transport primitives | Implemented handheld foundation; richer semantic/profile coverage remains |
| Quest | Exact-device ADB selection, lifecycle, deployment, wake/proximity policy, leases, and recovery | Working device-specific route sharing the Android transport foundation |
| Steam Deck | Direct SteamOS/Devkit administration and session-aware native operations | Working native platform interface; common facade coverage remains |

“Accepted” here means exercised against this repository's conformance and
real-application workflows. It is not a claim of universal hardware coverage
or a production support SLA. Platform-specific status, limitations, and setup
live under [`platforms/`](platforms/README.md).

## Controller-host support

The **target platform** is the OS being controlled. The **controller host** is
the machine that executes the selected adapter and is physically or logically
attached to its hypervisor or device. These are independent: coordinator code
running on Linux is not by itself a Linux-hosted route to a Windows VM.

The common coordinator and its fixture-backed checks run on macOS, Linux, and
Windows. Live desktop-VM hosting is narrower today:

| Controller host | Coordinator evidence | Live-tested desktop VM routes | Planned desktop VM routes |
| --- | --- | --- | --- |
| macOS | Portable and native checks; current live controller | UTM/QEMU for Windows and Linux; Tart for macOS | Current baseline |
| Linux | Hosted CI plus execution inside the retained Linux appliance | None | libvirt with QEMU/KVM for Windows and Linux guests |
| Windows | Hosted CI plus execution inside the retained Windows appliance | None | Hyper-V on eligible Windows editions for Windows and Linux guests; evaluate QEMU/WHPX only for measured gaps |

The Linux and Windows rows therefore claim coordinator portability, not a
live-tested local hypervisor adapter. Each planned provider must independently
prove exact target identity, guarded lifecycle, administration, workspace
isolation and cleanup, resident desktop conformance, explicit recovery, and
host non-interference before being documented as supported.

macOS guests remain on Apple hardware. A Linux or Windows caller will reach a
physical Mac, its target-resident controller, or an Apple-hosted Tart provider
through an authenticated remote route; the plan does not emulate macOS under
KVM or Hyper-V. Device routes have their own controller-host constraints—iOS,
for example, requires an authorized Mac—so `machine-control targets` reports
eligibility for the concrete selected route rather than inferring it from the
target OS.

The provider direction and adoption gates are maintained in
[`vm-workspaces-and-storage-policy.md`](topics/vm-workspaces-and-storage-policy.md),
while coordinator-versus-route portability is maintained in
[`cross-platform-coordinator.md`](topics/cross-platform-coordinator.md).

## Capabilities

Depending on the target, Machine Control can provide:

- target discovery, readiness diagnostics, and lifecycle;
- shell, files, processes, packages, services, logs, and deployment;
- application and window inventory, launch, activation, and termination;
- compact semantic snapshots and generation-scoped element actions;
- target-local display or exact-window capture;
- target-local keyboard, pointer, clipboard, and window management;
- truthful login, lock, interactive-session, integrity, and desktop state;
- explicitly authorized protected operations on dedicated test appliances;
- persistent, isolated, and retained-candidate VM workspaces;
- bounded maintenance, reboot proof, candidate validation, and image
  certification; and
- route, delivery, effect, evidence, host-interference, and uncertainty
  reporting.

Capabilities are discovered, not assumed. Unsupported or unsafe operations
return typed refusals rather than silently switching to a weaker or more
disruptive route.

## How it works

```text
agent on the target -------------------- local IPC ----+
                                                       |
agent somewhere else -------- authenticated transport +--->
                                                       |    target adapter
                                                       |      |
                                                       |      +-- desktop resident
                                                       |      |     semantics
                                                       |      |     capture/input
                                                       |      |     apps/sessions
                                                       |      |
authorized device host -------- CoreDevice / ADB ------+      +-- device-native runner

explicit recovery request -------------------------------> outer VM / KVM route
```

[`bin/machine-control`](bin/machine-control) is the common local entry point.
It selects a logical target and delegates to the authoritative platform
adapter. Desktop adapters then reach the target-resident facade; device
adapters use the strongest native runner available to that device class.

The common interface normalizes target selection, capability discovery,
requests, results, and evidence. It does not erase meaningful platform
differences. Windows UIA, macOS Accessibility, Linux AT-SPI, Chrome
accessibility, XCTest, and ADB keep their real authority and failure modes.

Agent coordination is a separate layer. YepAnywhere is the current surrounding
coordination plane for agent sessions and cross-host delegation, but it does
not own machine lifecycle or the machine-control contract. See the
[system map](SYSTEM-MAP.md) for ownership boundaries.

## Quick start

The common client requires Python 3.10 or later and uses only the standard
library.

```bash
git clone https://github.com/kzahel/machine-control.git
cd machine-control

bin/machine-control targets
python3 bin/check --portable
```

On Windows, use `py -3 bin/machine-control targets` and
`py -3 bin/check --portable`. Portable checks do not contact a VM or physical
device.

To connect a real target:

1. Choose its guide from the [platform index](platforms/README.md).
2. Install that platform's prerequisites and target-resident components.
3. Put concrete selectors, endpoints, paths, and policy in ignored local
   configuration or an optional private inventory provider.
4. Run the read-only doctor before requesting a mutation.

On a configured controller:

```bash
bin/machine-control inventory status
bin/machine-control --target windows target doctor
bin/machine-control --target windows target ensure-ready
```

`doctor` is read-only. `ensure-ready` is the explicit mutating composition: it
records the initial doctor result, performs only an adapter-declared ordinary
start when appropriate, and observes readiness again. It does not guess a
repair for a running unhealthy target.

Local target registries use the
[`machine-control-targets/v0`](contracts/targets-v0.schema.json) schema. Logical
target names are selectors, not credentials or bearer authority.

## Common workflows

### Inspect and control a desktop

```bash
mc=bin/machine-control

$mc --target windows desktop status
$mc --target windows desktop capabilities
$mc --target windows desktop applications
$mc --target windows desktop windows
$mc --target windows desktop snapshot \
  --target org.example.Application --query Save
$mc --target windows desktop capture \
  --scope window --target active_window
```

A semantic snapshot returns ephemeral, generation-scoped element references.
Use those references for actions and rediscover them after navigation, process
restart, or window recreation.

### Use a physical iOS target

```bash
$mc --target ios target doctor
$mc --target ios ios runner prepare
$mc --target ios ios application launch Settings --relaunch
$mc --target ios ios snapshot --interactive
```

iOS has a device-shaped operation family rather than pretending to be a
desktop. Android, Quest, ChromeOS, and Steam Deck likewise retain explicit
native operations where a common projection would hide important semantics.

### Request a VM workspace

```bash
$mc --target macos workspace acquire --intent isolated
$mc --target macos --workspace w-EXAMPLE123 desktop status
$mc --target macos workspace release w-EXAMPLE123
```

Callers request intent—`persistent`, `isolated`, or `candidate`—while the
platform adapter chooses the safe provider mechanism. Workspace handles are
opaque selectors backed by private exact-identity receipts.

### Reach a platform-specific operation

```bash
$mc --target windows testbed -- help
$mc --target chromeos maintenance capabilities
$mc --target chromeos maintenance audit --profile runtime
```

`testbed --` keeps platform lifecycle, bootstrap, recovery, and specialized
operations available without flattening them into a misleading universal
interface. `os --` provides an explicit guest-administration escape on
supported desktops.

## Safety model

Machine Control is designed for powerful automation without obscuring where
that power comes from.

- **Read-only diagnostics stay read-only.** Doctor does not boot, log in,
  deploy, repair, grant consent, or fall back to host input.
- **Mutations require exact targets.** Platform adapters bind state-changing
  operations to private provider identities, target roles, and fresh
  observations.
- **No silent route escalation.** An inner operation may recommend recovery,
  but it does not silently focus a VM window or invoke a more privileged route.
- **Delivery is not effect.** Results distinguish request acceptance, action
  delivery, independently observed effects, evidence, and uncertainty.
- **Secrets do not belong in ordinary requests.** Credential operations use
  dedicated one-shot transports and refuse before reading a secret when field
  discovery is uncertain.
- **Deployment posture is explicit.** A disposable test appliance may
  authorize stronger protected control than a personal or shared workstation.

The current Windows `dedicated-test-appliance` profile is intentionally
powerful. Read [SECURITY.md](SECURITY.md) before installing or arming protected
operations. The deeper routing and authorization policy is in
[inner-first routing](topics/inner-first-routing.md).

## Project structure

| Path | Purpose |
| --- | --- |
| [`bin/machine-control`](bin/machine-control) | Common target-selecting CLI |
| [`client/`](client/) | Portable coordinator and request translation |
| [`contracts/`](contracts/README.md) | Exercised request, result, doctor, workspace, and maintenance schemas |
| [`platforms/`](platforms/README.md) | Canonical platform lifecycle, native control, recovery, fixtures, and operating guides |
| [`src/`](src/) | Reusable resident runtime code; currently the Windows service/session implementation |
| [`providers/`](providers/) | Shared provider components such as workspace and ADB foundations |
| [`tests/`](tests/) | Cross-platform client and resident conformance |
| [`topics/`](topics/README.md) | Living architectural decisions and current direction |
| [`research/`](research/README.md) | Provider dossiers and platform comparisons with evidence levels |
| [`docs/tactical/`](docs/tactical/README.md) | Bounded implementation plans and completed execution records |

Concrete machine inventory, credentials, private routes, and deployment state
do not belong in this public repository.

## Documentation

Start with the document that matches your question:

- **How do I operate a target?** Use the
  [platform implementation index](platforms/README.md) and the selected
  platform's README or agent guide.
- **What does the common interface guarantee?** Read the
  [contract projections](contracts/README.md),
  [unified desktop client](topics/unified-desktop-client.md), and
  [capabilities and results](topics/capabilities-and-results.md).
- **Why is the system shaped this way?** Read
  [architecture](topics/architecture.md),
  [inner-first routing](topics/inner-first-routing.md), and the
  [glossary](GLOSSARY.md).
- **What owns each part?** Read the [system map](SYSTEM-MAP.md).
- **What has been evaluated?** Enter through the
  [research corpus](research/README.md).
- **What is the current decision or next direction?** Use the
  [topic index](topics/README.md).
- **How was a completed slice executed?** Use the
  [tactical index](docs/tactical/README.md).

The documentation deliberately separates durable architecture, evidence,
current decisions, and execution history. This README owns the product promise
and repository-level synthesis; linked documents own implementation detail.

## Development and validation

Run the dependency-light checks from one entry point:

```bash
python3 bin/check --portable
python3 bin/check --native
```

Portable checks run on macOS, Linux, and Windows without contacting configured
targets. Native checks select the applicable platform build and static
validation. The common client tests and guarded live desktop workflow are
documented under [`tests/client`](tests/client/README.md); each platform guide
names its deeper conformance suites.

Research changes should preserve the repository's evidence levels. Continuing
architectural concerns belong in a topic; bounded implementation programs
belong in a tactical. See the [topic index](topics/README.md) and
[research guide](research/README.md) before extending those corpora.

## Scope and non-goals

Machine Control is not trying to:

- flatten platform-specific semantics into one lowest-common-denominator
  implementation;
- replace mature native facilities such as UIA, Accessibility, AT-SPI, XCTest,
  CoreDevice, ADB, or Chrome accessibility;
- make screenshot-and-coordinate control the default;
- give ordinary workers generic access to hypervisors, hardware KVM, or
  privileged system shells;
- require an agent process inside every target;
- treat secrets, biometrics, or protected authorization as ordinary JSON; or
- claim that one successful provider call proves an application effect.

The common schemas are currently `v0` and intentionally evolving. The project
owns a stable ergonomic direction without prematurely freezing one universal
wire protocol.

## License

Machine Control is available under the [MIT License](LICENSE).

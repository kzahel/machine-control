# Machine Control

Status: current architecture notebook, started 2026-08-04.

## North Star

**Decision:** Give every supported computer and device the richest practical
target-native control system. macOS, Windows, Linux, and ChromeOS virtual or
physical machines should be able to control their own running OS from inside
that OS, and an authorized agent elsewhere should be able to reach that same
resident controller through an authenticated transport.

Mobile devices, headsets, and platforms that cannot host a general agent are
equally in scope. They should use the strongest platform-native runner and
device-host tooling available while presenting the same target-oriented
ergonomics. The goal is common agent experience, not identical process
placement on operating systems that impose different boundaries.

The agent-facing experience should feel the same in both cases:

```text
control(target=self, ...)
control(target=winvm, ...)
control(target=physical-windows, ...)
control(target=chromeos, ...)
control(target=ios, ...)
control(target=android, ...)
```

Changing the target may change transport, latency, capabilities, and evidence.
It should not require a different desktop vocabulary or a different skill for
driving applications.

```text
agent on the target -------------------- local IPC ----+
                                                       |
agent on another authorized machine --- tunnel/SSH ---+-->
                                                           target-resident control
                                                             - files/processes/admin
                                                             - semantic UI
                                                             - screen capture
                                                             - keyboard/pointer
                                                             - app/window/session state
                                                             - protected operations when armed

agent on an authorized device host ---- CoreDevice/ADB ---> mobile/device target
                                                             - native runner/semantics
                                                             - capture/input
                                                             - lifecycle/logs
```

For machines capable of hosting the full stack, this is an **inside-out control
model**. Remote access to a resident provider is still an inner route. It does
not mean focusing a VM window or routing the controller user's keyboard and
pointer through UTM, Tart, a hypervisor console, or a hardware KVM.

For stock iOS and similar constrained devices, the worker may run on an
authorized Mac while a signed native runner executes on the device. Android's
ADB, shell, screenshots, input, logs, and UIAutomator/accessibility routes are
the established foundation rather than functionality this project should
reimplement. These device-hosted placements are ordinary native routes for
their device class, not evidence that the device is outside the North Star.

Outer VM/KVM control remains necessary before the target can control itself:
unattended OS installation, initial bootstrap, independent diagnosis, and
recovery after the resident stack is unreachable. Once the resident controller
is healthy, ordinary development and testing must not require the VM window to
be visible or foregrounded on the host.

The target-native system should cover, as far as the platform permits:

- shell, files, processes, packages, services, logs, and deployment;
- compact semantic snapshots and stable, efficient element actions;
- complete target- or device-local screen or window capture;
- target- or device-local keyboard, pointer, clipboard, and window management;
- truthful login, lock, interactive-session, integrity, and desktop state; and
- an explicitly authorized resident service or protected broker for operations
  that cannot run in an ordinary user process.

Full control does not imply one unsafe deployment posture. A disposable test
appliance may deliberately arm a stronger resident controller because isolation
and rebuildability are part of its boundary. A personal or shared workstation
should keep protected operations behind visible, bounded, revocable authority
outside the ordinary agent process. Both profiles must expose the same honest
capability vocabulary; neither may silently widen itself from agent-controlled
arguments or environment.

Preboot firmware, disk-unlock screens, unavailable operating systems, and
physically broken machines may still require an outer provider or a human.
Those exceptions do not make outer control the normal desktop route.

The project should own the stable ergonomic contract. Cua, WinApp/UIA,
Accessibility, AT-SPI, Chrome accessibility/CDP, XCTest, CoreDevice, ADB,
UIAutomator, ChatGPT Computer Use, and similar systems can implement or
supplement it. Proprietary, agent-coupled providers may be excellent primary
routes or quality benchmarks, but the usable control surface must not exist
only inside one proprietary agent product.

### ChromeOS is the current reference implementation

**Current:** The physical ChromeOS testbed is the closest working example of
the desired desktop architecture. The agent normally runs on another machine,
but SSH is only the authenticated transport. Observation and action execute
inside the Chromebook:

```text
outside agent
  |
  +-- SSH administration -------------> ChromeOS files/processes/system
  +-- JSON commands over SSH ----------> target-local Python control client
  |                                        - DRM/EGL screen capture
  |                                        - evdev keyboard/touch input
  |                                        - experimental uinput mouse
  +-- built-in accessibility via CDP --> chrome.automation desktop tree/actions
  +-- per-target CDP ------------------> browser page semantics/actions
  +-- Chromebook-local ADB proxy ------> ARCVM Android target
```

This is not host-side pixel control. The outside agent gets rich, efficient
control while the actual semantics, capture, and input mechanisms remain
target-native. It demonstrates the North Star property that agent placement
and control implementation placement are independent.

`chrome.automation` is the quality reference for the desktop semantic plane:
it exposes windows, shelf, tray, dialogs, controls, state, actions, and bounds
through one coherent accessibility tree. Web pages additionally benefit from
ARIA and ordinary CDP accessibility, but the system-wide result is not merely
because every ChromeOS surface is a web page. ChromeOS's built-in accessibility
extension also projects native system UI into the automation tree.

The corresponding native semantic facilities on the other desktop platforms
are:

| Platform | Native semantic foundation |
| --- | --- |
| ChromeOS | `chrome.automation` plus per-page CDP |
| macOS | Accessibility/`AXUIElement` |
| Windows | UI Automation, currently through WinApp and evaluated Cua routes |
| Linux | AT-SPI in the active desktop session |

The common desktop facade should make the latter three feel as compact,
discoverable, and action-oriented as the current ChromeOS experience while
reporting real platform omissions rather than pretending the underlying APIs
are identical.

ChromeOS resilience limitations—developer-mode bootstrap, update-sensitive
SSH/devtools configuration, and lack of an independent physical recovery
path—remain real. They do not diminish its value as the reference for ordinary
control, which is already effective in practice.

### Outside control first; in-target agents when useful

An authorized outside agent must be able to select a machine and use its full
ordinary target-native control surface directly. Spawning an agent inside the
target must not be required merely to inspect or drive its UI.

An in-target YA worker remains valuable when the task benefits from local
filesystem, build, process, application, permission, or debugging context. It
can also unlock agent-coupled capabilities that exist only inside that target,
such as ChatGPT Computer Use installed in a Windows or macOS guest. In-target
placement is therefore an optimization and an additional capability, not a
replacement for the remotely reachable resident interface.

```text
outside session --target winvm ----> Windows-resident control
       |
       +-- optionally spawn YA worker inside Windows
              - build/debug with local context
              - use Computer Use when advantageous
              - call the same resident control locally
```

### Other existing device foundations

The Windows-first implementation focus must preserve and build on working
device routes already in the system:

- **iOS is already a first-class physical-device target.** Dotfiles discovers
  the configured phone and routes agents to the authoritative iOS testbed,
  which uses CoreDevice and a semantic XCTest runner for lifecycle,
  observation, actions, leases, and recovery.
- **Android begins with ADB.** Reuse its installation, shell, lifecycle,
  screenshot, input, logging, and UIAutomator/accessibility facilities. Add an
  adapter and consistent ergonomics only where needed; do not replace ADB.
- **Quest, Steam Deck, and future physical targets remain in scope.** Their
  authoritative testbeds should expose native capabilities honestly while
  sharing the same target-selection experience where possible.

The four desktop operating systems should converge on a common semantic,
visual, input, and administration experience. iOS and Android are conceptually
different device-control families, but they still belong to the same inventory,
authorization, target-selection, capability, evidence, and result model.

### Windows-first milestone

Prove the North Star completely on Windows before spreading implementation
effort across every platform:

1. Start from a clean, reproducible Windows installation.
2. Bootstrap administration, the interactive-session controller, and the YA
   worker with minimal routine console interaction.
3. Exercise the same desktop-control contract from a worker inside Windows and
   from an authorized agent outside it.
4. Cover semantics, guest-local capture/input, session transitions, elevated
   applications, and explicitly authorized secure-desktop behavior.
5. Verify that ordinary work never focuses the VM window or moves/types through
   the host desktop.
6. Let the controller and guest worker provision, validate, shut down, and seal
   or snapshot the finished test image so golden images are reproducible
   outputs rather than manually maintained prerequisites.

macOS, Linux, ChromeOS, iOS, Android, and other physical targets should all
provide the same target-selection ergonomics and honest capability reporting.
The Windows vertical slice is the immediate proving ground, not the boundary
of the project.

This directory explains how agents should develop and test applications across
physical machines, virtual machines, and attached devices without pretending
that every target has the same control technology. It exists because the code
is deliberately split among YepAnywhere, the testbed inventory, standalone
testbed repositories, guest helpers, device runners, and external recovery
providers.

It is documentation only. The implementations remain in their owning
repositories.

## Current position

The system has one intended ergonomic shape, not one universal platform
implementation:

1. **Target-native control is the normal machine-control surface.** A resident
   desktop controller, ChromeOS-native stack, XCTest runner, ADB route, or
   equivalent provider exposes the strongest honest capabilities of its target.
2. **Local and remote callers use the same conceptual surface.** A local worker
   can use direct IPC; an outside agent can use an authenticated tunnel or
   authorized device host. The target selector changes, not the conceptual
   control workflow.
3. **YepAnywhere is the coordination plane.** A controller session discovers
   authorized YA peers, creates native worker sessions on them, supervises
   progress, and receives results.
4. **Run a worker inside the target when useful, not as a prerequisite.** An
   outside agent retains rich ordinary control. An in-target worker adds the
   best filesystem, process, application, permission, debugging, and
   agent-coupled-tool context.
5. **Keep outer VM/KVM control independent.** Hypervisor and hardware-KVM
   routes own startup, bootstrap, independent observation, and recovery when a
   machine's resident route is unavailable. Device-host routes such as
   CoreDevice/XCTest and ADB may be ordinary target-native control for devices
   that cannot host the complete resident stack.
6. **Do not expose outer input as a routine fallback.** VM-host input can steal
   focus, move the pointer, type into the wrong window, and interrupt the
   controller user's work. A worker should request recovery rather than invoke
   that route directly.
7. **Normalize results, not platform behavior.** macOS AX, Windows UIA, Linux
   AT-SPI, Chrome accessibility, XCTest, ADB, and raw KVM pixels/HID have
   different authority and failure modes. A common contract must say which
   route actually ran and what it could verify.

```text
controller YA session
  |
  +-- YA delegation ----------> worker YA session on target/guest
  |                                |
  |                                +-- target-resident control
  |
  +-- authenticated tunnel ---> target-resident control on another SUT
  |
  +-- device-host provider ---> iOS / Android / headset native runner
  |
  +-- authoritative testbed ---> outer lifecycle/recovery provider
                                   - boot/resume/repair
                                   - framebuffer or screenshot
                                   - HID/input only when recovery requires it
```

For an iPhone or another device that cannot host a general agent, the worker
runs on an authorized controller machine and the device is a distinct control
target. Agent placement and control-target selection are separate decisions;
this placement difference must not create an unrelated agent-facing workflow.

## Reading order

- **North Star above:** the product direction that governs the remaining
  architecture and platform work.
- [Glossary](GLOSSARY.md): the identities, planes, routes, states, and evidence
  terms used throughout the project.
- [System map](SYSTEM-MAP.md): which existing repository or program owns each
  concern.
- [Architecture](topics/architecture.md): the component model and trust/failure
  boundaries.
- [Inner-first routing](topics/inner-first-routing.md): the policy that keeps
  ordinary VM testing from interfering with the controller host.
- [Delegation and agent placement](topics/delegation-and-agent-placement.md):
  how YepAnywhere workers and testbed targets relate.
- [Capabilities and results](topics/capabilities-and-results.md): a provisional
  vocabulary for truthful discovery and action outcomes.
- [Platform notes](topics/platform-notes.md): current routes and gaps per
  operating system and device family.
- [Open questions](topics/open-questions.md): unresolved decisions and the
  recommended first integration slice.

## Consolidation of earlier work

The original Cua-oriented brief has been consolidated into this repository and
removed. This is the sole current architecture source of truth; exact
experimental evidence remains in the spike repository rather than in a second
documentation tree.

The durable lessons retained here are deliberately narrower than that original
plan:

- own a transport- and facade-independent control contract rather than tying
  the architecture to MCP, SSH, Cua, Computer Use, or one agent product;
- use a stable target service plus an interactive-session companion and only a
  narrow protected broker where the platform requires one;
- distinguish dedicated test appliances from personal/shared machines, and do
  not mistake same-user tool policy for containment from a shell-capable agent;
- bind semantic references and protected authority to target/session
  generations, with expiry, cancellation, revocation, and structured refusal;
- pair semantic and visual observations by explicit epochs and keep action
  delivery separate from independently observed effect; and
- test providers with deterministic fixtures, event-aware waits, honest
  omissions, and independent oracles.

What was intentionally not carried forward is equally important: Cua is not
the universal core; spawning a YA worker inside a desktop is not required for
outside control; MCP is not the authorization boundary; and outer VM/KVM input
is not a routine fallback.

[`../machine-control-spike/`](../machine-control-spike/README.md) contains the
executable Cua evaluation and exact evidence. Its macOS and Windows findings
show that Cua contains useful contract ideas and may remain an optional
user-session provider, but it should not be the trust, lifecycle, recovery, or
cross-platform foundation of this system.

ChatGPT Computer Use is likewise a valuable installed provider and ergonomic
benchmark on supported systems. Because its protocol and availability are tied
to a proprietary agent product, it cannot be the only expression of the
target-native contract.

This directory is the current synthesis. It should link to detailed evidence
in the spike and to behavior owned by the testbeds instead of becoming another
implementation repository.

## Non-goals

- Replacing the standalone testbed CLIs.
- Moving target-specific lifecycle or recovery into YepAnywhere.
- Merging controller and worker transcripts into one provider session.
- Making screenshot-and-coordinate control the least common denominator.
- Giving a guest worker generic access to its hypervisor or physical KVM.
- Requiring an in-target agent session before an authorized outside caller can
  use the resident controller.
- Treating login, credentials, biometrics, or protected authorization as
  ordinary agent actions.
- Freezing a cross-platform wire protocol before the Windows local-and-remote
  vertical slice has survived real use.

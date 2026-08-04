# Machine Control Documentation Guide

This directory is the current documentation hub for cross-platform machine
control. It contains architecture and vocabulary, not a machine-control
implementation.

## North Star (highest priority)

The project's North Star is powerful **target-native control** across desktop,
mobile, headset, and other device classes. macOS, Windows, Linux, and ChromeOS
virtual or physical targets should be able to control their own running OS
from inside that OS: administration, semantic UI, screen capture, keyboard and
pointer input, application/session management, and an explicitly authorized
path for protected desktop operations.

For a platform such as stock iOS that cannot host a general agent or complete
resident service, use the richest platform-native runner on the device and an
authorized controller-host provider. XCTest/CoreDevice on iOS and ADB plus
UIAutomator/accessibility on Android are first-class implementations of the
same target-selection and control experience, not afterthoughts. Do not build
a replacement for a mature platform facility merely to make every provider's
process placement identical.

The same agent-facing control experience must work from either placement:

- an agent on the target calls the resident controller locally; and
- an agent elsewhere reaches that same resident controller through an
  authenticated tunnel or transport; or, for a constrained attached device,
  reaches its native runner through the authoritative device-host provider.

Local versus remote use should differ mainly by target selection and command
transport. It should not require a different UI vocabulary, different skills,
or host-side manipulation of a VM window. Remote use of a target-resident
provider is still an inner route; it is not outer VM/KVM control.

Hypervisor consoles, host input, hardware KVM, and similar outer routes exist
for unattended installation, initial bootstrap, independent diagnosis, and
recovery. They are not the ordinary application-testing path. After the
resident controller is healthy, a VM window should not need to be visible,
focused, or manipulated on the controller user's desktop.

The project should own a stable ergonomic contract even when implementations
use Cua, WinApp/UIA, AX, AT-SPI, Computer Use, Chrome accessibility/CDP,
XCTest, ADB/UIAutomator, or another provider.
Proprietary agent-coupled tools may be excellent optional routes and quality
benchmarks, but they are not the only foundation for the target-native
interface.

Treat the existing ChromeOS testbed as the closest current reference for the
desired desktop architecture. An agent outside the Chromebook reaches it over
SSH, while administration, `chrome.automation` desktop semantics, per-page
CDP, DRM/EGL capture, and evdev/uinput actions all execute on the target. This
is remote ergonomic access to target-native control, not external pixel/HID
control. Preserve that shape when designing the common facade and the Windows,
macOS, and Linux implementations.

An outside agent must remain capable of rich ordinary control without first
spawning another agent on the target. In-target YA workers are an optional
placement for work that benefits from local filesystem/build/debug context or
from agent-coupled capabilities such as Computer Use. Treat placement as an
optimization or additional capability, not as a prerequisite for driving the
machine.

Focus the first complete vertical slice on Windows: build a clean, reproducible
Windows test appliance; bring its resident control stack up without routine
manual console work; exercise the same interface locally and remotely; and let
an agent provision, validate, shut down, and seal or snapshot the resulting
image. Do not spread implementation effort across all platforms until that
slice proves the contract. Cross-platform design work should directly support
or be validated by this slice. Windows-first is sequencing, not a narrowing of
the destination: preserve and reuse the already strong ChromeOS and iOS
testbeds, treat ChromeOS as its own platform rather than generic Linux, and use
Android's established ADB foundation instead of starting over.

Treat this North Star as the highest-priority decision when other documents,
older spikes, or implementation conveniences pull in a different direction.

Start with the North Star in `README.md`, then read `GLOSSARY.md` and
`topics/inner-first-routing.md`. Read `SYSTEM-MAP.md` before changing ownership
boundaries among YepAnywhere, dotfiles, a testbed, a guest-resident provider,
or an outer provider.

Preserve these rules:

- YepAnywhere owns agent-session coordination and cross-host delegation.
- Dotfiles owns testbed discovery and availability declarations only.
- Each `*-testbed` repository remains authoritative for its target's lifecycle,
  transport, bootstrap, recovery, and safe operating policy.
- Agent placement and control-target selection are independent. An authorized
  outside agent must have the full ordinary resident or device-native control
  surface. Spawn a worker on the target when substantial local development or
  an in-target-only capability makes that placement useful.
- Guest-local administration and semantic desktop control are the normal
  routes. Guest-local capture and input are the ordinary fallbacks.
  Host/hypervisor/KVM input is for initial bootstrap and recovery.
- A worker agent must not silently fall back to an outer route. If an outer
  route could interrupt the controller user's desktop, it should normally be
  absent from the worker's tools and require an explicit recovery request.
- Dedicated test appliances may explicitly authorize a stronger resident
  service or protected broker than a personal workstation. Describe that
  privilege honestly; do not weaken the target-resident goal merely because a
  normal user process cannot cross a session, integrity, or secure-desktop
  boundary.
- ChromeOS, iOS, Android, Quest, and other physical devices are in scope for the
  North Star. Preserve their existing authoritative testbeds and native routes;
  do not make desktop VM architecture a prerequisite for device support.
- Unify the desktop experience across macOS, Windows, Linux, and ChromeOS as far
  as capabilities permit. Give mobile/device providers the same inventory,
  authorization, target selection, capability, and result vocabulary without
  forcing iOS and Android into a misleading desktop-control abstraction.
- A successful input API call is not proof of an application effect. Keep
  delivery, observed effect, and uncertainty separate.
- Capability descriptions must report real route, fidelity, omissions,
  privilege, session requirements, and host-interference risk.
- Do not collapse a YA peer, an agent execution host, a system under test, a
  testbed provider, or a delegation handle into one identity.

Label claims as one of:

- **Current**: observed in the checked-in testbeds or research spike.
- **Decision**: the present architectural direction.
- **Proposal**: a candidate contract or implementation approach.
- **Open**: a question that still needs evidence or a product decision.

When a decision changes, update the affected topic and `README.md`. When a new
program or repository enters the system, update `SYSTEM-MAP.md`. Keep exact
experiment evidence and third-party source pins in `machine-control-spike`;
link to those findings rather than copying detailed audit logs here.

Never store credentials, private machine configuration, VM/device identifiers,
personal captures, signed approval material, or generated support bundles in
this directory.

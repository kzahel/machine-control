# Platform Notes

Topic: `platform-notes`

Status: living cross-platform capability and gap survey.

These notes summarize the present direction. Exact validation evidence belongs
in the relevant testbed and `machine-control-spike`.

## Windows desktop

Preferred control is a Windows-resident service reachable through the same
facade from an outside agent or a local YA worker. The interactive-session
companion owns ordinary desktop operations; the worker is optional.

- Administration: PowerShell/SSH or another guest administration channel.
- Semantics: UI Automation through the existing WinApp relay.
- Guest-local visual/input fallback: a user-session provider where it does not
  cross integrity or secure-desktop boundaries silently.
- Optional supplements: Computer Use or Cua when either improves a task, without
  making it the only remotely usable surface.
- Outer recovery: UTM/QEMU console capture and input on the Mac controller.
- Protected future: a narrow session proxy and optionally a SYSTEM broker for
  truthful input-desktop state, companion bootstrap, and explicitly armed
  secure-desktop operations.

The Cua spike proved useful normal-user behavior but also found cross-integrity
IPC, lock-state, UIAccess, secure-desktop, signing, and provenance gaps. Cua is
therefore a reference or optional provider, not the system foundation. See
[`windows-findings.md`](../../machine-control-spike/docs/windows-findings.md).

## macOS desktop

Preferred control is a stable, consented, target-resident helper reachable
locally or remotely. A YA worker may run inside the physical Mac or VM when the
task benefits from local project context.

- Administration: local shell or `tart exec` for the VM.
- Semantics: Accessibility (`AXUIElement`) through a stable, consented helper.
- Capture/input: guest-local APIs when authorized.
- Outer recovery for VM: Tart screenshot and input.
- Protected boundary: login window, FileVault/preboot, TCC consent, and
  passwords are not ordinary AX actions.

Outer Tart input must not be available to an ordinary worker because it can
foreground the Tart window and move the controller pointer.

## Linux desktop

Preferred control is a target-resident service connected to the active desktop
session and reachable locally or remotely. A YA worker in that session is
optional.

- Administration: QEMU guest agent, SSH, or local shell.
- Semantics: AT-SPI under the correct user D-Bus session.
- GUI launch: through the active user's environment/systemd manager.
- Wayland input/capture: compositor/portal-specific and honestly reported.
- Outer recovery: UTM framebuffer and virtual HID.

GDM, lock screens, and a missing user session are different authority/session
domains from the logged-in AT-SPI desktop.

## ChromeOS

The developer-mode Chromebook currently exposes unusually rich on-device
control through root SSH, Chrome accessibility, CDP, DRM/EGL capture, and
device-native input. Treat ChromeOS as its own platform rather than generic
Linux.

This is the current reference for the North Star: an outside caller gets
compact system-wide `chrome.automation` semantics, page-level CDP, target-local
pixels/input, and administration without running an agent on the Chromebook or
manipulating it through a host window. The common facade should preserve that
ergonomic power while allowing different native adapters on other systems.

ARCVM is a distinct Android target within the ChromeOS testbed. A local
Chromebook ADB proxy/port forward should expose it through the Android capability
family rather than pretending `chrome.automation` covers Android application
internals.

The on-device route is rich but not independent: an update can break rootfs
changes, SSH startup, remote debugging, or the accessibility extension. The
hardware-KVM project is the intended outer path for normal-mode devices and
recovery, but it is still in bring-up.

## iOS and iOS Simulator

A stock iPhone cannot run a general YA worker. Place the agent on a Mac and
treat the phone as a separate SUT.

- Physical lifecycle and files: Xcode CoreDevice/`devicectl`.
- Semantic control: a signed, persistent XCUITest runner; Agent Device is the
  current provider through `ios-device-testbed`.
- Observation fallback: on-demand screenshots and coordinate gestures.
- Simulator: prefer the same XCTest semantics for parity; YepAnywhere's
  SimulatorKit/IOSurface/IndigoHID helper can remain an optional fast pixel/HID
  route.
- Human gates: passcode, biometrics, Apple Pay, account recovery, and protected
  authorization.

Agent Device's macOS/Linux/web support is not a reason to replace the richer
desktop testbeds, and it has no native Windows desktop backend.

**Open:** Decide whether simulator and physical-device routes share a stable
device-family target identity with different capabilities or remain distinct
targets. Do not hide lifecycle, signing, authority, or fidelity differences to
force one identifier.

## Android and Android-derived devices

ADB is the administration and lifecycle baseline. UIAutomator or an
accessibility helper can provide semantics when needed; screenshots and input
remain fallbacks. The worker normally runs on the attached controller, although
an Android-hosted worker is possible in specialized environments.

Quest adds headset state, wake/proximity policy, and protected in-headset
surfaces. Those remain owned by its testbed rather than a generic Android
provider.

## Physical desktop hardware

When the OS can host YA, prefer a local worker plus native administration and
semantic control. An independent management or hardware path may include:

- SSH or an OS management agent;
- BMC/IPMI/Redfish where hardware supports it;
- HDMI capture plus USB HID;
- remotely controlled power only under a separate, conservative policy; or
- a human gate when no safe independent path exists.

Hardware KVM is authoritative pixels and HID, not semantic truth. It should be
used for bootstrap/recovery and as an independent visual oracle, not as the
normal way to test an accessible desktop application.

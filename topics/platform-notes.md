# Platform Direction

Topic: `platform-notes`

Status: living cross-platform decision summary. Detailed candidate comparison
and investigation status live in the
[platform research index](../research/platforms/README.md).

## Windows desktop

**Decision:** Windows is the first complete vertical slice. Use a
target-resident interactive-session controller reachable through the same
logical facade by local and authorized remote callers. Keep WinVM responsible
for lifecycle, bootstrap, recovery, and safe outer control.

The recent spike establishes Cua as the provisional normal-user core; WinApp is
the adopted comparison/supplement. A session proxy must add truthful active
session, lock/input-desktop, reconnect, and authenticated transport behavior.
Add a SYSTEM broker only for concrete, explicitly armed protected operations.
Computer Use remains an optional in-target route and ergonomic benchmark.

See [Windows control research](../research/platforms/windows.md) and the
[Windows decision topic](windows-resident-control.md).

## macOS desktop

**Decision:** Use a stable consented target-resident helper for ordinary AX,
capture, input, window, and application operations. A local agent is optional.
Keep Tart input outside the ordinary worker route because it can foreground the
VM and interfere with the controller desktop.

Cua has recent live evidence; Peekaboo is the deepest macOS-specific source
reference found. TCC identity, exact-window capture, transient system surfaces,
private API posture, and login/protected domains remain explicit comparison
dimensions.

See [macOS control research](../research/platforms/macos.md).

## Linux desktop

**Decision:** Run semantics in the active target desktop session through
AT-SPI and report X11/XWayland/compositor-specific capture and input honestly.
A private virtual compositor is still target-native control and may be the best
non-interfering test-appliance shape. GDM, lock, and absent user sessions are
different authority domains.

See [Linux control research](../research/platforms/linux.md).

## ChromeOS

**Current:** The developer-mode Chromebook is the closest working desktop
North Star implementation: SSH administration, `chrome.automation`, page CDP,
DRM/EGL capture, and device-native input all execute on the target while an
outside agent receives ergonomic control. Required readiness now includes
stateful idle/lid-suspend inhibition, current-boot application evidence, and a
powerd-start self-healing guard, so the dedicated appliance remains reachable
through SSH with its lid closed. Touch taps use an isolated target-native
uinput device so contacts held against the closed physical panel cannot join
the automation gesture. Stock sleep behavior is not a cleanup state. ARCVM
remains a distinct Android target reached through a Chromebook-local ADB proxy.

**Decision:** Wrap and preserve the adopted stack before considering a rewrite
or common-provider backend. Do not classify ChromeOS as generic Linux.

See [ChromeOS control research](../research/platforms/chromeos.md).

## iOS and iOS Simulator

**Current:** CoreDevice plus a signed XCTest runner through Agent Device is the
adopted physical-device route. The agent runs on an authorized Mac because a
stock phone cannot host the full resident stack.

**Decision:** Preserve this native device-hosted architecture and normalize
inventory, authorization, target selection, capabilities, evidence, and
results with the wider system. Do not force mobile into a desktop process
model.

**Current:** The physical adapter now emits the common device doctor and a
leased CoreDevice full-reboot operation. Passcode-free disconnect/reconnect and
post-boot XCTest recovery are live-proven. Passcode-protected phones remain
supported after local first unlock and report that human gate explicitly after
reboot; no passcode or biometric entry is automated.

See [iOS control research](../research/platforms/ios.md) and the
[iOS device topic](ios-device-control.md).

## Android and derived devices

**Decision:** ADB is the administration, lifecycle, debug, screenshot, and
input baseline. Add UIAutomator/accessibility semantics and common ergonomics;
do not replace mature platform facilities. Keep Quest, ARCVM, TV, emulator, and
physical-device policy in their authoritative testbeds.

**Current:** Android handheld and Quest share neutral ADB discovery and
transport code while retaining distinct phone keyguard and headset policy. The
handheld adapter exposes common readiness and a guarded one-shot PIN path; real
credential effect has not yet been live-tested.

See [Android control research](../research/platforms/android.md) and the
[Android-family topic](android-family-control.md).

## Physical desktop hardware

**Decision:** Prefer resident administration and semantic control whenever the
OS is running. Hardware KVM, BMC, power, capture, and HID remain independent
bootstrap/recovery routes and visual oracles. They do not become routine
semantic control merely because the target is physical rather than virtual.

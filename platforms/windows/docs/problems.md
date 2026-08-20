# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using WinVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### A console on another macOS Space was invisible to provider capture

Status: **resolved 2026-08-04.** Window discovery now considers UTM windows
from every macOS Space, prefers an on-screen match when more than one exists,
and falls back to the largest matching off-Space console. The normalized
1399×985 capture succeeded while the console remained on another Space.

The VM, SSH, guest relay, and UTM input channel all remained healthy, and
macOS accessibility still identified the standard UTM `Windows` window.
Nevertheless, `winvm screenshot` failed with `No visible UTM window` because
Core Graphics discovery used `optionOnScreenOnly`.

Effect: provider-level visual recovery disappeared merely because macOS moved
the UTM window between Spaces. That is especially hazardous when screenshot
plus raw input is the fallback for a system-modal prompt.

### A first-listen firewall prompt can strand the SSH-backed UI relay

Status: **open; correlation observed, cause not yet isolated.** The first LAN
listen by an unsigned candidate displayed the Windows Defender Firewall
consent dialog. While that system-modal dialog was present, both guest-agent
IP discovery and SSH became unavailable. Semantic UI could not dismiss the
dialog because its session-1 relay is reached through SSH; provider screenshot
and raw click remained the only control path. A raw **Cancel** dismissed the
dialog and Windows created public-profile block rules for the candidate, but
the transport did not recover. A normal restart from the secure screen then
wedged on a black console and required a bounded force-stop/start recovery.

The firewall dialog and transport loss happened together, but this observation
does not prove the dialog caused the SSH or guest-agent failure. The guest's
OpenSSH firewall rules included the active profile after recovery.

Effect: a production-style first-LAN-listen test can lose both high-level
control channels at the exact point where a system prompt needs attention.

Workaround: take a provider screenshot before the first listen, keep provider
raw input ready, and use it for system-modal dialogs rather than waiting on the
SSH-backed semantic relay. After recovery, remove any candidate-specific block
rules and, when appropriate for the test, add a narrowly scoped temporary
inbound rule for the exact executable and port. Remove that rule during
cleanup.

Possible direction: teach the production-test helper to recognize the
firewall dialog from provider capture, report that semantic automation is
unavailable, and offer a bounded raw-input recovery path. Add bounded failure
times and diagnostics around IP discovery, SSH, and restart so a transport
loss cannot look like an indefinite controller hang.

### macOS can refuse the accelerated UTM window capture

Status: **open; observed 2026-08-20.** After the accelerated Windows display
initialized, Core Graphics still enumerated the UTM console but macOS refused
both its window-ID capture and a tiny screen-region permission probe. The
Windows-resident GDI capture remained healthy and returned the complete
1280×1024 desktop with no host interference.

Effect: outer visual recovery is unavailable in that host session even though
ordinary target-native control is healthy. The provider now fails closed with
a diagnostic that points to host lock/display state and Screen Recording
permission rather than emitting a black or unrelated host image.

Open: repeat the provider capture after the controller desktop is unlocked and
confirm whether host session state, Screen Recording authorization, or the
accelerated surface is the deciding condition.

### ARM64 desktop builds need explicit guest prerequisites

The clean ARM64 Windows guest could drive installed applications but could not
build a Rust/Tauri candidate. A successful native ARM64 build required the
official Visual Studio 2022 Build Tools with the C++ workload, the ARM64 C++
tools component, LLVM/Clang for crates such as `ring`, and the ARM64 Rustup
toolchain. Visual Studio component modification had to be launched with
`Start-Process ... -Wait`; invoking the bootstrapper directly with `--wait`
returned before component installation finished.

Effect: controller health is not the same as release-build readiness, and a
candidate run can otherwise discover a multi-gigabyte toolchain gap midway
through the platform matrix.

Possible direction: add a separate, opt-in `doctor-build` check or a documented
release-builder bootstrap. Keep the ordinary testbed requirements small: the
controller should not silently install a compiler toolchain merely to drive a
prebuilt application.

### Provider screenshots do not share the coordinate space used by `click`

Status: **re-resolved 2026-08-20.** The original fixed-resolution correction
worked only while the UTM console retained the configured size. Dynamic
resolution later changed the live Windows display between 1024×768 and
1280×1024. The stale 1399×985 configuration then either caused normalization
to fail or produced the wrong click coordinate space. Provider capture now
removes the configured UTM title-bar height and derives output dimensions from
the live viewport. Explicit width and height remain an opt-in for a guest that
does not follow console size.

`winvm screenshot` captures the full macOS UTM window with
`screencapture -l`. On the observed Retina host the PNG was 2798×2050 and
included UTM chrome/title-bar pixels, while the guest display and UTM mouse
API used roughly half-scale guest coordinates.

Effect: a point read from the screenshot cannot be passed directly to
`winvm click`; it needs an undocumented scale and title-bar transform. This
made WebView-only controls need trial-and-error clicks.

The display dimensions remain explicit configuration because screenshot
recovery must work even when SSH and PowerShell display discovery are
unavailable. Update them when the guest logical display mode changes.

### UIA invoke can report dispatch without an application transition

WinApp's InvokePattern reported that the NSIS installer's **Finish** button
was invoked, but the installer remained on the same page and the application
did not launch. The semantic `click` operation on the same named button did
advance the installer and launch the app.

Effect: a successful `ui invoke` response is not proof that the target handled
the action. Workaround: re-inspect the window after every material action and
retry with semantic click when the transition did not occur.

Possible direction: add this warning and the `click` fallback to the UI guide,
and consider an optional action helper that waits for a window/tree change.

### Embedded WebView content has no semantic driver

The 200 OK Tauri frame was discoverable, but its WebView2 controls were absent
from UIA. This limit is already noted in the README, but it is consequential:
settings, switches, server controls, and inline messages required screenshots,
raw clicks, and keyboard focus traversal. That path is substantially less
reliable than WinApp's native-control automation and made a visually clipped
dialog difficult to inspect.

Possible direction: add a WebView2/CDP-capable driver or a documented
application opt-in that exposes embedded web content to accessibility tooling.

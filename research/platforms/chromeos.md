# ChromeOS Control Research

Status: adopted testbed and current desktop North Star reference.

## Current stack

**Current — adopted:** The authoritative
[`platforms/chromeos`](../../platforms/chromeos/README.md) reaches a designated
developer-mode Chromebook through SSH while the actual control mechanisms run
on the target:

- files, processes, and administration over SSH;
- system-wide `chrome.automation` accessibility through the built-in
  accessibility extension;
- page-specific semantics through CDP;
- DRM/EGL capture;
- evdev keyboard input, isolated uinput direct-touch tap/swipe gestures, and
  an experimental uinput mouse;
- a required stateful powerd/embedded-controller policy for idle and closed-lid
  SSH availability; and
- a Chromebook-local ADB proxy for ARCVM as a distinct Android target.

This already proves that an outside agent can receive compact, rich control
without running another agent on the target and without manipulating a host VM
window. `chrome.automation` covers native system surfaces as well as web
content, so ChromeOS must not be reduced to generic Linux or page ARIA.

**Current — live-tested:** Bootstrap and post-update repair install the
documented powerd overrides that disable idle and lid suspend. The stateful SSH
boot helper reapplies the embedded-controller lid override and records
current-boot evidence, and a powerd-start guard heals in-boot resets. Common
doctor and maintenance audit observe the helper, guard, effective preferences,
and boot evidence without mutating power state; a changed-boot live proof
returned the original three policy checks healthy.

**Current — live-tested:** Direct touchscreen tap and swipe gestures use a
short-lived uinput device after a closed-panel run found held physical contacts
sharing the old evdev gesture slots. The isolated device preserved top-left
desktop coordinate mapping, opened the exact Quick Settings control, and
scrolled the ChromeOS Settings sidebar while two physical contacts remained
held. Both physical checks restored their initial UI state.

**Current — live-tested:** New-device bring-up exposed three prerequisites:
controller VPN routing can break LAN SSH even after a target downloads a
bootstrap successfully; developer Python can require `/usr/local/lib64` at
runtime; and the desktop accessibility provider may require Select-to-speak.
The bootstrap now reports local SSH handshakes separately from remote
reachability, while explicit setup provisions Python and verifies desktop
accessibility. The UI smoke test distinguishes a newly opened Quick Settings
gear from a preexisting pinned Settings button using baseline observations.

## Activation and post-update recovery

**Current — fixture-tested:** The recommended standalone `activate.sh` reuses
existing SSH keys and resumes full appliance preparation with the same command
across required reboots. Explicit `--ssh-only`, or declining full activation,
preserves rootfs verification and avoids reboot, root startup-job installation,
DevTools configuration, and Python installation. The original `start_sshd.sh`
remains a minimal entry. Existing appliance SSH paths may still reapply their
previously installed availability policy; limited mode does not undo it.

**Current — live-tested:** SSH-only activation on an updated physical device
returned authenticated SSH while common doctor still reported rootfs
verification enabled and the full runtime unprepared. Full activation then
prepared the active image and reached its announced reboot with the activation
script and progress retained on the stateful partition. VT2 resume restored
SSH autostart, writable-rootfs configuration, and the power-policy guard.
After profile sign-in all eleven smoke checks passed, including semantics,
capture, keyboard, isolated touch, and restoration of the original UI. A later
proof reboot returned SSH automatically on a changed boot with all runtime
maintenance checks healthy; no VT2 recovery was needed.

**Current — live-observed:** A Chrome restart with the debugging flag present
left its listener unavailable while signed out; signing in made the listener
and desktop semantics available. The subsequent normal proof boot had the
listener available even before profile sign-in.

**Current — fixture-tested:** Activation now reports a signed-out profile as pending desktop verification instead of failing system
preparation or repeatedly restarting Chrome. The native audit's `bootReady`
and explicit `--verify-reboot --boot-only` separate startup proof from full
runtime and desktop readiness. HUP survival during a console-affecting Chrome
restart is fixture-tested; the exact signal that interrupted the initial VT2
run was not observed.

**Open:** Activation saves progress on the stateful partition but has no proven
automatic continuation hook after an update replaces the root image. Required
preparation reboots still need the same command rerun from VT2. Full activation,
boot persistence, and unlocked-profile desktop readiness are distinct results.
The controller performs the final deployment and verification. See the
[activation guide](../../platforms/chromeos/README.md#after-a-chromeos-update).

## Closed-lid backlight behavior

**Current — live-tested:** Always-awake policy forces the reported lid open;
it does not keep the panel dark. Power-manager logs showed a user-requested
zero brightness followed by a return to the configured minimum. On the tested
panel, a stateful `min_visible_backlight_level` override of one hardware step
reduced that wake brightness while preserving EGL capture and injected input.
This is a lower brightness floor, not a maximum, a backlight-off guarantee, or
automatic restoration on physical lid opening. Physical light output and
other panel drivers require separate validation.

**Current — source-reviewed:** Chromium's
[internal backlight controller](https://chromium.googlesource.com/chromiumos/platform2/+/main/power_manager/powerd/policy/internal_backlight_controller.cc)
restores nonzero brightness for selected activity and display transitions.
Its forced-off mode also powers displays off, so that API alone does not
provide a dark panel with an active DRM framebuffer. A live `bl_power` write
did not lower the tested panel's reported actual brightness and is not adopted
as an alternative.

**Open:** A physical-lid-aware backlight-off policy that preserves target-native
capture and restores brightness on opening remains unimplemented. Do not undo
the availability overrides to obtain ordinary laptop lid behavior.

## Provider relationship

No surveyed common desktop provider currently supplies a first-class ChromeOS
backend matching the adopted testbed. Cua's current platform registry covers
Windows, macOS, and Linux; treating ChromeOS as Linux would hide its native
routes and omissions.

## Current direction

**Decision:** Preserve the working testbed and wrap its existing framed
operations behind the common contract before attempting a rewrite. Evaluate a
Cua backend, Cua remote sidecar, or independent compatible provider only after
the wrapper proves which contract changes are genuinely required.

**Open:** Complete and validate ARCVM ADB forwarding, harden update-sensitive
SSH/devtools startup, and add an independent hardware-KVM recovery path without
changing the ordinary inner route.

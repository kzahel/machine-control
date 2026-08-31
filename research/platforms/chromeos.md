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

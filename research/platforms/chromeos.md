# ChromeOS Control Research

Status: adopted testbed and current desktop North Star reference.

## Current stack

**Current — adopted:** The authoritative
[`chromeos-testbed`](../../../chromeos-testbed/README.md) reaches a designated
developer-mode Chromebook through SSH while the actual control mechanisms run
on the target:

- files, processes, and administration over SSH;
- system-wide `chrome.automation` accessibility through the built-in
  accessibility extension;
- page-specific semantics through CDP;
- DRM/EGL capture;
- evdev keyboard/touch and experimental uinput mouse; and
- a Chromebook-local ADB proxy for ARCVM as a distinct Android target.

This already proves that an outside agent can receive compact, rich control
without running another agent on the target and without manipulating a host VM
window. `chrome.automation` covers native system surfaces as well as web
content, so ChromeOS must not be reduced to generic Linux or page ARIA.

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

# XDG Desktop Portal

Upstream: [flatpak/xdg-desktop-portal](https://github.com/flatpak/xdg-desktop-portal).

Declared license scope: the RemoteDesktop implementation declares
[LGPL-2.1-or-later](https://github.com/flatpak/xdg-desktop-portal/blob/main/desktop-portal/remote-desktop.c).
The repository uses per-file SPDX declarations and carries LGPL, GPL, MIT,
CC0, and font license texts in
[LICENSES](https://github.com/flatpak/xdg-desktop-portal/tree/main/LICENSES).
Backend and media-plugin licenses remain separate. Machine Control calls
installed D-Bus interfaces and media libraries; it does not copy portal code.

Last review: 2026-10-02.

## Architecture and reach

**Current — source-reviewed:** Desktop backends mediate normal-user access.
[RemoteDesktop](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.RemoteDesktop.html)
owns visible consent, input devices, session start/closure, Notify methods, and
optional EIS connections. [ScreenCast](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html)
adds source selection and a restricted PipeWire descriptor to the same session.
These APIs support ordinary applications as well as sandboxes.

**Decision:** The Linux desktop app uses the installed interfaces directly,
preserving the owned AT-SPI facade. It uses Notify input and GStreamer PipeWire
capture, without a Cua fork, root virtual HID, private permission-store edit,
or silently installed GNOME Shell extension.

## Evidence

**Current — conformance-tested, GNOME x64 VM:** Combined consent returns
one monitor and keyboard/pointer authority. Capture yields a PNG with verified
dimensions/hash. GTK semantic actions, portal pointer, and clipboard-backed
portal paste produce independent file effects. Native approvals, refusal,
expiry, Stop, sharing closure, and old references pass in the source companion
and exact signed Debian/AppImage installs. Discrete wheel and drag effects are
independently observed; lock closes the sharing session.
[Tactical 056](../../docs/tactical/056-linux-desktop.md) owns execution and
package-specific gates.

**Current:** Mutter Notify keysyms acknowledge tested non-keymap Unicode without
inserting it. The adapter reuses the owned clipboard ownership oracle and
portal Ctrl+V, preserving Unicode with an explicit clipboard side effect.

**Current:** GNOME initially selects its sole screen. This profile's GTK4 AT-SPI
tree omits its checked state; toggling deselects it. The test actor preserves
that selection and requires stream metadata plus a real frame. Consent is
bounded and cancelled on Stop/session loss.

## Limits and direction

**Current:** Capture covers the selected screen, not arbitrary target windows.
Input uses shared-screen logical coordinates and reaches the foreground window.
AT-SPI top-level activation can refuse on Wayland; desktop-ID launch remains a
distinct route. Operator/approval/portal and password surfaces stay guarded.
Root appliance input is never a desktop fallback.

**Open:** KDE/wlroots/X11, physical hardware, multi-monitor scaling, restore-token
lifetime, libei comparison, arbitrary window activation, ARM64 desktop execution,
and suspend/resume. Report the actual backend, selected screen and
devices, ordinary-user privilege, and session state.

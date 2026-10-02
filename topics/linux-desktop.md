# Linux Desktop

Topic: `linux-desktop`

Status: source-native GNOME x64 grant/control and browser acceptance passes;
development AppImage lifecycle passes. Final signed installed and update
acceptance is in progress. No published Linux package.

**Decision:** Extend the shared Tauri settings and tray app with an ordinary-user
Linux companion. Reuse the owned AT-SPI facade, with compositor-mediated XDG
RemoteDesktop and ScreenCast consent for input and pixels. The dedicated
appliance's root virtual-HID broker is a separate profile and is never selected
by the desktop app.

**Decision:** Start with Ubuntu 24.04 GNOME 46 Wayland. Report session, semantic,
capture, input, shortcut, and browser availability independently. KDE, wlroots,
X11, lock/login, other users, and physical hardware require their own evidence.

**Decision:** Preserve the compact Access, Permissions, Activity, and Settings
UX, native approval, scoped timed grants, Stop, expiry, own-interface protection,
session-loss revocation, and reference generations. Only the inherited operator
channel can arm or approve; same-user agents with shells are not contained.

**Decision:** Deliver Debian and AppImage packages. AppImage replacement uses
the existing signed Tauri updater. Linux joins the single desktop version,
required changelog, release script, manifest, downloads, and update service;
there is no Linux-only publication flow.

[Tactical 056](../docs/tactical/056-linux-desktop.md) owns the ordered work and
acceptance. [Linux resident control](linux-resident-control.md) owns appliance
behavior; [native distribution](native-distribution.md) owns release policy.

**Current:** The companion passes 45 native GNOME x64 VM checks covering native
approval/denial, pause, scope enforcement, Stop, expiry, sharing closure, old
generations/references, capture hashes, and independent semantic, pointer, and
Unicode effects. Another 29 Chrome for Testing checks establish browser scope,
click and Unicode effects, capture/hash, Stop, stale references, and replacement
reconnect. Portable grants and native Linux compile/Clippy pass. The existing
appliance live smoke passes alongside the desktop companion. A development
AppImage passes 43 native UI/lifecycle checks, including the tray, single
instance, startup registration, real Stop shortcut, native approval, portal
capture/hash, Restart, close-to-tray, and Quit. Both architectures' initial CI
packages pass authentication; final corrected candidate acceptance remains open.

**Open:** Installed portal consent and lifetime, native approval protection, tray visibility on GNOME,
shortcut registration, installed browser integration, startup, packaged replacement,
architecture coverage, and compatibility with the appliance runtime.

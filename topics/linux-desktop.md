# Linux Desktop

Topic: `linux-desktop`

Status: signed Debian/AppImage preview accepted on an Ubuntu GNOME Wayland
x64 VM. Native x64/ARM64 packages are authenticated. No published Linux package.

**Decision:** Extend the shared Tauri settings and tray app with an ordinary-user
Linux companion. Reuse the owned AT-SPI facade, with compositor-mediated XDG
RemoteDesktop and ScreenCast consent for input and pixels. The dedicated
appliance's root virtual-HID broker is a separate profile and is never selected
by the desktop app.

**Decision:** Start with Ubuntu 24.04 GNOME 46 Wayland. Report session, semantic,
capture, input, shortcut, and browser availability independently. KDE, wlroots,
X11, protected login/unlock, other users, and physical hardware require their
own evidence.

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

**Current:** Exact signed x64 Debian/AppImage candidates pass native UI, grant,
portal, independent effect, restart, tray, and operator-loss acceptance. Signed
AppImage replacement passes tamper and active-access refusal, automatic relaunch
Off, stale generations, browser reconnect, and independent browser tasks.
Native lock revokes access and closes sharing. Reboot starts the exact app in
the background with access and sharing Off. Local and outside CLI routes reach
the same companion; the existing appliance smoke passes independently.

**Current:** Linux owns its opt-in XDG startup entry and GNOME Stop shortcut.
Foreign entries are preserved. The system Python companion uses clean library
search paths, and blocking operator IPC stays outside GTK's event thread.
Debian updates use the package manager; AppImage uses the signed updater.

**Open:** Native ARM64 desktop execution, physical hardware, other compositors,
multiple monitors/scaling, suspend/resume, arbitrary window activation, and
protected login/unlock need separate acceptance. Publication and the production
Linux updater route require the unified release transaction.

# Linux Desktop

Topic: `linux-desktop`

Status: public desktop 0.5.3 includes signed Debian/AppImage packages for
x64 and ARM64. Installed x64 acceptance passes on Ubuntu GNOME Wayland;
ARM64 desktop execution remains open.

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
UX, native approval, scoped timed or operator-selected until-stopped grants,
Stop, expiry, own-interface protection,
session-loss revocation, and reference generations. Only the inherited operator
channel can arm or approve; same-user agents with shells are not contained.

**Decision:** Deliver Debian and AppImage packages. AppImage replacement uses
the existing signed Tauri updater. Linux joins the single desktop version,
required changelog, release script, manifest, downloads, and update service;
there is no Linux-only publication flow.

[Tactical 056](../docs/tactical/056-linux-desktop.md) owns initial acceptance;
[059](../docs/tactical/059-public-linux-desktop.md) owns exact-package retesting
and public six-platform publication.
[Linux resident control](linux-resident-control.md) owns appliance behavior;
[native distribution](native-distribution.md) owns release policy.

**Current:** Public 0.5.3 Debian x64 passes production YA verification and the
installed Python CLI's bounded native grant/portal/GTK effect/capture/restart
slice. [Installed agent CLI](installed-agent-cli.md) owns its evidence and
limits. The broader run's Stop-shortcut checkbox did not become checked under
isolated product state; startup/shortcut 0.5.3 parity is not inferred from the
accepted core slice or earlier package evidence.

**Current:** Exact signed public 0.5.0 x64 Debian/AppImage bytes pass native UI,
grant, portal, independent effect, restart, tray, and operator-loss acceptance. Signed
AppImage replacement passes tamper and active-access refusal, automatic relaunch
Off, stale generations, browser reconnect, and independent browser tasks.
Native lock revokes access and closes sharing. Reboot starts the exact app in
the background with access and sharing Off. Local and outside CLI routes reach
the same companion; the existing appliance smoke passes independently.

**Current:** Linux owns its opt-in XDG startup entry and GNOME Stop shortcut.
Foreign entries are preserved. The system Python companion uses clean library
search paths, and blocking operator IPC stays outside GTK's event thread.
Debian updates use the package manager; AppImage uses the signed updater.

**Current:** [Public downloads](https://machinecontrol.dev/downloads/) and
[desktop 0.5.3](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.3)
serve both architectures. [Tactical 059](../docs/tactical/059-public-linux-desktop.md)
retains the earlier 0.5.0 production metadata and signed replacement acceptance.
Positive installed production-feed replacement to 0.5.3 remains separate from
package authentication and the Debian CLI/core acceptance above.

**Open:** Native ARM64 desktop execution, physical hardware, other compositors,
multiple monitors/scaling, suspend/resume, arbitrary window activation, and
protected login/unlock need separate acceptance.

**Current, implementation:** the native operator supports **Until I turn it
off**, reporting `until_stopped` and null remaining seconds. Session loss still
revokes access; scopes, Stop and update exclusion remain enforced. Public
agent requests stay timed. This is not in public 0.5.3. [Tactical 091](../docs/tactical/091-desktop-until-stopped.md)
owns installed acceptance and unified publication. Restart/reboot persistence
is deferred.

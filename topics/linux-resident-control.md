# Linux Resident Control

Topic: `linux-resident-control`

Status: accepted Ubuntu GNOME Wayland logged-in appliance; other compositors,
protected login planes, and physical Linux hardware remain research-stage.

## Current state

The authoritative [`platforms/linux`](../platforms/linux/README.md) now
provides an accepted Ubuntu 24.04 GNOME 46 Wayland logged-in software-testing
surface. A persistent active-user resident exposes the same
`machine-control/v0` Unix-socket contract to guest-local and outside callers.
It owns compact AT-SPI semantics, GNOME display and active-window capture,
argv-only user-systemd application lifecycle, generation-bound references,
and a bounded root appliance input broker available only to the active user.

The guarded corpus covers GNOME Shell, dock, top bar, notifications, Files,
Settings, a file chooser, Polkit detection/cancellation, GTK, Qt/XWayland,
Chromium, and custom-rendered visual fallback. It verifies independent
application or OS effects and fails closed on every outer UTM-window capture
or input operation. A full reboot restores both resident services and rejects
pre-reboot references as stale.

**Current:** Tactical 018 re-proved the retained appliance without cloning or
outer input. Its static device-activated QEMU guest-agent, GNOME auto-login,
resident, semantics, capture, and input all returned after a boot-ID-changing
reboot while outer UI remained prohibited. The same exact candidate reached a
clean stopped promotion handoff and passed a disposable-marker outcome. A live
restart also exposed and fixed the bounded provider race in which guest
execution preceded UTM's first IPv4 result.

**Current:** Tactical 021 added and live-proved a Linux-native maintenance
surface around that accepted shape. A nonce-bound minimized audit checks dpkg
consistency, pending
reboot, declared runtime/development packages, QEMU/SPICE support, the GNOME
Wayland session, resident, input broker, and target-native status before the
common doctor. Its exact-candidate repair changes only installed systemd
startup invariants and keeps a missing guest agent as an explicit recovery
boundary. On-demand certification audits without repair, uses the provider's
changed-boot-ID reboot proof, runs an archive of exact committed source inside
Ubuntu, cleans staging, and stops only after success. Dependency-light policy
fixtures cover the current contract. The retained candidate passed an
idempotent development-profile bootstrap, healthy audit and no-reboot repair,
exact-source portable and Linux-native certification after a changed-boot-ID
reboot, and a final outer-prohibited resident smoke cycle. No clone or
workspace was used, and the appliance was left stopped.

**Current:**
[`Tactical 028`](../docs/tactical/028-linux-libvirt-controller-host.md) built a
separate native x86_64 Ubuntu 24.04 GNOME Wayland appliance under Linux
libvirt/QEMU/KVM. The same resident, AT-SPI, capture, input, fixture,
maintenance, exact-source certification, and local/outside contracts passed
without ordinary host-console access. A receipt-bound QCOW2 workspace proved
discard semantics, and the accepted base was left stopped and claim-free.

## Current goal

**Decision:** Keep this accepted GNOME Wayland profile stable while extending
Linux through separate compositor and authority profiles. The target selector
may change, but guest-local and outside callers should retain the same facade,
capability, result, and reference vocabulary.

## Decisions

- Treat GNOME Wayland as a concrete platform profile, not generic “Linux.”
  Capability reports name the desktop session, compositor, XWayland use,
  portal state, and actual capture/input route.
- Reuse the owned facade and result concepts proven on Windows and macOS while
  keeping AT-SPI, D-Bus, PipeWire, portals, EIS/libei, and any dedicated
  appliance privilege explicit.
- Use the owned native resident as the default for this profile. It is deeper
  for measured Qt semantics and reliable Unicode input and does not require an
  interactive portal for dedicated-appliance input.
- Keep Cua 0.17.0 as an optional composed provider for its rich Chromium
  combined tree/image and GNOME Shell helper's arbitrary target-window
  capture. The measured gaps do not justify a fork.
- Report the input broker honestly as `root_test_appliance`. It is deliberate
  dedicated-appliance authority, not same-user containment or a generic
  workstation route.
- Treat GNOME Settings' labelled but zero-bounds GTK 4 controls as a visual
  fallback: fixed display capture, target-local HID, and an independent
  `gsettings` effect. Do not invent semantic coordinates.
- A private or nested compositor may later be a valuable isolated test target,
  but it is not a prerequisite for proving the existing logged-in GNOME
  appliance.
- GDM, lock screen, encrypted preboot, and absent-user-session control are
  separate authority domains. They are not part of the first logged-in slice.

## Known gaps and next work

The native capture route supports the display and exact active window, not an
arbitrary hidden window. Cua can supply arbitrary target-window capture when
its GNOME Shell helper is deliberately installed. Portal/libei input is a
viable bounded workstation route, but its consent/session lifetime and latency
need a separate non-appliance profile.

GDM, lock screen, encrypted preboot, absent-user sessions, other compositors,
and physical hardware remain separate authority and compatibility profiles.
The completed execution record is
[`Tactical 012`](../docs/tactical/012-linux-gnome-wayland-resident-control.md),
the maintenance execution record is
[`Tactical 021`](../docs/tactical/021-linux-post-update-and-appliance-certification.md),
and exact differential evidence lives in the
[Linux findings](../../machine-control-spike/docs/linux-findings.md).

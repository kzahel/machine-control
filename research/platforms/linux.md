# Linux Control Research

Status: Ubuntu 24.04 GNOME 46 Wayland logged-in appliance accepted; other
desktop sessions, compositors, protected planes, and physical hardware remain
research-stage. Every claim must identify X11, XWayland, the Wayland
compositor, and the active desktop session rather than saying only “Linux.”

## Native foundation

AT-SPI is the semantic foundation in the active user D-Bus session. X11
provides broadly available discovery, capture, activation, and synthetic
input. Wayland deliberately delegates those powers to compositor- and
portal-specific interfaces, so capture and input capabilities differ across
Sway/wlroots, GNOME/Mutter, KDE/KWin, XWayland, and nested compositors.

## Candidate matrix

| Candidate | Evidence | Depth | Current use |
| --- | --- | --- | --- |
| [Cua Driver](../providers/cua-driver.md) | `conformance-tested` on GNOME 46 Wayland | AT-SPI plus GNOME Shell window/capture helper and portal/libei input | Optional composed provider; native resident is the accepted profile's default |
| [Open Computer Use](../providers/open-computer-use.md) | `source-reviewed` | Compact AT-SPI Computer Use runtime; session discovery; best-effort compositor behavior | First common-provider comparison set |
| [Touchpoint](../providers/touchpoint.md) | `source-reviewed` | Compact AT-SPI facade; raw input mainly X11 | Alternative semantics/facade reference |
| [kwin-mcp](../providers/kwin-mcp.md) | `source-reviewed` | Private virtual KWin session, compositor capture, EIS/libei input | Best isolated-session model |
| [OculOS](../providers/oculos.md) | `source-reviewed` | AT-SPI/daemon shape, incomplete capture depth | Service reference |
| Existing linuxVM route | `adopted` for GNOME 46 Wayland | Persistent AT-SPI resident, GNOME capture, appliance virtual HID, user-systemd lifecycle, guarded QEMU guest-agent transport | Accepted logged-in software-testing route; outer UI is recovery-only |

## Accepted GNOME Wayland profile

**Current:** The target-owned `machine-control/v0` facade is available through
the same private active-user Unix socket to guest-local and outside callers.
AT-SPI supplies semantics; GNOME's in-session capture supplies the full display
and exact active window; a root dedicated-appliance broker exposes bounded
virtual HID only to the active user; and argv-only user-systemd units own
application lifecycle. Provider restart and reboot invalidate old references.
Acceptance prohibits host UTM-window capture and input.

Deterministic effects prove GTK, Qt through XWayland with its accessibility
bridge enabled, Chromium with renderer accessibility enabled, and
custom-rendered visual fallback. GNOME Shell, dock, top bar, notifications,
Files, Settings, file chooser, and Polkit detection/cancellation are included.
GTK 4 Settings controls expose labels but zero-sized bounds on this image, so
that cell uses fixed-appliance capture plus target-local HID and verifies the
setting through `gsettings`.

**Decision:** Use the owned native resident as the default on this profile.
Keep Cua as an optional provider for its rich Chromium combined tree/image and
GNOME Shell helper's arbitrary target-window capture. The comparison found
that native AT-SPI covered Qt where Cua did not correlate a semantic tree, and
the native clipboard-backed input preserved Unicode that Cua's older GNOME
libei fallback omitted. Cua portal input is useful for a bounded workstation
route but is unnecessary for the explicitly privileged test appliance.

Exact pinned evidence, timings, observation sizes, and cleanup are recorded in
the [Linux findings](../../../machine-control-spike/docs/linux-findings.md).

## Remaining profiles

**Open:** Build separate evidence matrices for X11, Sway/wlroots, KDE/KWin,
nested compositors, and physical Linux hardware. Test exact arbitrary-window
capture, foreground/background actions, portal lifetime, transient surfaces,
and effect oracles per profile. GDM, lock, encrypted preboot, and absent-user
sessions remain separate protected authority planes.

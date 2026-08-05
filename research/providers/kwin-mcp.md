# kwin-mcp

Upstream: [isac322/kwin-mcp](https://github.com/isac322/kwin-mcp)

Declared license: [MIT](https://github.com/isac322/kwin-mcp/blob/main/LICENSE)
for the repository.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| KDE Plasma 6 Wayland | `source-reviewed` | Virtual/live session setup, AT-SPI, compositor capture, EIS/libei input, and limitations were inspected. No local conformance run. |
| Other Linux desktops | Unsupported as an equivalent route | The architecture depends on KWin-specific interfaces. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

kwin-mcp can start a private `dbus-run-session` and virtual KWin compositor or
connect to an existing KWin desktop. It reads AT-SPI semantics, captures
through KWin's screenshot interface, and injects pointer, keyboard, and touch
through KWin's private EIS RemoteDesktop interface and libei. Optional isolated
home/XDG directories improve test reproducibility.

The private compositor is an important non-interference boundary: real Wayland
applications and native APIs run inside the target session, while the
controller user's desktop receives neither the windows nor the input. This is
target-native control in an isolated test appliance, not an outer KVM path.

Current targeting is more application/session oriented than the full exact
window contract, and screenshot scope is not yet a universal per-window
surface. Private compositor APIs and KDE version coupling require explicit
compatibility evidence.

## North Star fit

kwin-mcp supplies the strongest isolated Linux desktop-session pattern found.
Its value is complementary to a common semantic provider: Cua, Touchpoint, or
another AT-SPI facade could run inside the same private compositor.

## Current disposition

**Proposal:** Use its virtual-session architecture in the later Linux slice
and test common provider adapters inside it. Do not generalize KWin behavior to
GNOME, Sway, X11, or generic Wayland.

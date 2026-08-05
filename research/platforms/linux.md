# Linux Control Research

Status: architecture and source-review stage. Linux follows the Windows slice,
and every claim must identify X11, XWayland, the Wayland compositor, and the
active desktop session rather than saying only “Linux.”

## Native foundation

AT-SPI is the semantic foundation in the active user D-Bus session. X11
provides broadly available discovery, capture, activation, and synthetic
input. Wayland deliberately delegates those powers to compositor- and
portal-specific interfaces, so capture and input capabilities differ across
Sway/wlroots, GNOME/Mutter, KDE/KWin, XWayland, and nested compositors.

## Candidate matrix

| Candidate | Evidence | Depth | Current use |
| --- | --- | --- | --- |
| [Cua Driver](../providers/cua-driver.md) | `source-reviewed` for Linux | AT-SPI plus X11 and compositor-specific Wayland routes, structured refusals, shared fixtures | Leading common-spine candidate; not locally conformance-tested |
| [Open Computer Use](../providers/open-computer-use.md) | `source-reviewed` | Compact AT-SPI Computer Use runtime; session discovery; best-effort compositor behavior | First common-provider comparison set |
| [Touchpoint](../providers/touchpoint.md) | `source-reviewed` | Compact AT-SPI facade; raw input mainly X11 | Alternative semantics/facade reference |
| [kwin-mcp](../providers/kwin-mcp.md) | `source-reviewed` | Private virtual KWin session, compositor capture, EIS/libei input | Best isolated-session model |
| [OculOS](../providers/oculos.md) | `source-reviewed` | AT-SPI/daemon shape, incomplete capture depth | Service reference |
| Existing linuxVM route | `adopted` at testbed depth | QEMU guest agent, user-session launch, AT-SPI, outer recovery | Current lifecycle and baseline route |

## Current direction

**Decision:** Evaluate the common semantic provider independently from the
session appliance. Running Cua or another AT-SPI adapter inside a private KWin
or nested compositor can provide both contract reuse and strong
non-interference.

**Open:** Build a matrix for X11, XWayland, Sway, GNOME, KWin, and the selected
nested compositor. Test exact-window capture, foreground/background actions,
portal lifetime, lock/login domains, Unicode input, transient surfaces, and
effect oracles separately in each accepted environment.

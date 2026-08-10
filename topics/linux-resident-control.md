# Linux Resident Control

Topic: `linux-resident-control`

Status: active GNOME Wayland vertical slice; other compositors and protected
login planes remain research-stage.

## Current state

The authoritative [`linuxvm-testbed`](../../linuxvm-testbed/README.md) already
provides UTM lifecycle, root-equivalent QEMU guest-agent commands, durable
launch into the active desktop user's systemd session, and on-demand AT-SPI
inspection/actions. Those are useful foundations, but the current screenshot
and coordinate-input fallback manipulates the outer UTM window. There is not
yet an owned persistent resident facade or one common local/remote contract.

## Current goal

**Decision:** Go deep first on the existing Ubuntu GNOME Wayland appliance.
Prove a complete logged-in software-testing surface from inside the target
before expanding to X11, KDE, Sway, nested compositors, GDM, or physical Linux
hardware.

The accepted surface should combine:

- compact AT-SPI semantics for applications, windows, GNOME system UI, and
  ordinary controls;
- target-native display/window capture through a compositor-, portal-, or
  otherwise explicitly authorized in-target route;
- target-local pointer, keyboard, text, and scroll fallback through a truthful
  GNOME/Wayland or dedicated-appliance route;
- application/session lifecycle and root-capable non-UI administration;
- explicit handling of Polkit and other protected desktop prompts;
- deterministic GTK, Qt, Electron/browser, and sparse/custom fixtures with
  independent effects; and
- the same facade and result vocabulary for guest-local and outside callers.

The conformance harness must prohibit UTM-window capture and input during
ordinary acceptance. QEMU guest-agent transport remains an inner route when it
only reaches components executing in the guest; it must not become an excuse
to manipulate the graphical console from the host.

## Decisions

- Treat GNOME Wayland as a concrete platform profile, not generic “Linux.”
  Capability reports name the desktop session, compositor, XWayland use,
  portal state, and actual capture/input route.
- Reuse the owned facade and result concepts proven on Windows and macOS while
  keeping AT-SPI, D-Bus, PipeWire, portals, EIS/libei, and any dedicated
  appliance privilege explicit.
- Evaluate Cua as a replaceable common provider against native AT-SPI. Select
  routes by independent effects; do not assume one provider is best for every
  control or framework.
- A private or nested compositor may later be a valuable isolated test target,
  but it is not a prerequisite for proving the existing logged-in GNOME
  appliance.
- GDM, lock screen, encrypted preboot, and absent-user-session control are
  separate authority domains. They are not part of the first logged-in slice.

## Immediate work

Execution is tracked in
[`Tactical 012`](../docs/tactical/012-linux-gnome-wayland-resident-control.md).
Continuing direction belongs here after that tactical completes.

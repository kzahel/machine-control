# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using LinuxVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### There is no documented GUI-application launch path

Status: **resolved 2026-08-04.** `linuxvm gui-launch -- COMMAND [ARG...]`
now verifies the active user's systemd manager has an imported display, starts
the application as a collected transient user service, and prints its unit for
later inspection or teardown. The smoke suite verifies that the launched unit
inherits a real Wayland/X11 display.

`linuxvm user-exec` intentionally supplies the user runtime directory and
D-Bus address but not `DISPLAY` or `WAYLAND_DISPLAY`. Launching an AppImage
through it therefore failed with `Failed to initialize GTK`. The architecture
document explains that it does not guess a Wayland socket, but the CLI offers
no corresponding `ui launch` operation.

The command preserves the deliberate `user-exec` boundary: non-GUI commands
still receive only the runtime directory and session bus rather than a guessed
Wayland socket.

### Common desktop shortcuts are missing from `key`

The provider recognizes a small fixed set of names. `linuxvm key ctrl-l`,
needed for GTK file-chooser path entry, returned `Unknown key name`. Falling
through to `type` without the shortcut activated GTK type-ahead and selected a
different nested folder.

Possible direction: add generic modifier parsing or at least common chooser
and editing shortcuts such as Ctrl-L, Ctrl-A, and Ctrl-C/V. Until then, abort a
sequence immediately when `key` returns nonzero and use semantic actions or
coordinates.

### The action selector supported by `press` is not documented

GTK folder rows exposed multiple actions in this order: **Expand or
contract**, **Edit**, and **Activate**. `press` defaults to the first action,
so using it without an action selector does not open the directory.
`linuxui.py` does support `--action`, but neither the README nor
`docs/ui-automation.md` shows that option.

Possible direction: document `linuxvm ui press QUERY --action Activate` and
include it in `--help` examples for multi-action AT-SPI nodes.

### `shutdown` returns before the VM reaches `stopped`

Status: **resolved 2026-08-04.** `linuxvm shutdown` now polls UTM until the VM
reports `stopped`, returns that state on success, and fails with the last state
after `LINUXVM_SHUTDOWN_TIMEOUT`. It never escalates a timeout to force-stop.

Immediately after `linuxvm shutdown`, `linuxvm status` still reported
`started`; a short poll then reported `stopped`.

Cleanup scripts can now treat a successful shutdown command as the terminal
lifecycle boundary.

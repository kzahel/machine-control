# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using LinuxVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### There is no documented GUI-application launch path

`linuxvm user-exec` intentionally supplies the user runtime directory and
D-Bus address but not `DISPLAY` or `WAYLAND_DISPLAY`. Launching an AppImage
through it therefore failed with `Failed to initialize GTK`. The architecture
document explains that it does not guess a Wayland socket, but the CLI offers
no corresponding `ui launch` operation.

Workaround: `systemd-run --user` inherits the GNOME user manager's imported
display environment and launched the AppImage successfully.

Possible direction: add a session-owned GUI launch command that reads the
active user manager environment, or document the `systemd-run --user` recipe
next to `user-exec`.

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

Immediately after `linuxvm shutdown`, `linuxvm status` still reported
`started`; a short poll then reported `stopped`.

Effect: cleanup scripts can finish while the VM is still shutting down.
Possible direction: either wait for the terminal state within the configured
timeout or document the asynchronous contract and provide a `wait` command.

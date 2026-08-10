# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using LinuxVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Resolved 2026-08-10 during resident reboot acceptance

### Enabled resident services were not boot-ready

The first guarded reboot returned the QEMU guest agent before GNOME autologin.
Doctor sampled the session too early. The user resident also started from
`default.target` before the user manager received `WAYLAND_DISPLAY`, while the
root input broker's `After=graphical.target` ordering conflicted with its
`multi-user.target` enablement and left it inactive.

The input broker now orders only after logind. The user resident is re-enabled
under `graphical-session.target`, and doctor waits boundedly for the active
Wayland user, AT-SPI, and the complete semantic/capture/input status. A second
clean reboot restored both services, changed the resident generation, refused
a pre-reboot reference as stale, and passed smoke plus full GNOME/framework
acceptance with outer UI prohibited.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### Cold start can race guest-agent readiness

`linuxvm up` returned an Apple-event `OSStatus error -2700`, followed by guest
agent/IP failures, when invoked against the stopped VM. GNOME reached the
desktop and `qemu-guest-agent` was active, and the same doctor passed after the
cold boot settled. The first result was therefore a transport-readiness race,
not a failed guest service.

The 2026-08-04 candidate-validation rerun also found that this failure path can
leave the VM started without an on-screen UTM console. The settled doctor then
passed the command channel, session, and AT-SPI checks but failed **visible UTM
window**. Running `open -a UTM` on the Mac host exposed the already-running VM
console once; on later boots it opened only the UTM library. Choosing the VM
from UTM's **Window** menu exposed the console without restarting the guest,
and the next doctor passed every check. Treat that as the bounded workaround
until `up` owns both readiness and visible console presentation.

Possible direction: make `up` wait for a bounded guest-agent readiness result
or return an unambiguous started-but-not-ready status, ensure the requested VM
console is visible after a successful start, and place a timeout around each
`utmctl exec` readiness probe so a cold-start check cannot block past the
controller deadline.

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

The ARM64 Chrome store run also needed End to reach Google's consent buttons;
`linuxvm key end` failed with the same unknown-key result. Raw scan codes were
an effective fallback for that key.

Possible direction: add generic modifier parsing plus navigation keys, or at
least common chooser/editing shortcuts such as Ctrl-L, Ctrl-A, Ctrl-C/V, Home,
End, Page Up, and Page Down. Until then, abort a sequence immediately when
`key` returns nonzero and use semantic actions, documented scan codes, or
coordinates.

### Raw shortcuts do not establish the intended guest window focus

Two `linuxvm key alt-f4` calls returned success while a visible application
window remained open. AT-SPI actions used immediately beforehand operated the
application semantically but had not made its frame the active recipient of
raw guest input. The frame published by `mutter-x11-frames` exposed a
`window.close` action; invoking its visible **Close** control closed the exact
window and allowed the product's last-window behavior to be validated.

Possible direction: document that `key` targets the guest's existing input
focus, not the application most recently addressed by `linuxvm ui`. Add a
first-class semantic window activate/close example or command so callers do
not infer target focus from a successful raw-key return.

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

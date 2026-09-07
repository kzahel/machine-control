# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using MacVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-09-03 during first bring-up from a non-GUI controller session

### The launchd runner starts a windowless VM, disabling the whole outer path

Observed: `macvm up` bootstraps `tart run` into `gui/$UID` with
`ProcessType Interactive` and `LimitLoadToSessionType Aqua`, and the VM boots
and serves `tart exec` normally. But no Tart window is ever created, so every
outer command fails with `No visible Tart window named 'NAME' was found; run
without --no-graphics` even though `--no-graphics` was never passed. The window
is not merely off-screen: a full `CGWindowListCopyWindowInfo(.optionAll)` sweep
finds zero Tart windows.

The cause is the controller session, not Tart and not the plist. When the
invoking agent or terminal is not itself in an Aqua GUI session, processes it
spawns get no window-server connection, and `launchctl bootstrap gui/$UID`
from that context does not repair it. This reproduces cleanly with any GUI
binary: launching one through LaunchServices (`open -a Calculator`) yields a
window, while executing the same binary directly
(`Calculator.app/Contents/MacOS/Calculator`) yields none. Screen Recording is
irrelevant to this failure; window titles were fully readable throughout.

Effect: on such a controller the documented bootstrap consent flow is
unreachable, because granting guest Accessibility and Screen Recording needs
the outer path and the outer path needs a window. Guest administration,
`deploy-ui`, and `authorize-ui` still work, so the target looks healthy while
`semantic`, `capture`, and `input` stay unavailable with no obvious cause.

Workaround: start the VM through LaunchServices so it inherits the Aqua
session, then activate it before each outer command, because the window is
created unmapped and only appears on screen once the application is activated:

```bash
open -a "$(dirname "$(dirname "$MACVM_TART")")/libexec/tart.app" --args \
  run --suspendable --capture-system-keys --dir=macvm-testbed:REPO:ro NAME
open -a .../tart.app     # activate; otherwise the window stays off-screen
bin/macvm screenshot /tmp/guest.png
```

A VM started this way is outside the launchd runner, so `macvm up` will not
manage it and a later `up` reproduces the windowless state.

Possible direction: have the provider detect the absent window and either
launch through LaunchServices itself or fail with a diagnostic that names the
non-GUI controller session as the cause, rather than suggesting
`--no-graphics`. A one-shot `macvm activate-window` would also make the
unmapped-window step explicit instead of incidental.

### Changing run flags silently invalidates a suspend snapshot

Observed: a VM suspended while `MACVM_FORBID_OUTER_UI=true` (so `tart run`
omitted `--capture-system-keys`) refused to resume once that flag was flipped,
failing with `VZErrorDomain Code=12 ... failed to restore with error "invalid
argument"`. Virtualization.framework requires an identical machine
configuration to restore saved state, and the outer-UI policy changes it.
A stale `state.vzvmsave` also blocks a cold boot until removed, and killing a
mid-suspend `tart` leaves `Failed to lock auxiliary storage`.

Effect: a policy change unrelated to lifecycle can strand a suspended VM, and
the error names neither the flag nor the snapshot.

Workaround: shut the VM down rather than suspending it before changing
outer-UI policy; to recover, remove `~/.tart/vms/NAME/state.vzvmsave` and cold
boot, accepting the loss of suspended RAM state.

Possible direction: record the run flags beside the snapshot and refuse to
suspend, or warn on resume, when the effective configuration has changed.

## Observed 2026-08-10 during inner-only Aqua acceptance

### Tart system-key capture retained host keyboard focus

Status: **mitigated 2026-08-10.** The testbed now defaults
`MACVM_CAPTURE_SYSTEM_KEYS` to `false`, and outer-UI-forbidden launches suppress
the Tart flag even if local configuration requests it. System-key capture is
an attended outer-recovery option only.

A long-running Tart process started with `--capture-system-keys` retained the
host keyboard grab after focus moved to another host application. The host
menu bar continued to identify Tart and other applications could not receive
typing. Suspending the VM removed the Tart process and released the grab;
restarting host SystemUIServer and Control Center restored the menu bar.

Effect: a VM doing target-resident tests could still interfere with its
controller host even though no host-side screenshot or input operation ran.
The outer-UI command guard alone was insufficient while the Tart launch itself
requested a global system-key capture.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### `macvm up` is not durable under process-group-reaping command runners

Status: **resolved 2026-08-04.** `macvm up` now submits `tart run` as a
transient job in the current user's launchd GUI domain. A separate invocation
verified the VM remained running after the launcher command and its process
group exited. Suspend is allowed to finish and exit the runner naturally so
the saved state remains available; the next `up` replaces the inactive job.

`providers/tart-macos/provider.sh` starts `tart run` with `nohup ... &` and
returns once Tart reports `running`. Under an agent command runner that reaps
the completed command's process group, Tart exits as soon as the `macvm up`
invocation ends even though `nohup` was used. Ordinary interactive shells may
not reproduce this.

Effect: a successful `up` is followed immediately by a stopped VM and later
commands fail. Keeping the launching shell alive in a persistent execution
session made the VM stable for the full smoke.

The launchd runner retains the graphical Aqua session, suspendability,
system-key capture, and read-only repository share used by the prior direct
launch.

### Tree formatting hides a control's value when it also has a label

Status: **mitigated in the resident facade 2026-08-10.** Legacy text output is
unchanged, but resident full and compact records carry label and value
separately. A composed Cua result exposed both a System Settings checkbox
label and its value during the live resident test.

`macui` records title, description, and AX value, but `formatted(_:)` prints
only the first non-empty member. A labeled checkbox or switch therefore shows
its label but not its `0`/`1` value. Queries can still match the value, but a
human or agent cannot inspect checked state from normal tree output.

Effect: the 200 OK app-settings switches were discoverable by name but their
state had to be verified through persisted settings or side effects.

Possible direction: print non-duplicate `value=` data separately, especially
for switches, checkboxes, radio buttons, text fields, and sliders.

### `set-value` does not reliably commit WebView-controlled inputs

Setting the AX value of a React number input changed the accessible value but
did not dispatch the DOM input/change event used by React, so the new port was
not persisted.

Effect: `macvm ui set-value` can report success without changing application
state for WebView inputs.

Workaround: use physical focus/select/type input and verify the application
side effect. Possible direction: document this boundary explicitly or add a
WebView-aware input path that generates real keyboard/DOM events.

### Native open panels can expose unnamed rows

The macOS folder chooser sometimes exposed row/cell elements with empty title,
description, and value fields. In that state semantic queries could not name
the target directory even though it was visibly present.

Workaround: use Command-Shift-G and enter an exact path, or use a fresh
screenshot and coordinates. Possible direction: document the path-navigation
recipe and consider deriving row text from named child cells when available.

### Semantic tree discovery and actions can disagree

Status: **mitigated in the resident facade 2026-08-10.** In Chrome, `macvm ui tree` exposed meaningful controls,
including the address field, extension toolbar controls, and extension page
content. Fresh `ui find`, `ui press`, and `ui set-value` invocations could not
reliably rediscover some of those same controls, even with the same explicit
application selector and an increased traversal depth.

Effect: a control can appear automatable during inspection but fail when the
test attempts to act on it. Because each command starts a fresh helper and
rebuilds the Accessibility snapshot, dynamic browser UI and focus changes may
contribute to the disagreement.

Possible direction: make tree output and state-changing actions share one
query/traversal implementation, add diagnostic output explaining why visible
records were excluded, and add regressions for Chrome's address field,
extension toolbar controls, and extension page buttons. A longer-lived
guest-side helper may be worth evaluating if fresh AX references are the root
cause.

The resident holds generation-scoped references and its Cua adapter preserves
the provider snapshot token through the subsequent action. Stale-reference
conformance lives in the machine-control corpus; legacy one-shot commands
remain diagnostic compatibility commands.

### Host keyboard modifier chords can degrade into literal input

Status: **unresolved.** During Chrome automation, `macvm key cmd-l` entered a
literal `l` instead of focusing the address field. Another modified shortcut
also produced printable input rather than the requested chord. The VM had been
started with Tart system-key capture enabled, so this was not explained by the
documented launch prerequisite.

Effect: shortcut-driven navigation can corrupt text or URLs and invalidate a
test step while still appearing to complete successfully.

Possible direction: add end-to-end chord tests against a simple guest-native
target, inspect how CoreGraphics flags and modifier key transitions reach
Tart, and prefer a guest-local keyboard action for normal post-bootstrap
automation.

### Outer input disrupts concurrent work on the host

Status: **unresolved design gap.** `macvm click`, `macvm type`, and `macvm key`
foreground the Tart window and send input from the host. This is appropriate
for bootstrap, consent, and recovery, but it steals focus and can interfere
with someone using the host when semantic automation falls back to it during a
routine test.

Effect: unattended MacVM validation is not currently safe to run alongside
interactive host work if it may use outer input.

Possible direction: make routine automation guest-native and non-disruptive by
default. Add an explicit no-host-input mode that fails rather than falling
back, reserve outer input for an opt-in exclusive/recovery mode, and provide
guest-native primitives for common operations such as opening a URL in a
chosen browser and sending a keyboard chord to a chosen application. Document
which commands can activate the Tart window.

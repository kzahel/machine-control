# Running Problems and Improvement Notes

This is a living record of concrete gaps encountered while using MacVM
Testbed. Keep observed behavior, effect, workaround, and a likely improvement
direction together so later work can reproduce the problem.

## Observed 2026-08-04 during 200 OK `v0.1.6` smoke

### `macvm up` is not durable under process-group-reaping command runners

`providers/tart-macos/provider.sh` starts `tart run` with `nohup ... &` and
returns once Tart reports `running`. Under an agent command runner that reaps
the completed command's process group, Tart exits as soon as the `macvm up`
invocation ends even though `nohup` was used. Ordinary interactive shells may
not reproduce this.

Effect: a successful `up` is followed immediately by a stopped VM and later
commands fail. Keeping the launching shell alive in a persistent execution
session made the VM stable for the full smoke.

Possible direction: provide a launchd-owned or otherwise fully detached Tart
launch mode, and add a doctor/smoke probe that verifies the VM remains running
after the launcher process exits.

### Tree formatting hides a control's value when it also has a label

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

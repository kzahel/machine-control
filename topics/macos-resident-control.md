# macOS Resident Control

Topic: `macos-resident-control`

Status: ordinary-session and normal administrator-sheet slices complete;
login/preboot and broader administration remain.

## Current state

The authoritative [`macvm-testbed`](../../macvm-testbed/README.md) now packages
a persistent ordinary-session facade inside the stable MacVM UI application
identity. Guest-local and `tart exec` callers use the same user-owned socket,
generation, request vocabulary, and normalized result shape without routine
Tart-window input.

Native Workspace, AX, Quartz, and CoreGraphics providers are ready for
applications/windows, compact semantics/actions, Dock, Control Center,
exact-window capture, key input, and lifecycle. Cua is installed as a
replaceable adapter and is selected for default text insertion because the
identical fixture oracle proved a value effect that native Unicode key events
did not. Explicit provider requests never fall back.

Normal logged-in Aqua administrator sheets are now part of the accepted inner
surface. The resident strictly fingerprints the active `SecurityAgent`
requester, prompt, process, exact window, secure field, and unique buttons
before issuing a short-lived, generation-bound, single-use lease. A separate
interactive helper reads one credential without echo and streams it over the
resident's mode-`0600` socket without placing the secret in JSON, arguments,
environment, files, captures, logs, or results. The calling workflow remains
responsible for independently proving its intended privileged effect.

## Decisions

- Start from a copy-on-write clone of the prepared Tart base. Do not rebuild
  macOS from IPSW merely to prove the ordinary resident contract.
- Keep Tart lifecycle, bootstrap, consent, and recovery in macvm-testbed.
  Reaching a target-resident process through `tart exec` is an inner route;
  Tart-window input is outer recovery.
- Put the stable operation/result facade and reusable conformance corpus in
  this repository. A macOS-native runner may remain in macvm-testbed when its
  packaging and TCC identity are inseparable from that testbed.
- Reuse the Windows contract shape where it is exercised and honest: explicit
  applications/windows, compact semantics, capture, input, window state,
  actual route, delivery, effect, uncertainty, generation, and cleanup.
- Use a stable signed application identity for Accessibility, Screen Recording,
  and input consent. Never edit or transplant TCC databases.
- Make guest-native AX/application APIs, capture, and input the ordinary path.
  Outer Tart pixels/input must fail closed unless bootstrap or recovery was
  explicitly selected.
- Normalize provider data inside the facade. Compact projection changes detail,
  not field names, and filtered semantic queries must not return an unrelated
  full tree.
- Route per measured operation. The current composition uses Cua for default
  text insertion and native routes for the rest of the accepted surface.
- Treat loginwindow, FileVault/preboot, Recovery, another user's session, and
  arbitrary privileged administration as later protected-plane slices. A
  normal Aqua `SecurityAgent` sheet is accepted only through its bounded
  one-shot lease; it is not evidence of unrestricted root control.

## Accepted ordinary-session surface

The first complete slice covers a logged-in Aqua session and exercises:

- local and `tart exec` callers through the same facade;
- application/window inventory, stable selection, lifecycle, and exact
  capture;
- Finder, Dock, menu bar/Control Center, System Settings, TextEdit, and Safari;
- semantic observation and actions with independently observed effects;
- guest-native keyboard/pointer behavior without host focus or cursor changes;
- provider/helper restart, generation changes, and truthful degraded states;
- bounded artifacts and owned-state cleanup; and
- stopped retention of the accepted copy-on-write appliance.

Completed execution is recorded in
[`Tactical 008`](../docs/tactical/008-macos-ordinary-session-resident-control.md).

The reusable corpus lives under [`tests/macos`](../tests/macos/README.md). It
passes target-local and remote placement, real applications, native/Cua
fixture comparison, Dock, Control Center, normal consent retention, resident
restart, stale references, exact capture, cleanup, and unattended reboot
recovery. The retained copy-on-write appliance is stopped; its prepared source
remains suspended.

## Accepted administrator-sheet surface

[`Tactical 009`](../docs/tactical/009-macos-administrator-sheet-control.md)
adds normal Aqua administrator authorization to the same resident. A harmless
native fixture records requested, cancelled, authorized, and command-completed
states independently. Live conformance proves:

- exact requester matching and typed refusal without visual or outer fallback;
- native cancellation and independently observed dismissal;
- single use, short expiry, changed-sheet detection, and generation invalidation;
- one controlled wrong credential with `no_effect` and no automatic retry;
- a correct credential with independently confirmed read-only privileged
  command completion;
- full guest reboot followed by a fresh bounded authorization workflow; and
- fixture, oracle, and transient authorization artifact cleanup.

The accepted appliance needed no root daemon or privileged broker for this
surface. Initial Accessibility consent still cannot use the resident before
the resident is trusted.

## Later boundaries

- Bounded non-UI privileged administration and policy.
- Lock/loginwindow credential transport and session-state reporting.
- FileVault and preboot recovery.
- Multiple displays, Spaces, minimization/occlusion, localization, and long
  soak runs beyond the first acceptance corpus.
- Whether repeated evidence justifies adopting, forking, or replacing Cua or
  deeper macOS-specific provider code.

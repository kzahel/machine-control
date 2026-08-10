# Tactical 012: Linux GNOME Wayland Resident Control

Status: active.

Topics: `linux-resident-control`, `inner-first-routing`, and
`capabilities-and-results`.

Research:
[`Linux platform report`](../../research/platforms/linux.md).

Authoritative testbed:
[`linuxvm-testbed`](../../../linuxvm-testbed/README.md).

## Objective

Turn the existing Ubuntu GNOME Wayland VM into a guarded, target-native
software-testing appliance. An agent inside the guest or outside it must reach
the same resident control contract for compact semantics, capture, input,
application/session management, system surfaces, and administration without
ordinary UTM-window capture or input.

## Completion conditions

- All mutation occurs on an explicitly guarded candidate or disposable clone.
  The existing source VM is protected, and the accepted candidate is stopped
  normally at completion.
- Acceptance fails closed if any UTM screenshot, click, drag, text, key, or
  scan-code command is attempted. A read-only host oracle proves the host
  cursor and foreground application do not change.
- One active-user resident and Unix socket expose versioned, normalized
  requests to both the guest-local CLI and the outside testbed wrapper. Both
  placements share the same generation, references, routes, artifacts, and
  result vocabulary.
- Compact AT-SPI snapshots/actions cover ordinary GTK controls and relevant
  GNOME Shell, dock, top-bar, Settings, Files, notification, and dialog
  surfaces. Independent application or OS effects remain authoritative.
- Full-display and best-available exact-window capture execute in the target
  session. Results identify PipeWire, portal, compositor, D-Bus, or other
  actual routes and distinguish unsupported exact-window fidelity honestly.
- Pointer, click, drag, scroll, keyboard, and Unicode text fallback execute
  inside the guest through a compositor-approved or explicitly authorized
  dedicated-appliance route. No accepted input moves the host pointer or types
  into the host session.
- A Cua/native comparison exercises identical deterministic effects and
  records provider reach, omissions, latency, observation size, and fallback
  behavior. Provider acknowledgement alone never establishes correctness.
- Deterministic GTK plus available Qt, Electron/browser, and custom-rendered
  paths prove semantic or visual fallback behavior from both placements.
- Root-equivalent guest-agent administration and Polkit UI behavior are
  described separately. Protected UI fails closed unless an explicit,
  secret-safe authorized route is proved; shell authority is not mislabeled as
  a bounded desktop authorization broker.
- Resident/helper restart and full guest reboot restore the logged-in ready
  surface. Fixtures, artifacts, transient units, portal sessions, and owned
  state are removed before normal shutdown.

## Boundaries

- The first slice targets Ubuntu 24.04 GNOME Wayland on the existing UTM
  appliance. X11-only sessions, KDE/KWin, Sway/wlroots, nested compositors, and
  other distributions remain separate profiles.
- GDM, lock screen, absent-user sessions, encrypted preboot, Recovery, and
  physical-device input are deferred protected planes.
- Fresh Ubuntu autoinstall and a distributable golden-image factory are not
  prerequisites. The accepted candidate and bootstrap deltas must still be
  reproducible and documented.
- Do not weaken Wayland, portal, Polkit, secure-input, or desktop-session
  boundaries merely to make an API return success. A dedicated test appliance
  may authorize stronger target-resident capture/input or administration, but
  its privilege and scope must be reported honestly.
- Do not force every route through Cua or native code. Keep the owned facade and
  choose measured providers per operation and environment.

## Implementation steps

### 1 — protect the source and prohibit outer UI

Inventory the selected VM, create or verify a copy-on-write candidate, add
role/name mutation guards, and add an acceptance mode that rejects every
UTM-window observation/input command while retaining lifecycle and guest-agent
transport.

### 2 — establish the resident contract

Package the active-session controller as a stable resident service with a
private user-owned socket and guest-local CLI. Normalize status, capabilities,
applications, windows, compact snapshots, actions, generation-bound
references, delivery, effect, uncertainty, and route metadata. Prove identical
guest-local and outside requests.

### 3 — complete target-native capture and input

Inventory GNOME portal, PipeWire, compositor, EIS/libei, D-Bus, and
dedicated-appliance options. Implement the strongest supported full-display,
window, pointer, keyboard, text, drag, and scroll routes behind the facade.
Keep explicit consent and privilege visible in capabilities and results.

### 4 — exercise GNOME and real application surfaces

Drive the shell, dock, top bar, Settings, Files, notifications, file choosers,
menus, modal dialogs, and Polkit behavior. Build deterministic framework and
custom-rendered fixtures with file/API oracles, then exercise both placements
and provider composition.

### 5 — prove recovery and cleanup

Restart providers and the resident, invalidate stale references, reboot the
guest, and replay representative semantic, capture, input, system, and
framework cells under the outer-UI guard. Remove all corpus-owned state and
stop the candidate normally.

### 6 — publish the accepted Linux profile

Update the testbed runbook, Linux topic and platform report, provider dossiers,
root synthesis, and this execution record with exact routes, fidelity,
privilege, omissions, and deferred compositor/protected-plane work.

## Validation record

Pending live implementation and acceptance.

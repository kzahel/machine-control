# macOS Resident Control

Topic: `macos-resident-control`

Status: active ordinary-session implementation concern.

## Current state

The authoritative [`macvm-testbed`](../../macvm-testbed/README.md) already
provides Tart lifecycle, prepared-image bootstrap, `tart exec`, a stable
consented Swift Accessibility helper, normalized outer screenshots, and
explicit recovery input. The existing helper is target-native, but each
command launches a fresh process, its result vocabulary is testbed-specific,
and routine input fallbacks still depend on foregrounding Tart.

The [macOS platform report](../research/platforms/macos.md) records live Cua
evidence and source-reviewed macOS-specific providers. Cua is a comparison and
possible common-plane adapter, not a predetermined dependency. The existing
native AX route is the implementation baseline; adopt Cua only for measured
advantages behind the owned facade.

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
- Treat loginwindow, FileVault/preboot, secure input, authorization sheets,
  and arbitrary privileged administration as a later protected-plane slice.

## First acceptance surface

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

Execution is tracked in
[`Tactical 008`](../docs/tactical/008-macos-ordinary-session-resident-control.md).

## Later boundaries

- Protected administration and authorization leases.
- Lock/loginwindow and credential transport.
- FileVault and preboot recovery.
- Multiple displays, Spaces, minimization/occlusion, localization, and long
  soak runs beyond the first acceptance corpus.
- Whether repeated evidence justifies adopting, forking, or replacing Cua or
  deeper macOS-specific provider code.

# macOS Resident Control

Topic: `macos-resident-control`

Status: full logged-in Aqua software-testing milestone accepted for Tart,
including Java Swing and Electron;
lock/login, preboot, Recovery, and physical hardware are deferred.

## Current state

The authoritative [`platforms/macos`](../platforms/macos/README.md) now packages
a persistent ordinary-session facade inside the stable MacVM UI application
identity. A per-user Aqua LaunchAgent starts and keeps that signed resident
available after login, reboot, or a crash; doctor observes it without starting
it. Guest-local and `tart exec` callers use the same user-owned socket,
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

The dedicated Tart appliance also deliberately gives its test administrator
passwordless `sudo` through the guest command channel and enabled SSH service.
That provides functional target-native package, file, service, and command
administration for the current disposable-appliance profile. It is not a claim
that the common facade yet has a bounded privileged API suitable for a personal
workstation.

## Current Tart goal

**Decision:** Until physical Mac testing becomes an active workstream, focus
macOS implementation on complete software testing inside a prepared,
continuously logged-in Tart Aqua session. After the one-time controller
bootstrap, an agent must not need Tart-window capture, Tart-window input, or
another host/hypervisor UI route to operate software or respond to a prompt.

The caller may run inside the guest or reach the same resident from outside.
That placement changes only transport. Both placements must have the same
semantic, visual, input, administration, dialog, authorization, and effect
vocabulary.

This goal includes:

- native semantic observation and actions wherever macOS exposes useful AX;
- full-display and exact-window capture produced inside the guest;
- target-local coordinate keyboard and pointer fallback for sparse,
  custom-drawn, or otherwise non-semantic UI;
- System Settings and the privacy/consent prompts relevant to software under
  test, including repeatable Allow, Deny, reset, and effect verification;
- administrator sheets, native open/save panels, notifications, installers,
  disk-image and download workflows, menus, and other modal application UI;
- representative AppKit, SwiftUI, Electron, web, Java, and custom-rendered
  software paths as available in the appliance; and
- local/remote parity, bounded artifacts, truthful failure, reboot recovery,
  and zero host-desktop interference.

Semantic control is preferred for efficiency, but in-guest pixels plus
in-guest coordinate input are an accepted target-native fallback. The defining
constraint is where observation and action execute, not whether every program
has a rich accessibility tree.

The conformance harness must be able to prohibit outer UI operations so a test
cannot pass by silently focusing or driving the Tart window. Tart lifecycle and
the guest-agent command transport remain allowed; they do not manipulate the
guest desktop from outside.

## Decisions

- Start from a copy-on-write clone of the prepared Tart base. Do not rebuild
  macOS from IPSW merely to prove the ordinary resident contract.
- Keep Tart lifecycle, bootstrap, consent, and recovery in the canonical
  `platforms/macos` implementation.
  Reaching a target-resident process through `tart exec` is an inner route;
  Tart-window input is outer recovery.
- Keep the stable operation/result facade, TCC-bound packaging, lifecycle, and
  reusable conformance corpus together in this canonical repository.
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
  text insertion. Native AX supplies AppKit, SwiftUI, and Swing semantics. The
  deterministic Electron cell explicitly uses Cua semantics after native AX
  exposed and acknowledged its Chromium button without producing the
  file-oracle effect; Cua produced that effect after target activation and
  bounded semantic-readiness polling.
- Treat loginwindow, FileVault/preboot, Recovery, another user's session, and
  bounded privileged APIs for less-trusted deployment profiles as later
  protected-plane slices. A normal Aqua `SecurityAgent` sheet is accepted only
  through its bounded
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

## Accepted full Aqua software-testing surface

[`Tactical 010`](../docs/tactical/010-macos-full-aqua-software-testing.md)
completes the current Tart goal. Outer screenshot and input are fail-closed in
acceptance, while both guest-local and outside callers use the same resident
for native semantics, exact and full-display capture, target-local input,
applications, artifacts, and authorization.

The live corpus now includes:

- repeatable Camera, Microphone, Automation, Accessibility, Input Monitoring,
  Screen Recording, Local Network, notifications, protected folders, and Full
  Disk Access policy workflows through supported prompts and System Settings;
- open/save/folder panels, menu and menu-extra surfaces, nested sheets,
  relaunch, quarantine/Gatekeeper, Safari download approval, DMG mounting, and
  harmless package installation;
- exact fail-closed authorization profiles for ordinary SecurityAgent,
  Installer, System Settings, and Gatekeeper's LocalAuthentication sheet;
- compact AppKit, SwiftUI, Java Swing, and Electron semantics through both
  placements, Safari/web, and an in-guest pixel/input fallback for sparse
  custom-rendered UI; and
- resident restart, full unattended guest reboot, representative post-reboot
  replay, complete corpus cleanup, and normal candidate shutdown.

The current image has SIP disabled, so protected-data policy UI is controllable
but Full Disk Access and protected-folder enforcement cannot be proved on that
image. Tart has no camera or microphone hardware; consent state and hardware
absence are reported separately.

[`Tactical 011`](../docs/tactical/011-macos-java-electron-framework-coverage.md)
closes the framework-runtime omission with pinned ARM64 Temurin, Node, and
Electron distributions. Deterministic Swing and Electron apps supply file
oracles and stable bundle identities. The four-framework corpus passed local
and remote semantics plus exact-window capture before and after full reboot,
with outer UI forbidden and the host oracle unchanged. Fixtures are removed
after acceptance while the reusable runtimes remain installed.

## Later boundaries

- A bounded privileged facade for personal or less-trusted deployment profiles;
  the disposable Tart appliance already has functional passwordless root shell
  access.
- Lock/loginwindow credential transport and session-state reporting.
- FileVault and preboot recovery.
- Multiple displays, Spaces, minimization/occlusion, localization, and long
  soak runs beyond the first acceptance corpus.
- Whether repeated evidence justifies adopting, forking, or replacing Cua or
  deeper macOS-specific provider code.

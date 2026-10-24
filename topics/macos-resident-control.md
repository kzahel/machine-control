# macOS Resident Control

Topic: `macos-resident-control`

**Current:** the experimental workstation
[locked-use implementation](macos-locked-use.md) adds covered temporary unlock
and native takeover to approved bounded tasks. Its evidence and limitations
are separate from the earlier exposed one-shot appliance unlock below.

Status: full logged-in Aqua software-testing milestone accepted for Tart,
including Java Swing and Electron;
existing-session unlock accepted on a SIP-enabled disposable Tart appliance;
fresh login, preboot, Recovery, and physical hardware remain open.

## Current state

**Current (2026-10-24), shipped in desktop 0.6.9:** the
installed signed desktop 0.6.8 reproduces the reported crash on the first
download-location `dialog.choose` in two independent fresh launches under
normal workstation approval. Both OS reports match the original HIToolbox
input-source property dispatch assertion on the native provider worker.
The original standalone appliance baseline passes, so it did not qualify the
packaged process. Keyboard-layout snapshots now copy those properties on the
main queue while panel waits and input remain on the worker. A locally signed
0.6.8-based app with the repaired embedded framework passes the same browser
workflow: 62 checks across three successful runs, sixteen download/upload
cycles, layout changes, Settings recreation and a fresh app launch, with stable
within-run PID/generation and no new OS crash report.
[Tactical 135](../docs/tactical/135-browser-file-dialog-crash.md) records the
initial evidence and qualification limits. [Tactical 137](../docs/tactical/137-desktop-0.6.9-release.md)
qualifies the exact published ARM64 package, including browser soak, recovery
faults and reviewed crash export. Physical/Intel execution remains separate.

**Current (2026-10-16):** native AX `set_value` accepts an empty string,
including independently checked editor clearing/restoration. The bounded
SecurityAgent recognizer also accepts the exact `security` requester and
System Certificate Trust Settings prompt with its unique Update Settings
button. Existing process/window/secure-field, generation and one-use lease
checks still apply; a stored-credential cleanup and independent removal check
passed on the test appliance. Resident Swift tests (215) and the isolated
`tests/smoke.sh --static` suite pass. The live smoke tail requires a disruptive
claim and was not run under the ordinary application-test claim. This does
not grant arbitrary prompt matching.

**Current (2026-10-15), unreleased source candidate:** native keyboard input
resolves character keys through the active layout and its Command mapping,
with logical modifier semantics and explicit event-state cleanup. The real
Tart resident passes U.S., Dvorak and Dvorak–QWERTY Command with default and
swapped Command/Option plus Caps→Control mappings; native fixture effects and
real Chrome for Testing shortcuts/text are covered. Terminal/readline and a
standalone Electron editor also pass all six configurations, including native
menus and independently observed text/editing effects. A separate six-cell
real SecurityAgent authorization matrix passes stored credential submission
and independently confirmed root-command effects. The secure dummy fixture
also covers both credential delivery routes through the production planner.
Broader layouts, composition input methods, login-window input, System
Settings' real session-keyboard authorization under alternate layouts and
keyboard-specific Java/additional-editor coverage remain unqualified.
[The platform report](../research/platforms/macos.md#keyboard-layouts-and-modifier-remappings)
owns the bounded evidence; [Tactical 126](../docs/tactical/126-macos-keyboard-layout-input.md)
owns implementation and repeatable acceptance. The source is deployed to the
test guest; this does not update the installed workstation app or publish a
release.

**Current:** `dialog.choose` (`desktop dialog choose --path P [--target APP]
[--no-confirm]`) chooses a location in an application's open AppKit Open or
Save panel. It navigates through the panel's own Go to Folder sheet (setting
the field through accessibility and typing it only if the value does not
take), refuses to confirm unless the panel's location shows the requested
folder, and reports a follow-up such as Replace without answering it. The
live system-dialogs suite covers folder, file, new save, unanswered Replace
and no-panel refusal on macOS 26.6 through outside and guest-local callers;
the same route loaded an unpacked extension in Chrome for Testing, saved
from sandboxed TextEdit, whose panel is hosted out of process, and added an
`.app` to System Settings' Screen Recording list. Packages such as `.app`
bundles are selected like files rather than entered as folders. Verification
is by folder display name, so two folders with the same name are not
distinguished; other macOS releases need the same suite before claiming them.

The authoritative [`platforms/macos`](../platforms/macos/README.md) now packages
a persistent ordinary-session facade inside the shared `Machine Control.app`
identity that physical hosts also run; a root-owned appliance deployment
policy gives guests standing access
([`host-control`](host-control.md)). A per-user Aqua LaunchAgent starts and keeps that signed resident
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
The System Settings inline sheet uses the guest-session keyboard stream after
foreground and secure-field focus checks. Process-targeted keys failed on that
sheet in a live Accessibility Add flow; the session route passed the same
authorization and opened the subsequent app chooser. Other accepted sheet
profiles retain process-targeted delivery.

The dedicated Tart appliance also deliberately gives its test administrator
passwordless `sudo` through the guest command channel and enabled SSH service.
That provides functional target-native package, file, service, and command
administration for the current disposable-appliance profile. It is not a claim
that the common facade yet has a bounded privileged API suitable for a personal
workstation.

## Current screen state and authorized unlock

**Current (2026-09-10):** The resident and read-only doctor now share a native
console-session observer. They distinguish locked, unlocked, no-session, and
unknown state independently of display availability, administration, TCC, and
ordinary UI readiness. Desktop transitions invalidate element references and
administrator-sheet leases. Ordinary native/Cua mutations refuse known locked
or unknown state; app-targeted input also requires successful activation and
verified focus. OS sampling and global input retain a check-to-dispatch race.
The [historical investigation](../platforms/macos/docs/lock-screen-investigation.md)
records the bugs that motivated these changes.

**Current:** `session.unlock` works through the same resident locally and
remotely on the tested SIP-enabled Tart appliance. An explicitly root-installed
Authorization Services plug-in and LaunchDaemon authenticate the resident's
kernel peer identity and pinned code hash. A bounded, single-use grant binds
to the existing console session, boot, helper epoch, and live requester.
Native input triggers loginwindow; independent OS readback establishes unlock.
No account password or per-request sudo enters this operation.

Doctor, status, and capabilities independently report installation health,
opt-in policy, actual caller eligibility, and immediate unlock readiness. A
locked target can be unlockable while ordinary desktop readiness is false.
Read-only checks never arm, wake, install, or display consent UI. An enabled
helper has its own startup readiness; ordinary desktop readiness does not
promise that the helper has finished starting.

**Current:** Discovery also exposes `lockScreen` independently of ordinary app
readiness and helper health: full-display capture preflight, limited loginwindow
AX eligibility (contents unverified), native event-posting permission, blocked
ordinary input, and the missing dedicated credential-entry API. Capture and
AX observation do not need the root unlock helper. Its explicit installation
enables policy persistently; arming happens only per unlock transaction, for a
one-use ten-second grant. Status reports this mode rather than inventing a
live armed-state observation. The follow-up projection passed native pure
fixtures and doctor/client checks; it did not repeat the earlier live VM tests.

**Decision:** This is explicit appliance authority. The callback authorizes the
next matching mechanism evaluation in a short session-wide window and cannot
authenticate the initiating agent. It is not containment against the same user
with a shell or sudo. Unlock exposes the desktop and leaves it unlocked; screen
covers, local-input blocking, and automatic relock remain deferred. The provider
continues to advertise `experimental` because OS policy/session signals are
version-sensitive, despite completed acceptance for this bounded VM profile.

[Tactical 034](../docs/tactical/034-macos-session-state-and-unlock.md) records
implementation and acceptance. The [runbook](../platforms/macos/docs/session-unlock.md)
explains installation, generation-bound requests, recovery, and removal. Root
setup and normal TCC consent remain separate. Signed local builds were tested
with SIP, authenticated-root protection, and Gatekeeper enabled; Developer ID,
notarized downloads, physical hardware, fresh login, and preboot remain open.
Headless guest-native Screen Sharing was used for consent/password-fallback
validation and disconnected during integrated unlock conformance. It is not a
runtime dependency or controller-desktop input route.

## Current maintenance and certification

**Current:** `macvm bootstrap`, `post-update audit|repair`, and
`appliance-certify` provide the retained appliance with a bounded operational
surface beside ordinary lifecycle and desktop control. Audit is read-only and
refuses a stopped target. Repair is exact-candidate only, is limited to the
checked-in resident and enumerated launchd support, and reboots only when the
caller explicitly asks. Neither path edits TCC or installs missing developer
tools.

The stable signed resident is installed as a per-user Aqua LaunchAgent with
`RunAtLoad` and `KeepAlive`; doctor only observes it. Deployment preserves an
already-current signed application when adding or repairing the LaunchAgent,
so routine migration does not needlessly change the identity to which macOS
consent is attached.

**Current (2026-08-11):** The live development-profile rehearsal reused the
retained Tart candidate without a clone or workspace. A stopped audit did not
start it. Bootstrap, common audit, and no-reboot repair were healthy.
Exact-commit certification observed a real reboot, verified the source digest,
passed portable and macOS-native guest checks in isolated state, removed
staging, and left the candidate off. The common entry point is
`machine-control --target TARGET maintenance ...`; launchd and TCC policy
remain owned here.

**Current:** [`Tactical 044`](../docs/tactical/044-macos-tart-bootstrap-stages.md)
adds a read-only Tart prepared/vanilla bootstrap stage report. A live retained
candidate had an unknown Aqua state in resident status while a direct guest
probe observed it unlocked. A guarded resident restart restored full doctor
readiness, and the report now suggests that action for this exact mismatch.
The host maintenance command bounds guest report calls so restarting Tart
transport cannot hang its caller. A fresh prepared guest reached ready doctor
after the agent used its verified, recorded public bootstrap credential for
the visible initial Accessibility sheet, granted Screen Recording through
System Settings, and restarted the resident. The one-shot outer credential
route keeps password bytes out of arguments and output. A fresh Apple IPSW
guest completed Setup Assistant, installed the guest agent and resident,
received visible Accessibility and Screen Recording grants, then reached all
stages complete, ready doctor, and a healthy development post-update audit.
The run exposed a default disk too small for Command Line Tools, a mismatched
newer SDK selected by the installed tools, scaled-window coordinate error, and
unreliable synthetic modifier keys. The [bootstrap guide](../platforms/macos/docs/bootstrap.md)
records the supported recovery and current keyboard limits.

**Current:** [`Tactical 045`](../docs/tactical/045-macos-tart-outer-keyboard.md)
first established modifier loss and added fail-closed safeguards. Its
[follow-up comparison](../platforms/macos/experiments/outer-keyboard/README.md)
proved that matching left-side device flags restore shifted text and Command
menu effects. The outer CLI now enables verified Shift/Command sequences,
including ASCII secret entry, while retaining the exact-focused-window check
and guards for untested Control/Option/Fn. The input path requires no guest
agent; acceptance used the prepared guest for independent oracles. Ordinary
post-bootstrap input stays target-resident, and the exact private VM-view
translation mechanism remains unproved.

## Resident lifetime reliability

**Current (2026-09-29):** Investigation following RSTorrent Tactical 232
reproduced one retained pipe descriptor per session probe outside a draining
autorelease pool. The unchanged resident grew about three pipe FDs per second
while idle; no capture or application operation was necessary. Reduced-limit
reproduction turned the resulting probe launch failure into unknown desktop
state. A same-guest high-FD experiment also identified the Darwin spawn
file-action ceiling at descriptor 10,240 despite a 65,536 process limit; both
probe and capture-like Foundation subprocess launch failed with EBADF. The two
historical incidents are consistent with this cause, but their removed logs
cannot establish identical causes or the exact capture failure.

**Decision:** The observer owns a pool, closes its handles explicitly, bounds
output/execution, and reaps failed/cancelled children. Idle refresh also has a
pool. Probe failure diagnostics and authorization projections stay separate
from desktop readiness; unknown state continues to refuse ordinary input.
[Tactical 047](../docs/tactical/047-macos-resident-resource-reliability.md)
owns reproduction, bounded workload/recovery validation, and remaining limits.

**Current (2026-10-01):** Resident-owned Unix listeners and client sockets are
marked close-on-exec. A regression test reproduced a plain spawned child
retaining the live resident listener and now proves that the listener does not
survive execution. Signed Tauri restart/update handoff acceptance is owned by
[Tactical 052](../docs/tactical/052-macos-production-updates.md), separately from
the session-probe lifetime workload above.

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
- Keep the accepted existing-session unlock scope in Tactical 034; retain
  fresh login, FileVault/preboot, Recovery, another user's session, and broader
  privileged APIs for less-trusted deployment profiles as later slices.
  A normal Aqua `SecurityAgent` sheet is accepted only
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
- Loginwindow credential transport beyond the accepted password-free
  existing-session unlock.
- FileVault and preboot recovery.
- Multiple displays, Spaces, minimization/occlusion, localization, and long
  soak runs beyond the first acceptance corpus.
- Whether repeated evidence justifies adopting, forking, or replacing Cua or
  deeper macOS-specific provider code.

## Native effect observation latency

**Current, bounded live-tested:** [Tactical 088](../docs/tactical/088-targeted-native-effect-observation.md)
limits AX window fingerprints to the actual affected app and excludes the
resident's own main-thread AX queries. A signed GUI trial exposed roughly
five-second actions that consumed the finite owner watchdog; the deadline
remains unchanged. Source/static/deployment checks and the immutable signed
native regression pass: 1.259-second AX effect, real capture bytes, independent
pointer/key/activation effects and Pause refusal. Independent fixture counters
remain the effect oracle. Protected/hardware and sustained-load qualification
remain separate.

# Tactical 010: macOS Full Aqua Software Testing

Status: complete with declared appliance omissions.

Topics: `macos-resident-control`, `inner-first-routing`, and
`capabilities-and-results`.

Research:
[`macOS platform report`](../../research/platforms/macos.md).

Authoritative testbed:
[`platforms/macos`](../../platforms/macos/README.md).

## Objective

Make a prepared, continuously logged-in Tart macOS appliance fully operable for
software testing through mechanisms executing inside its Aqua session and
target OS. After the controller's one-time Accessibility and Screen Recording
bootstrap, an agent must be able to observe software, drive semantic or visual
UI, respond to relevant consent and authorization surfaces, administer the
test appliance, verify effects, and recover from ordinary application failures
without Tart-window capture or input.

The same surface must work for an agent in the guest and an authorized agent
outside it. `tart exec` may transport a request to the resident; it must not
turn the Tart graphical window into the ordinary controller.

## Completion conditions

- Every mutation uses a guarded copy-on-write candidate. Prepared sources stay
  protected, and the accepted candidate is stopped normally at completion.
- The acceptance harness has a fail-closed mode that rejects Tart-window
  screenshot, click, drag, type, and key operations. Every accepted workflow
  runs under that mode and reports `hostInterference: none`.
- The resident supplies compact semantic observation/actions where AX is
  useful, plus full-display and exact-window capture and coordinate keyboard
  and pointer input produced inside the guest. The visual fallback does not
  focus Tart, move the host pointer, or type through the host session.
- A deterministic permission corpus triggers every software-testing privacy
  class practicable in Tart, including Accessibility, Screen Recording,
  Automation, Input Monitoring or event access, protected user folders, Full
  Disk Access, Local Network, notifications, camera, and microphone. Each
  surface records whether Tart lacks the corresponding virtual hardware
  separately from whether its consent UI is controllable.
- Every permission surface in the accepted corpus supports explicit Allow and
  Deny workflows, independent application-effect verification, supported
  reset, and a second prompt or state observation. The controller never edits
  or transplants a TCC database.
- The resident operates relevant System Settings panes and common software
  surfaces: native open/save/folder panels, menus and menu extras,
  notifications, browser downloads, disk images, harmless package installers,
  quarantine/Gatekeeper dialogs, restart/relaunch requests, and nested modal
  sheets. Results distinguish input delivery from the intended effect.
- Representative semantic and sparse/custom UI paths are exercised across
  available AppKit, SwiftUI, Electron, browser/web, Java, and custom-rendered
  applications. Sparse semantics select the target-local visual fallback, not
  an outer provider.
- Normal administrator prompts use the accepted generation-bound one-shot
  credential path. Non-UI administration uses the appliance's declared
  passwordless root shell. Secrets never enter ordinary request JSON,
  arguments, environment, files, captures, logs, results, or repository state.
- Guest-local and outside callers exercise the same facade, provider selection,
  references, artifacts, authorization behavior, and result vocabulary.
- No relevant prompt encountered in the accepted workflows remains dependent
  on host/hypervisor UI. A macOS-protected surface needs a target-resident or
  supported policy solution before acceptance; it cannot silently fall back.
- Resident restart and full guest reboot restore the logged-in Aqua testing
  surface. Fixtures, permission state owned by the corpus, applications,
  mounts, downloads, packages, captures, logs, and temporary artifacts are
  removed or restored to their declared baseline.

## Current appliance assumptions

- One explicit initial bootstrap has already granted the stable resident
  Accessibility and Screen Recording access. Reproducing fresh Setup Assistant
  or granting a controller permission before it can control UI is not part of
  this tactical.
- The dedicated appliance remains logged in and does not intentionally enter
  lock screen, loginwindow, sleep, or another user's session during testing.
- The appliance deliberately permits passwordless `sudo` through its command
  channel and enabled SSH service. This is an honest strong test-appliance
  profile, not a containment boundary against an agent that already has shell.
- Camera, microphone, Bluetooth, removable-media, or other physical effects
  may be unavailable in Tart. The corpus still tests any prompt and consent
  state the OS can expose, while reporting absent virtual hardware honestly.

## Boundaries

- Lock/loginwindow, FileVault/preboot, Recovery, firmware, power-loss recovery,
  multiple interactive users, and physical Mac control are deferred until real
  hardware or those planes become an active testing need.
- Tart lifecycle, `tart exec`, and independent health diagnosis remain allowed.
  Only host-side manipulation of the guest's graphical surface is prohibited
  during acceptance.
- Do not weaken SIP, Gatekeeper, TCC, secure input, code-signing, Authorization
  Services, or application sandboxing. Use supported consent, reset, policy,
  application lifecycle, and administration paths.
- Do not pre-approve every application under test. Permission Allow or Deny is
  an explicit test action whose resulting application behavior must be
  observable and repeatable.
- Do not treat a successful click, key event, accessibility action, permission
  API call, or package command as proof of effect. Use fixture state, process
  state, files, APIs, semantic readback, or another independent oracle.
- Do not turn absence of virtual camera, microphone, removable media, or other
  Tart hardware into a false UI-control failure. Keep permission decision,
  prompt control, and hardware effect separate.
- Do not add fleet MDM, a general-purpose root broker, login credential
  transport, or physical recovery merely for architectural completeness. Add a
  target-resident component only when a live accepted Aqua workflow requires
  it.

## Implementation steps

### 1 — make outer UI impossible during acceptance

Add an explicit testbed guard that refuses host-side screenshot and input
commands while allowing lifecycle and guest-agent transport. Instrument the
conformance run so any attempted outer UI route is visible and fatal. Establish
a clean logged-in baseline and inventory the current resident capabilities,
sudo posture, TCC readiness, display coordinate spaces, and host focus/cursor
state.

### 2 — complete the in-guest universal fallback

Expose full-display capture and target-local coordinate pointer, keyboard, and
text operations through the facade alongside exact-window capture and AX.
Bind coordinates to explicit display/window spaces, report actual routes, and
prove the fallback on a deliberately sparse or custom-rendered fixture while
the host desktop remains unchanged.

### 3 — build the privacy and consent fixture corpus

Create minimal signed fixtures with independent state for each relevant TCC or
privacy class. Trigger one prompt at a time, inventory its actual process,
window, semantics, capture visibility, buttons, and restart requirements, and
then implement explicit Allow and Deny paths. Use supported reset facilities to
replay decisions; never edit TCC storage. Record prompt control separately from
hardware availability and application effect.

### 4 — exercise system and application approval surfaces

Build harmless deterministic workflows for open/save/folder panels,
notifications, downloads, mounted disk images, package installation,
quarantine/Gatekeeper, application relaunch, System Settings changes, menu-bar
items, and nested sheets. Reuse the administrator lease where a normal
`SecurityAgent` prompt appears and use passwordless shell administration for
non-UI setup and cleanup.

### 5 — prove representative software coverage

Run sustained workflows across available AppKit, SwiftUI, Electron, web,
Java, and custom-rendered software. Prefer compact semantics, select the
in-guest visual fallback when needed, and record latency, observation size,
agent round trips, fallback choice, delivery, effect, and uncertainty. Exercise
the same workflows through guest-local and outside placements.

### 6 — prove recovery, isolation, and cleanup

Restart providers and the resident, reboot the guest, verify automatic return
to the ready logged-in Aqua surface, and repeat representative permission,
system-dialog, semantic, and visual-fallback workflows. Prove there was no
outer UI invocation or host focus/cursor interference. Reset corpus-owned
consent state, remove every fixture and artifact, stop the candidate normally,
and verify clean repositories and protected sources.

### 7 — publish the accepted surface

Update the macOS topic, platform research, capability/result vocabulary,
testbed runbook, root entry point, and this execution record with the exact
surface matrix. Distinguish accepted target-native paths, hardware omissions,
macOS-enforced gaps, and explicitly deferred physical or non-Aqua planes.

## Validation record

Completed on a guarded copy-on-write Tart candidate. Every acceptance script
set `MACVM_FORBID_OUTER_UI=true`; host screenshot and input commands therefore
failed closed while guest shell transport, resident control, and lifecycle
remained available. Each accepted result reported `hostInterference: none`,
and the host cursor/frontmost-application oracle was unchanged.

The completed corpus proved:

- remote and guest-local parity through one resident generation for compact AX
  semantics, exact-window capture, full-display capture, keyboard, pointer,
  text, application lifecycle, artifacts, and truthful provider selection;
- target-local visual fallback on a deliberately custom-rendered AppKit surface,
  including move, click, drag, and scroll with an independent file oracle;
- Camera, Microphone, Automation, Accessibility, Input Monitoring, Screen
  Recording, Local Network, notifications, protected-folder, and Full Disk
  Access policy surfaces through supported prompts or System Settings, with
  allow/deny or grant/revoke, supported reset, and independent API/file effects;
- native Open, Save, folder-selection, nested-sheet, relaunch, notification,
  Safari-download, mounted-DMG, Gatekeeper, and harmless Installer workflows;
- strict one-shot authorization for ordinary SecurityAgent, Installer,
  System Settings, and Gatekeeper's exact LocalAuthentication sheet, with the
  credential confined to the non-echoing staged channel;
- compact AppKit and SwiftUI semantic workflows from both placements. A
  representative post-reboot run returned roughly 1 KB observations at
  40–122 ms while independent state files proved the effects;
- a normal full guest shutdown and unattended bring-up into the logged-in Aqua
  session, retained Accessibility/Screen Recording readiness, resident restart,
  stale-reference invalidation, and successful post-reboot semantic, visual,
  privacy, dialog, and framework cells; and
- reset/removal of corpus-owned TCC state where supported, all fixture apps and
  sources, mounts, downloads, package payload and receipt, capture artifacts,
  caches, and file oracles before a final normal shutdown.

During execution, Tart system-key capture was found to be able to retain host
keyboard focus beyond the expected window interaction. The testbed now defaults
it off, acceptance mode suppresses the flag even when local configuration asks
for it, and post-reboot process inspection confirmed the flag was absent.

Declared appliance omissions are not acceptance failures:

- the prepared image has SIP disabled, so Full Disk Access and protected-folder
  UI grant/revoke is controllable but protected-read enforcement is unavailable;
- Tart exposes no camera or microphone hardware, although both consent decisions
  and the separate no-hardware application effect are repeatable; and
- the image has Swift/AppKit and Safari but no usable Java or Electron build
  runtime. The framework corpus fails if either runtime later becomes available
  without gaining a deterministic fixture.

The Java/Electron omission above describes this tactical's execution-time
image. It was subsequently closed by
[`Tactical 011`](011-macos-java-electron-framework-coverage.md) with pinned
runtimes, deterministic fixtures, and pre/post-reboot acceptance. The SIP and
virtual-hardware limitations remain.

Lock/loginwindow, FileVault/preboot, Recovery, physical Mac hardware, multiple
interactive users, and physical-device peripherals remain outside this
tactical's explicit boundary. Continuing macOS direction is maintained in the
[`macOS resident-control topic`](../../topics/macos-resident-control.md).

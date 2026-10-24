# macOS conformance

`browser-file-dialogs.py --source-root STAGED_SOURCE --claim CLAIM --repeat 5`
runs inside an already claimed, unlocked VirtualMac with standing appliance
authority. Stage this runner, `providers/chrome-extension` and
`platforms/chromeos/cdp.py`; it uses the existing Chrome for Testing fixture
under `~/mc-cft/chrome-mac-arm64`. It refuses a different browser identity and
uses an isolated disposable profile. Extension clicks/Unicode text/capture,
real HTTP downloads, native Save and upload Open panels, cancellation,
unanswered Replace, Save Page As and missing-panel refusal are checked against
file bytes and HTTP effects. Every response must retain the same resident
generation; final PID and OS crash-report inventory must also remain unchanged.
The caller owns deployment, doctor, claim renewal/release and power restoration.
The runner reaps its browser process group before removing its profile and
stops its fixture server on failure as well as success. No outer UI is used.
The default mode qualifies a bounded source-native Mac route, not signed installed
acceptance, other platforms or sustained crash resistance.

For the installed Tauri app, add `--expected-policy approval --observer-socket
OBSERVER_SOCKET`. The candidate must occupy the canonical resident socket and
the observer must be a separate, already authorized standing appliance process.
This mode presses the actual native approval, uses the candidate's bundled
extension/native host, and records the embedded framework digest. Add
`--keyboard-environment GUEST_HELPER` (built from the existing keyboard fixture's
`environment.swift`) to cycle already-enabled U.S./Dvorak/hybrid sources before
panel choices; the initial source is restored. Add `--settings-cycle` to
recreate and close the real Settings WebView between download/upload cycles.
The runner waits read-only for the normal activity-guard quiet window, logging
closed blocking reasons; it never disables or resumes that guard. A closed
resident connection reports unknown outcome and forbids replay.
The caller must back up and restore the original installed app, trusted root
policy, LaunchAgent, operator files and preferences before replacing an
appliance installation with a workstation candidate. Follow the existing
runtime-presentation setup/restoration boundary below. Never use this procedure
on a personal workstation. [Tactical 135](../../docs/tactical/135-browser-file-dialog-crash.md)
records released-app crashes and the locally signed embedded-framework fix.

[`../browser/locked-macos-live.py`](../browser/locked-macos-live.py) is a
guest-only browser feasibility probe. Stage it, the owned extension directory,
and `platforms/chromeos/cdp.py` in the guest; supply `--source-root`, the current
exclusive `--claim`, a private `--output` directory, and explicit `--lock`.
It requires the existing standing appliance observer and Chrome for Testing at
the fixture location, an unlocked console and disabled covered unlock. It
checks independent HTTP effects and IOKit lock state, reaps its test browser
and deletes its disposable profile. It deliberately leaves the guest locked;
the caller owns authorized unlock or shutdown, staging/evidence cleanup, and
claim release.

For source-native workstation acceptance, first use
`build-browser-locked-fixture.py --output PRIVATE_BUILD --socket
/tmp/browser-lock-fixture/session/control.sock --preferences-suite
org.machine-control.browser-lock-fixture.preferences`. Stage that app in the
guest and pass its path as `--workstation-app`. The fixture starts with no
grant, enables the preference through its in-process local operator, and uses
real native approval pressed through the independent appliance. It checks
mixed-grant retention, desktop/new-scope refusals, browser-only admission,
Pause/Resume and disabling. Its operator input cannot answer approval.
Use `--appliance-identity` only in a source-native VM whose ordinary resident
already uses the same ad-hoc requirement; it reuses that existing TCC consent.
Otherwise grant the fixture its normal OS permissions first. This qualifies
source-native authorization, not the signed installed Settings UI.

`keyboard-layouts.py --target macos --claim CLAIM [--install-profile]` runs
keyboard acceptance in an already running, healthy, exclusively claimed Tart
VM. It switches U.S., Dvorak and Dvorak–QWERTY Command with default and swapped
Command/Option plus Caps→Control mappings, without restarting the real resident.
AppKit menu/text and WebKit events are independent effect oracles; a fixed
public dummy exercises the shared production credential planner/emitter in a
secure field through both delivery routes. It never opens a real authentication
sheet or requests a real secret. Settings are restored and the unique fixture
is removed in cleanup. `--install-profile` persists the alternate Dvorak setup
after success. Add `--browser-smoke` for real Chrome for Testing address-bar,
text, clipboard and new/close-tab effects under Dvorak/remapped modifiers. It
requires the existing separate test-browser fixture and uses an isolated
profile with mock-keychain flags.

Add `--apps-smoke` for Terminal/readline and a standalone Electron editor in
all six configurations, or `--apps-only` to run that matrix separately. Install
the [pinned framework runtime](../../platforms/macos/docs/ui-automation.md#resident-requests)
first; the runner checks the Electron version against the repository manifest.
Terminal checks exact PTY lines after Control/Option editing and new/close-tab
shortcuts. Typed bytes go to `read -e`, never a shell evaluator. Electron checks
exact Unicode text, clipboard/undo and native Save/Find menu accelerators with
independent file state. Each app uses an owned process and scratch files;
cleanup restores input settings and reaps both apps. This qualifies the fixture,
not every Electron editor or terminal configuration.

The caller owns VM lifecycle, claim renewal/release, and any recovery. Outer UI
is prohibited throughout this runner. Passive host samples
report equality or an unattributed change; use `--require-host-unchanged` only
when deliberately keeping the controller quiet. See
[Tactical 126](../../docs/tactical/126-macos-keyboard-layout-input.md).

`keyboard-authorization.py --target macos --claim CLAIM` separately tests real
SecurityAgent administrator authorization in all six keyboard configurations.
The canonical `guest-login-password` entry must be ready in private inventory
(`--credential-testbed` selects that entry's testbed, default `macvm`). The
runner requires an absent admin fixture, deploys the existing fixture, refuses
a wrong requester, and submits once through `authorization-submit --stored`.
Every cell requires dialog dismissal and the same request's independent
`authorized`/root-command completion oracle, then checks single-use refusal
and clean modifier state. Any failed or uncertain submission stops the matrix;
there are no incorrect-password tests or automatic credential retries. Cleanup
removes the owned fixture and restores the full input profile. The caller owns
VM power and claim cleanup. This qualifies the ordinary SecurityAgent profile;
System Settings inline sheets, loginwindow and unlock remain separate routes.

`locked-use-live.py` exercises an explicitly installed and enabled covered
workstation candidate under an existing claim and ordinary native approval.
It checks covered capture plus an independent fixture effect, then one chosen
completion, expiry, disconnect, resident stall/crash, or guardian crash cell.
Supply guest `--executable` and `--socket` for an isolated candidate. Each cell
leaves the VM locked; the caller owns native setup, manual unlock, policy/power
restoration, and claim release. It never reads a password or installs on the
controller. Physical takeover and visible cover inspection are separate
explicitly authorized tests. See the [locked-use guide](../../platforms/macos/docs/locked-use.md).

For explicitly requested physical-Mac acceptance, use `--local --target host`
with `--registry` when needed and `--session-probe` pointing to the candidate's
bundled `mc-session-probe`. Launch the native fixture locally first. This mode
reads its local file oracle, checks AX, pointer, and keyboard effects, fetches
capture through the common artifact interface, and verifies relock with the
independent native probe. Native setup, access approval, and manual unlock
belong to the person at the Mac. `--case physical_presence` waits for their
hardware takeover after printing its readiness message.
Use `--manual-lock` to wait for a normal operator lock instead of assuming a
synthetic shortcut will lock the physical Mac. An ended session reports its
termination reason immediately while waiting for covered activation.
Alternatively compile `session-lock.m` with Foundation and IOKit and pass its
executable as `--session-lock` in local mode. This explicit runner uses the
watchdog's native lock primitive, binds the current user's console, and verifies
lock through IOKit; it does not authorize or perform unlock. It requires the
literal `--lock` argument when invoked outside the live runner.
Process-failure cells remain dedicated-testbed only. Physical qualification requires observed live
results; availability of this runner is not acceptance evidence.

The runner requires exactly one native fixture and ties its semantic PID to the
independent file oracle. For successive unattended-task acceptance, use
`--start-locked` without a starting lock action and `--expect-retained-access`
on completion or lease-expiry cells. The latter checks that the original grant
ID survives clean relock; neither option creates approval or clears a failure
pause.

`tauri-desktop.py` exercises an already installed signed Tauri candidate in a
claimed dedicated testbed. Supply the logical target, current exclusive claim,
guest candidate app path, and socket. Keep the standing appliance resident
running separately, deploy and launch the AppKit fixture first, and give the
candidate workstation policy. The test uses native AX input to approve and
deny; no socket or test-only bypass approves access. Installation, consent,
signed replacement, power restoration, and claim release belong to the caller.
Do not run it on a personal workstation.

`--candidate-client` routes candidate operations through the packaged Python
CLI and acquires/releases a separate guest-local host claim. It also exercises
the ergonomic capture/artifact commands and independently checks PNG bytes.
The controller's VM claim remains distinct. Start the fixture before running.
Use `--control-only` for the bounded approval/action/artifact slice; the default
still exercises tray navigation and production update discovery separately.

When the candidate occupies the canonical installation, supply a separate
source-native appliance with `--operator-app` and `--operator-socket`.

`tauri-update.py` uses that same separate observer to check production update
discovery, disabled installation during active access, explicit Stop, signed
replacement, relaunch, permission readiness, access revocation, and stale
reference refusal. Supply the authenticated sender and expected release
versions. `--verify-restart-before` and `--verify-restart-after` also exercise
the Permissions Restart button. `--legacy-reopen` permits one native reopen
for published 0.3.3/0.3.4 senders and reports it separately from automatic
relaunch. The caller owns installation, fixture setup, and restoration.

The macOS corpus drives the target-resident facade owned by
`platforms/macos`. `conformance.sh` runs the same request vocabulary
through two placements:

- `remote`: the host wrapper sends a request through `tart exec`; and
- `local`: `tart exec` launches the installed guest-local client, which calls
  the same private resident socket.

The deterministic AppKit fixture supplies both visible AX state and a separate
file oracle. Tests do not treat an AX or input acknowledgement as proof of an
application effect. The script also checks exact-window artifacts, resident
restart, stale-reference refusal, and System Settings background behavior.
`aqua-visual-fallback.sh` runs with Tart-window pixels and input forbidden. It
checks target-local full-display capture at Retina scale and move, click, drag,
and scroll on a deliberately sparse custom AppKit surface. Its file oracle
proves guest effects, while an independent read-only host oracle proves the
host cursor and frontmost application did not change. Both outside and
guest-local callers exercise the same resident.
`privacy-consent.sh` uses a signed fixture and file oracle to reset and replay
Camera, Microphone, and Automation prompts. Each class proves both Don't Allow
and Allow through native system-dialog semantics, distinguishes policy from
Tart's missing camera/microphone hardware, and alternates outside and
guest-local calls without host interference.
`privacy-settings.sh` covers settings-managed Accessibility, Input Monitoring,
and Screen Recording grants and revocation. It drives the Privacy & Security
pane, proves a real event tap and ScreenCaptureKit enumeration after the
relevant grants, and uses the resident's bounded one-shot credential lease only
when macOS presents the strict inline administrator window. The credential
cases are interactive and never put the secret in request JSON, arguments,
environment, files, logs, captures, or results.
`privacy-appliance-posture.sh` records the prepared image's relevant omission:
SIP is disabled, and direct Documents, Downloads, and protected-data fixture
reads are not refused after supported TCC resets. It treats that as unavailable
enforcement rather than a successful Full Disk Access decision.
`system-dialogs.sh` drives deterministic Open, folder-selection, and Save
panels, a nested application sheet, and an application relaunch request. It
alternates outside and guest-local callers and verifies files and fixture state
independently.
`artifact-workflows.sh` builds disposable guest artifacts and proves a
quarantined-app Open Anyway flow, DMG mounting with Finder semantics, a Safari
download approval, and a harmless Installer package. Exact Gatekeeper and
Installer credential sheets use strict resident authorization leases when
macOS presents them, so the script requires an interactive terminal. It
removes the mount, download, package receipt/payload, server, and working
directory afterward.
`framework-coverage.sh` requires the checksum-pinned runtime set and proves
compact semantic actions, independent effects, and exact-window capture
through both caller placements on deterministic AppKit, SwiftUI, Java Swing,
and Electron fixtures. Native AX drives AppKit, SwiftUI, and Swing. The
Electron cell explicitly activates the guest application and uses Cua's
semantic route because live differential evidence found native AX acknowledged
the Chromium button without producing its independent effect. The Cua target
cache is polled boundedly after activation; an empty tree never passes. The
script links the already separate browser/web and custom-rendered acceptance
cells and records observation size and latency.
`real-applications.sh` sustains the same facade across Finder, System Settings,
TextEdit, Safari, an application menu bar, exact-window artifacts, focus
preservation, and owned-state cleanup.
`provider-comparison.sh` runs identical compact snapshot, action, independent
fixture-effect, and exact-window capture cells through native macOS and Cua
routes. It then proves native Dock and Control Center reach while requiring
any Cua gap to fail closed without fallback.
`administrator-sheet.sh` proves that a normal Aqua administrator sheet can be
identified, cancelled, and submitted entirely inside the guest. It exercises
wrong-requester, cancellation, expiry, changed-sheet, resident-restart,
incorrect-credential, correct-credential, reboot-recovery, and cleanup cases.
The two credential cases are interactive by design: the secret is read without
echo by the testbed's one-shot helper and never enters request JSON or this
repository.

Run it from this repository after selecting a guarded disposable/candidate VM
in the testbed's ignored local configuration:

```bash
tests/macos/conformance.sh
tests/macos/conformance.sh remote
tests/macos/conformance.sh local
tests/macos/aqua-visual-fallback.sh
tests/macos/privacy-consent.sh
tests/macos/privacy-settings.sh
tests/macos/privacy-appliance-posture.sh
tests/macos/system-dialogs.sh
tests/macos/artifact-workflows.sh
tests/macos/framework-coverage.sh
tests/macos/real-applications.sh
tests/macos/provider-comparison.sh
tests/macos/administrator-sheet.sh
tests/macos/administrator-sheet.sh session
```

No target name, guest account, network endpoint, or captured artifact is
written into this repository.

## Existing-session unlock

`session-unlock.py --target macos --claim "$claim_id" [--registry FILE]` runs
local and remote lock/unlock cycles against an explicitly installed disposable
appliance. It requires SIP, active input/capture consent, the native counter
fixture, and outer UI prohibited. It checks locked doctor/input refusal, stale
generations/references, duplicate requests, no-op behavior, and independent
post-unlock fixture effects. It leaves the session unlocked and does not install
a provider or enter credentials. The caller owns claim and appliance cleanup.

`doctor-state.py` verifies current/legacy, stopped-resident, and powered-off
projection through the actual doctor script using isolated fixtures.
`lock-screen-projection.py` compiles the resident's pure projection and checks
consent, inactive display, unknown session, and ordinary-input separation.
`session-observation.m` tests the pure observer parser without touching a
desktop. `unlock-grants.m` is a root-only disposable-guest fixture: it uses a
separate fixed state directory and refuses a preexisting one. It validates
malformed/stale grants and concurrent one-use consumption while OS state stays
locked. `unlock-broker-client.m` exercises actual IPC denial and, only after
explicit privileged fixture setup, disconnect/timeout revocation. These native
fixtures do not authorize use of the controller desktop. See
[Tactical 034](../../docs/tactical/034-macos-session-state-and-unlock.md) and the
[runbook](../../platforms/macos/docs/session-unlock.md) for scope and evidence.

## Resident resource reliability

`session-probe-resources.py` compiles the production session observer with a
synthetic probe and a 128-FD limit. It needs no UI consent and never queries a
desktop. Always-on Swift preconditions check repeated completion, launch and
parse errors, bounded output, timeout, cancellation, recovery, FD counts, and
child reaping. `--idle-only --source FILE` accepts the old no-argument observer
for a before/after reproduction; `--caller-pool` isolates the missing pool.
The opt-in `--spawn-boundary` diagnostic retains at most 12,000 pipe readers
in an isolated process and checks the actual Darwin spawn boundary separately
from configured FD limits. It requires already sufficient limits and is not
part of the ordinary native check suite.
`maintenance-projection.py` checks the actual audit's consent/readiness
projection. Both run in the native static suite.

`resident-resources.py` is an explicit **guest-local** live runner. The caller
must first doctor, claim, ensure readiness, deploy and launch a previously
absent AppKit fixture, and arrange fixture/power/claim cleanup. Invoke it through
common `os -- /usr/bin/python3 -c "$(cat tests/macos/resident-resources.py)"`.
It isolates operation families before a combined workload, checks independent
fixture effects, and reports numeric FDs/types, non-FD lsof entries, RSS,
threads, children, test request counts, latency, and readiness. It captures
only the fixture and deletes every owned artifact. It does not measure opaque
framework queues or claim that sampled RSS is a strict memory bound.

`resident-recovery.py --evidence-dir PRIVATE_DIRECTORY` runs on the controller
under the same claimed task. It refuses an inherited fixture, owns its setup
and removal, tests common capture/artifact round trips, temporarily removes
execute permission from the deployed session probe with `finally` restoration,
and verifies unknown-state refusal while an independent probe sees unlocked.
It then uses supported resident stop, maintenance audit/repair, and fresh AX
effects to check recovery and stale references. This is a deliberate fault
injection for a dedicated test appliance, not a personal-workstation command.
The caller owns initial power-state restoration and claim release.

[Tactical 047](../../docs/tactical/047-macos-resident-resource-reliability.md)
contains replay commands, measurements, and the limits of historical attribution.

## Native sudo acceptance

[Native sudo](../../platforms/macos/sudo/README.md) documents the signed fixture
builder and claimed dedicated-appliance conformance runner. It uses real sudo
and a native AX secure-field driver, with temporary exact-command password
policy and canonical secret transport. Never run the driver on a workstation.

`tests/browser/indicators-live.py --client INSTALLED_COMMAND` exercises browser
operations through the installed CLI instead of direct socket calls, including
browser PNG capture and artifact retrieval. Its dedicated Chrome for Testing
profile, native host/extension, independent HTTP/CDP oracles and process cleanup
remain the same. The caller owns guest-local and controller claims, native
approval, canonical native-host socket selection and restoration.

## Caller identity experiment

[caller-authorization/README.md](caller-authorization/README.md) describes a
standalone native Unix-socket gate with audit-token and strict code-identity
checks. It uses temporary signed fixtures and installed YA's Bun to compare
specific executable trust with overly broad publisher trust. It performs no
desktop actions and does not exercise production grants or session delegation.

## Signed native desktop delegation

[Native delegation acceptance](native-delegation/README.md) runs the actual
signed YA/native CLI/signed MC operator path in an exclusively claimed Mac
appliance. It proves independent AX effects, native trust enrollment,
Pause/fresh Resume, Stop and unrelated-process refusal using an owned protocol
provider. It does not run an LLM or qualify covered/hardware/distribution use.


`runtime-presentation.py` qualifies one presentation profile on an installed
signed workstation candidate in a claimed dedicated VM. Supply the app,
socket, packaged CLI, profile and optional separate standing observer. It
starts/terminates its candidate, asserts healthy trusted-policy-file loading
at startup and restart, uses native AX approval without bypasses, and checks
actual Settings WebView count and same-runtime recovery, deferred mode
changes, live reset, local/outside independent effects, capture bytes, native
notice, Pause/Resume, Stop, signed restart, native keyboard/pointer effects,
stale references and update discovery with installation disabled during access. It never installs the discovered
production update over the candidate.
Optional `--browser-suite` and `--browser-chrome` run the existing headed
browser corpus with Settings absent. The suite root contains the browser runner,
owned extension and ChromeOS CDP client. Use a separately identified Chrome for
Testing; the candidate must occupy the canonical native-host socket and the
standing observer must use a separate endpoint. Save and restore existing
canonical operator preferences and the observer's launch registration.
`--verify-temporary-restart` also proves one-launch override expiry against the
saved preference. `--standing-policy` selects a bounded appliance-policy trial
for independent effects, Stop/Resume, stale references and personal recovery;
it preserves the separately provisioned standing policy.
The caller owns signed installation, TCC consent, temporary policy restoration,
fixture lifecycle, target power and claim cleanup. Do not use on a personal Mac.

For an additional OS reboot/cold-boot trial, use persistent guest staging and
keep controller-side copies of every file needed for restoration. macOS clears
`/tmp` at startup; neither an app nor its backups there can survive that test.
The runner's Restart checks restart the app, not the operating system.

`runtime-host-load.py --app CANDIDATE --claim CLAIM --evidence-dir PRIVATE_DIR`
is a bounded physical-host discovery/recovery check. The caller first runs
host doctor, acquires a fresh exclusive host claim and supplies `--registry`
when needed, then releases the claim in cleanup. The runner verifies signatures,
launches an isolated endpoint with saved appliance/temporary minimal presentation,
opens Settings during 96 attempted incomplete handshakes, then performs
concurrent read-only discovery for 30–300 seconds. It checks same-runtime
recovery, main-thread samples, sampled FD/RSS recovery, no candidate access
grant, unchanged canonical app/helper/policy/presentation fingerprints and the
installed resident PID. It terminates its candidate and restores focus.
Raw process samples/logs remain private. This is neither a strict memory bound
nor native-effect/protected-session acceptance. Deterministic Swift fixtures
separately inject blocked helper/session/provider/Resume dependencies and
slow-reader reply floods without changing the real helper or session.

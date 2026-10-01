# macOS conformance

`tauri-desktop.py` exercises an already installed signed Tauri candidate in a
claimed dedicated testbed. Supply the logical target, current exclusive claim,
guest candidate app path, and socket. Keep the standing appliance resident
running separately, deploy and launch the AppKit fixture first, and give the
candidate workstation policy. The test uses native AX input to approve and
deny; no socket or test-only bypass approves access. Installation, consent,
signed replacement, power restoration, and claim release belong to the caller.
Do not run it on a personal workstation.
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

# macOS covered locked use

Owning topics: [macOS locked use](../../topics/macos-locked-use.md),
[host control](../../topics/host-control.md), and
[macOS resident control](../../topics/macos-resident-control.md).

Status: complete.

## Objective

Implement the requested first Mac version with the documented Codex/ChatGPT
locked-use experience, excluding closed-lid support. A persistent opt-in enables
approved work after normal screen lock, while all displays remain covered and
physical input returns priority to the person.

## Completion conditions

1. Off by default; native operator toggle installs/enables the helper with
   administrator authentication. Cancel/failure leaves the setting off.
2. The setting alone never grants desktop access. An approved bounded session
   owns temporary unlock, and expired/revoked grants cannot rearm it.
3. Every display is covered before unlock. Native agent display capture
   excludes the covers; desktop semantics/input still reach the application.
4. Hardware keyboard/pointer activity blocks local input, relocks, revokes
   access, and prevents automatic unlock until manual unlock is observed.
5. Completion, disconnect, Stop, expiry, sleep/display/session transitions,
   disabling, and resident failure relock; cover teardown requires observed
   lock. An independent watchdog handles a stalled/dead resident.
6. Local tests and claimed VM tests independently verify lock, cover, capture,
   application effects, takeover, refusal, and cleanup. Record untested cells
   honestly. No controller-host lock or privileged installation.

## Boundaries

Awake, open-lid, existing-session macOS only. No password persistence, TCC
database edits, weakened authentication, arbitrary root dispatch, publication,
or physical-host acceptance implied by VM evidence. The user explicitly
authorized outer VM Computer Use if necessary; prefer deterministic inner
interfaces and acquire a disruptive claim before outer input.

## Ordered work

### 1 — define the setting and active control session

Add native operator state and setting, a bounded connection-owned session with
explicit completion and liveness heartbeats, and capability/refusal reporting. Preserve default
lock revocation when locked use is off.

### 2 — install protected authority and failure relock

Package signed helper/plug-in/installer payloads. Extend the typed broker with
an authenticated covered-session watchdog, short unlock grants, cancellation,
and profile separation. Setup uses native administrator authentication.

### 3 — cover displays and preserve native control

Install nonactivating opaque windows before unlock, exclude them from native
display capture, and add an independent hardware event guard. Relock before
removing covers; refuse uncertain state and unsupported provider routes.

### 4 — prove the experience on the VM

Run Swift tests and desktop checks/builds; use read-only doctor, an exclusive
claim, canonical credential lookup, and the supported deployment workflow.
Exercise visible operator setup and independent application/lock effects.
Use outer input only for authorized hardware takeover/recovery evidence.
Restore target policy/preferences and release claims in cleanup.

### 5 — reconcile documentation and results

Update topic, platform report, runbook, desktop guide, and this execution record
with current behavior and explicit evidence/remaining gaps.

## Validation

State-machine tests cover default-off, approval requirements, expiry,
disconnect, replay/stale ownership, takeover latch, and lock-before-uncover.
Broker tests cover profile isolation and watchdog fail-closed behavior.
Live acceptance uses independent OS lock observations, fixture file effects,
outside-vs-agent capture, and physical-origin input when available.

## Final result

Implementation and bounded VM acceptance are complete in source. Original
target policy/helper/power state was restored and the exclusive claim released. The default-off Settings toggle installs the
profile through native sudo and preflights capture while unlocked. Local
revocation is immediate and does not prompt again; full administrator uninstall
restores the saved screensaver policy. No account password is persisted.

The resident implements `session.control` and exact-ID `session.control.end`,
checks ordinary observe/control approval, caps the task by access expiry and a
finite 1–900-second deadline, and requires owner heartbeats. The same executable
runs a separately authenticated cover/input companion. Clean completion is
handed to that companion before relock; the resident retains a five-second
failure fallback, avoiding a false unexpected-end pause. The root broker has an
independent maximum deadline and heartbeat watchdog plus a durable pre-unlock
restart marker. Root and resident profiles reject exposed appliance unlock
and generic privileged JSON dispatch. Sleep/lid/display/console changes terminate
rather than retarget. Covers survive a stalled or killed resident until OS lock
readback; replacement invalidates the old console scope.

### Validation results

| Cell | Evidence/result |
| --- | --- |
| Local Swift authorization/lease/socket/state tests | 58 passed, including host-lock-independent approval, authority/session replacement, expiry, heartbeat, physical latch, and invalid duration |
| Common Python client suite | 153 passed, including bounded CLI parsing and a real Unix socket owner/heartbeat/final-result test |
| Release/package suite | 61 passed |
| Mac static smoke and resource conformance | Passed, including 500 native observation success/error/deadline/cancellation/reaping samples |
| Packaging | ARM64 Tauri app build and deep strict signature verification passed; Intel helper build and resident typecheck passed |
| VM posture | macOS 26.6.2, SIP disabled in the existing appliance; no SIP/TCC database or credential-policy weakening performed |
| Default off and native setup | Candidate refused access without approval; a forced native administrator cancel left setting off, and authenticated enable installed a healthy profile |
| Native consent | Existing AX/input/Screen Recording grants retained; additional ScreenCaptureKit prompt approved through observed native UI; enable now preflights it while unlocked |
| Normal screen lock | Approved connection transitioned from waiting to covered, temporarily unlocked console; independent outside capture showed cover |
| Native agent capture | ScreenCaptureKit PNG showed fixture underneath and excluded covers/operator app |
| Application effects | Independent fixture file proved AX counter action and synthesized keyboard delivery while covered |
| Completion | Final reusable AX/pointer/capture cell independently relocked, removed covers, and returned `completed` with no pause; guardian-owned ordering fixes the observed premature-relock race |
| Hardware keyboard takeover | Authorized Tart hardware-origin key caused relock, access revocation, physical-presence reason, and persistent pause |
| Manual recovery | Canonical owner-only stored appliance credential used only through exact-window secret transport; manual unlock cleared pause |
| Resident stall | SIGSTOP cell independently observed relock while resident suspended; companion/root remained effective |
| Resident crash | SIGKILL cell independently observed relock; pause persisted after signed resident replacement |
| Connection loss | Exact guest owner termination independently relocked and paused; outer-wrapper exit alone is not claimed as transport-loss evidence |
| Refusals | No ordinary approval, stale stop ID, standalone workstation unlock, generic root-socket client proxy, and shell guardian invocation refused |
| Deadline expiry | Independent OS relock with `duration_expired`, zero covers, and no manual-unlock pause |
| Native pointer | Independent fixture counter increment beneath cover; operator windows hidden to preserve self-interface protection without false pointer refusal |
| Local disable | Immediate persistent off without administrator prompt; re-enable/repair uses native setup |
| Covered refusals | Explicit Cua route and additional DevTools approval prompt refused; existing covered grant reuse retains original authority/lifetime |
| Hardware pointer takeover | Authorized Tart pointer event caused `physical_presence`, independently observed relock, access revocation, and manual-unlock pause |

Reusable [acceptance runner](../../tests/macos/locked-use-live.py) runs one
explicit cell per approval/manual-unlock cycle. Private captures and exact
identities stay outside Git. The independent outside/agent image comparison and
hardware-origin input used the user's explicit outer authority under a
renewed disruptive target claim. Ordinary application effects used inner native
routes; no worker agent was needed.

### Remaining qualification

This is bounded VM evidence for one display on macOS 26.6.2, not physical-Mac,
Intel execution, multiple-display, notarized-distribution, or all-macOS acceptance.
The earlier SIP-enabled appliance unlock evidence does not qualify this new
covered workstation profile; repeat its acceptance with SIP enabled.
Full system sleep, real laptop lid, display hotplug, fast-user switching,
forced guardian death, daemon restart, power loss, and real transport failures
remain distinct qualification cells. The killed-cover-process exposure interval
is not eliminated by a normal user window; the watchdog requests relock, but
no zero-frame privacy guarantee or same-user shell containment is claimed.
The lock primitive is a measured private OS API. No Cua covered-control
acceptance, sleep prevention, closed-lid, login, or FileVault/preboot support
was added. Consumer launchers must adopt the documented task connection to
bind their own completion/disconnect to relock.

### Cleanup

The candidate and native test driver/job were removed. Administrator uninstall
restored the normalized original screensaver policy, removed the plug-in,
broker, dedicated authorization right, state, and socket. Original appliance
policy and absent local opt-in preference were restored; the temporary forced
password rule was removed. The final source-native resident was redeployed
through the supported wrapper. Read-only doctor independently reported
administration/resident/semantics/capture/input ready, unlocked desktop, no
unlock helper, and locked use off. The canonical owner-only credential remains
valid, verified by successful normal password recovery. The platform's ordinary
shutdown lacked administrator authority, so target-native authorized sudo
shutdown supplies the OS boundary. Independent doctor confirmed `power: off`,
matching the initial state; the exclusive disruptive claim was released after
restoration.

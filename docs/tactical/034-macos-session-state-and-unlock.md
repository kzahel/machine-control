# macOS session state and authorized unlock

Status: complete (bounded SIP-enabled disposable-appliance implementation).

Owning topics: [macos-resident-control](../../topics/macos-resident-control.md),
[capabilities-and-results](../../topics/capabilities-and-results.md), and
[target-lifecycle-and-readiness](../../topics/target-lifecycle-and-readiness.md).

## Objective

Turn the tested authorization plug-in into an explicitly installed,
target-native unlock capability for an already logged-in, locked macOS
session. Give agents accurate screen-lock state and actionable unlock
readiness through doctor, resident status, and capability discovery. Both
guest-local and outside callers must use the same resident and protected
helper, without controlling a hypervisor window.

The originating request was to implement the feasible root-installed unlock
approach and expose whether the screen is locked and whether Machine Control
can unlock it. The user subsequently authorized implementation and a commit on the main
branch. That authorization covered the disposable VM, not the controller's
physical desktop.

## Evidence and starting points

**Current:** [Tactical 033](033-macos-sip-authorization-unlock.md) proved the
owned plug-in on a disposable Tart guest with SIP, authenticated-root
protection, and Gatekeeper enabled. Installation and policy registration used
root commands without Settings interaction or reboot. Ordinary resident input
and capture separately needed normal Accessibility and Screen Recording
consent. Root did not substitute for that consent.

The [macOS platform report](../../research/platforms/macos.md#owned-authorization-unlock-prototype)
owns the evidence summary. The
[retained prototype](../../platforms/macos/experiments/authorization-unlock/README.md)
owns the mechanism and reproduction procedure. A valid direct authorization
evaluation did not itself unlock the desktop: loginwindow had to invoke the
mechanism, triggered by a guest-native empty Return in the tested flow.

The [lock investigation](../../platforms/macos/docs/lock-screen-investigation.md)
also found false unlocked reporting and app-targeted input reaching the
password field. Relevant implementation surfaces are:

- `platforms/macos/guests/macos/ui/macui.swift` and its guest-local client;
- `platforms/macos/scripts/doctor-json.sh` and `doctor.sh`;
- platform deployment/bootstrap scripts and the common desktop adapter;
- `contracts/doctor-v0.schema.json`, the request/result contract, and client
  contract validation; and
- `tests/macos`, platform smoke fixtures, and common client tests.

Reusable code belongs in the canonical macOS guest implementation. The
experiment remains an evidence reference, not a second production installer.

## Completion conditions

1. Doctor and resident status agree on freshly observed locked, unlocked,
   no-session, or unknown state; neither substitutes console ownership for
   lock observation. Administration, display availability, permissions, and
   ordinary UI readiness remain separate.
2. Discovery distinguishes implemented support, installation/health, configured
   authorization, caller eligibility, and readiness for this session. Every
   unavailable or unknown result includes a typed reason and relevant next
   action. Read-only checks never arm, unlock, wake, install, or show consent UI.
3. An explicit root-authorized installer deploys the owned plug-in and narrow
   privileged helper, verifies policy integration, preserves password
   fallback, and supports conflict-aware upgrade, rollback, and removal.
4. An authenticated, typed resident unlock request works locally and remotely
   without an account password or per-request sudo. It binds to fresh target,
   session, desktop, resident, and helper state and has one bounded attempt.
5. Ordinary app input cannot knowingly be redirected into loginwindow.
   Session transitions invalidate stale references and pending authorizations.
6. The SIP-enabled disposable-VM matrix below passes with outer UI prohibited,
   independent unlock/application effects, restoration, and claim cleanup.
   Physical hardware and distributed installer acceptance remain separately
   labeled until those tests actually run.

## Boundaries

- **Decision:** Successful unlock exposes the ordinary desktop. Screen covers,
  local-input blocking, automatic relock, and preserving the visible lock
  screen during control are deferred. Grant expiry limits authorization time,
  not the duration of the unlocked session.
- Scope is the selected user's existing console session. Fresh login,
  FileVault/preboot, Recovery, other-user unlock, and general fast-user-switching
  control are excluded; detect or refuse unsupported/ambiguous transitions.
- Preserve SIP, authenticated-root protection, Gatekeeper, account policy,
  normal password fallback, and supported TCC consent. Authorization policy
  composition is the explicit opt-in change, using Authorization Services
  tooling; do not edit TCC databases.
- Root installation and TCC consent are separate setup steps. An already
  authorized agent/control channel may complete normal consent and admin UI
  within the user's authorization. Initial trust still requires a human or
  an existing authorized channel. Do not promise one prompt for every setup.
- Expose no arbitrary privileged command, path, authorization-right name, or
  input-event dispatch. A target-use claim is cooperative usage coordination,
  not broker authentication or permission to unlock.
- The appliance profile provides no containment against a sudo-capable agent.
  Authenticate the actual IPC peer and document the allowed local identity;
  do not present self-asserted agent labels as a security boundary.
- Execute VM work only after exact-target doctor and exclusive claim, carrying
  the claim and workspace handle where applicable, renewing as needed, and
  releasing in finally-style cleanup. Do not use controller-desktop input.
  Physical testing requires a separately authorized target and test window.
- Keep concrete inventory, grants, raw captures, and credentials outside Git.
  Dummy test credentials remain in the private machine manifest/store; normal
  password fallback uses the dedicated credential transport.

## Ordered implementation

### 1 — define truthful state and unlock discovery

**Implemented design:** Reuse `states.desktop` in doctor and `desktopState` in resident
status. Add one shared, typed unlock projection to capabilities/status and a
validated doctor extension rather than separate contradictory booleans.
Finalize field spelling in the contract before wiring adapters. The projection
must represent these independent facts:

| Fact | Required meaning |
| --- | --- |
| Screen state | `locked`, `unlocked`, `no_session`, or `unknown`, with source, observation time, and opaque transition generation |
| Display state | Active, inactive, or unknown; independent of lock and full system sleep |
| Unlock support | Implemented scope and evidence level; installation alone is not live readiness |
| Installation | Missing, healthy, inconsistent, or unknown; component versions, helper reachability, and policy integration checked separately |
| Policy | Enabled or disabled for the selected local profile/session scope |
| Caller eligibility | Allowed, denied, or unknown based on the real authenticated context; discovery without that context must not claim permission |
| Current readiness | Ready, not needed, unavailable, or unknown, with typed blockers and bounded remediation |
| Consequences | Actual native provider route, required privilege/input route, and exposed desktop after unlock |

Readiness is a fresh preflight, not a guarantee that a subsequent action will
succeed. An unlocked session is `not needed`, while still reporting whether
the provider is installed and enabled. A locked session can have unlock ready
and ordinary desktop `ready: false`. Missing Screen Recording affects capture;
it must not block unlock unless the selected unlock route actually requires
it. Missing input consent does block a route that depends on that input.

Example summaries: “locked; unlock ready”, “locked; helper not installed”,
“locked; caller not authorized”, and “screen state unknown; resident
unreachable”. Proposed reason codes include `unlock_not_installed`,
`unlock_disabled`, `unlock_policy_conflict`, `unlock_caller_denied`,
`unlock_caller_unknown`, `unlock_input_unavailable`, `no_interactive_session`,
and `session_state_unknown`.

Keep stopped/unreachable results honest: lack of a resident response is not
proof of either a locked or unlocked screen. Human and JSON doctor output
must agree. Preserve `ensure-ready`'s existing start-only behavior; it must not
implicitly install or unlock.

### 2 — observe session transitions and guard ordinary input

Create a shared native session observer usable by the resident, read-only
doctor probe, and helper. Begin with the prototype's measured OS signals,
validate their availability on the tested OS, and return unknown for missing,
contradictory, or ambiguous evidence. Treat notifications as invalidation
signals and re-read state before protected or foreground mutations.

Track desktop transitions independently of resident process generation.
Invalidate element references and authorization leases across lock/unlock,
console-user change, logout, and observer uncertainty. Never silently retarget
a pre-lock reference after unlock.

Guard native and Cua app-directed keyboard/pointer dispatch: require the
intended desktop and verified activation/focus before global input. Return a
typed refusal without posting if those checks fail. Record the remaining
check-to-dispatch race honestly, recheck after dispatch, and do not claim
atomic targeting where the underlying API cannot guarantee it. Keep a narrowly
selected loginwindow trigger separate from ordinary app input. Do not disable
healthy administration or mislabel retained window pixels as interactive UI.

### 3 — package explicit installation and restoration

Promote the original plug-in into the guest runtime and add a separately
supervised privileged helper. Select and document the supported macOS service
installation mechanism and stable signing identities; keep development and
distribution profiles explicit. Ordinary bootstrap must not silently opt the
machine into alternate screen-unlock authorization.

Provide explicit install, inspect, disable, and uninstall operations. The
installer must validate ownership/signatures and expected existing policy,
save a protected original policy and installation receipt, install verified
components before enabling the alternate branch, and read back the result.
Reject unsupported policy composition instead of overwriting another product's
integration. Preserve the original password branch.

Make repeated installation idempotent. Upgrade and failure rollback must
compare current state with the installer-owned receipt before restoring or
removing it. Disable/revoke first; remove the policy reference before deleting
its plug-in. Interrupted installation and interrupted removal must remain
recoverable through target-native administration. Never overwrite unrelated
policy changes during cleanup.

Document separately: root/admin installation, ordinary Accessibility consent,
capture consent, resident restart when required, and the initial trusted
channel. Use the existing bounded admin-sheet credential helper where its
fingerprint matches. Do not make headless Screen Sharing or its experimental
client a mandatory runtime dependency.

### 4 — implement the protected unlock transaction

**Implemented design:** Add `session.unlock` to the resident and expose it through the
common desktop client, preserving the existing request/result vocabulary.
The operation is explicit and takes no account credential. It carries an
expected opaque session/desktop generation and bounded request identity;
installation and opt-in policy remain separate from invocation.

The resident reaches the privileged helper through authenticated local IPC.
Specify peer identity verification, root-owned policy, allowed caller scope,
payload bounds, concurrency limits, and revocation before enabling arming.
Remote transport authenticates access to the resident; the helper validates
the resident peer and configured scope. Neither a claimed bundle identifier
nor a target-use claim is sufficient authentication. Keep internal arm/revoke
operations out of the general agent surface.

Serialize attempts for the selected session. Recheck lock, console session,
policy, permissions, and generations; create one short-lived grant; trigger
the independently identified loginwindow through the measured native route;
then observe lock state and revoke any outstanding grant in cleanup. Retain
the prototype's one-shot consumption, monotonic expiry, purpose/session/boot
binding, and protected file handling. Add helper/resident restart invalidation.

The prototype grant authorizes the next matching mechanism evaluation; a
competing evaluation could consume it. Investigate correlation available to
the authorization callback and test concurrent consumers. Do not claim the
callback authenticates an agent merely because the broker authenticated the
arming request. If the OS cannot bind the callback to that initiating request,
document the bounded session-wide authorization window and restrict acceptance
to the explicitly opted-in appliance profile.

Separate accepted request, trigger delivery, authorization outcome, observed
unlock, and uncertainty. Authorization success alone is insufficient. Already
unlocked is an observed no-op, with no grant or key injection. Timeout or
transport loss after dispatch yields an observable/reconcilable unknown
outcome, not an automatic retry. Repeated request identities must not create
another grant. Another user's session, changed generation, or unknown state
must refuse before arming.

### 5 — integrate doctor, maintenance, and agent guidance

Project the shared observer and helper health into both doctor implementations,
resident status/capabilities, and common schema validation. Doctor must work
when the helper is missing and must not require that helper to determine lock
state if an ordinary read-only OS probe is available. A health check must never
evaluate the unlock mechanism or consume a pending grant.

Add bounded installation/policy checks to macOS maintenance audit. Repairs
must preserve explicit opt-in and current installation ownership; ordinary
resident repair must not install unlock authority by implication. Expose
actionable blockers to agents with separate permission, display, resident,
helper, and policy state. Describe installation, explicit unlock, independent
post-unlock verification, disable/removal, and failure recovery in the runbook.

### 6 — prove the SIP-enabled appliance and record acceptance

Use a disposable SIP-enabled guest. Record authenticated-root, Gatekeeper,
artifact provenance, and actual signatures independently. Keep any consent
bootstrap separate from acceptance, disconnect its remote-viewing client before
unlock tests, and prohibit outer UI for both local and remote callers.

| Validation | Required independent result |
| --- | --- |
| Missing/disabled helper | Accurate lock state remains available; unlock has the correct blocker; doctor makes no mutations |
| Locked/unlocked/no-session/unknown and inactive display | Doctor/status agree with OS observations; readiness does not confuse permission, display, transport, or session state |
| Ordinary input while locked; activation failure | App-targeted key/pointer requests refuse before posting; fixture and login field show no unintended effect |
| Transition and stale references | Lock/unlock and session changes invalidate references/leases without resident restart; uncertain transitions refuse |
| Authorized unlock, local and remote | Repeated cycles observe OS unlock and fresh fixture AX/file effects; no credential entry or per-request sudo |
| Denied/unknown caller or disabled policy | Refused before grant creation and trigger delivery |
| Missing, expired, reused, wrong-session/boot/generation grant | Denied; no unintended unlock; ordinary password fallback still works |
| Concurrent requests and competing mechanism evaluation | At most one grant consumption; no cross-session authorization or false attribution of effect |
| Lost transport, trigger failure, timeout, helper/resident restart | Outstanding authority expires/is revoked; outcome is reconciled without blind replay |
| Install twice, upgrade, partial failure, external policy change | Idempotency, bounded rollback, and conflict-aware refusal; stock password path preserved |
| Reboot after installation | Helper/resident recover after normal session bootstrap; no previous grant survives; fresh-login behavior is not claimed |
| Disable and uninstall | Unlock becomes unavailable, policy restoration verified, stock password unlock and ordinary fixture control still work |

Run focused native unit/fixture tests for grant validation, state projection,
input refusal, IPC authorization, and installation transactions. Run affected
portable contract/client and macOS smoke checks, then the relevant ordinary
resident and administrator-sheet regressions. Do not treat mocks as evidence
of loginwindow behavior or broker authentication under the actual OS.

Record exact build/source evidence privately, minimize public results, restore
policy, remove owned fixtures/artifacts, stop/dispose the task-owned VM, and
release its claim. Update the platform report, macOS topic, runbook, tactical
index, and this result before labeling the capability accepted.

## Physical device and distribution follow-up

Retain a reproducible checklist for an explicitly authorized spare physical
Mac: protection state, artifact provenance, installer authorization and TCC
steps, lock/status parity, native unlock plus app effect, password fallback,
display-off behavior, restart, and removal. Full system sleep is separate from
display sleep and may make resident transport unavailable. Do not infer
physical behavior from Tart or test the controller's desktop without approval.

Validate Developer ID/notarized downloaded artifacts and their actual
quarantine/assessment path separately from locally built ad-hoc artifacts.
Report VM implementation acceptance, distribution acceptance, and physical-Mac
acceptance separately; missing signing credentials or hardware must not erase
the narrower completed evidence or be presented as a passing result.

## Final result

**Current (2026-09-10):** Implemented and accepted for the explicitly opted-in
SIP-enabled Tart appliance. The common CLI exposes `desktop session unlock`,
and the resident exposes `session.unlock`. Shared native observation drives
status, capabilities, doctor, transition generations, and input guards. The
root installer owns an authenticated LaunchDaemon and original Authorization
Services plug-in; ordinary deployment and maintenance never opt in implicitly.
The [runbook](../../platforms/macos/docs/session-unlock.md) and
[component design](../../platforms/macos/guests/macos/unlock/README.md) own current
operation and trust-boundary guidance.

### Recorded validation

The fresh disposable vanilla guest ran macOS 26.6.2 on Apple silicon. SIP and
authenticated-root protection remained enabled. Gatekeeper was explicitly
enabled before installation and verified again after removal. The artifacts
were locally compiled and ad-hoc signed. Normal Accessibility and Screen
Recording consent used guest-native Screen Sharing; its client was disconnected
before integrated unlock acceptance. Outer UI remained prohibited. All target
operations carried an exact exclusive claim; private inventory, dummy
credentials, identities, captures, and raw evidence stayed outside Git.

| Area | Result and evidence boundary |
| --- | --- |
| Local/remote unlock | Both placements passed repeated cycles before and after cold boot using the same resident/helper. Native lock readback and fresh AppKit counter effects confirmed unlock independently. No unlock password or per-request sudo was used. |
| Lock/input/references | Locked doctor/status agreed; native and explicit Cua key/pointer requests refused before provider dispatch; fixture counters stayed unchanged. Old desktop/helper generations and pre-lock AX references refused. Duplicate IDs refused; an unlocked request performed no input. Cua was absent on this vanilla guest, so this proves its common pre-dispatch guard, not Cua execution. |
| Shared observation | Locked and unlocked live observations passed, including locked doctor with the helper removed and the resident stopped. Display-off separately reported inactive/capture unavailable, then explicit guest-native activity restored the display. Pure native fixtures covered no-session, missing, malformed, and ambiguous observations; no fresh-login or fast-user-switching acceptance is claimed. Legacy-resident and powered-off doctor fixtures remained unknown rather than falsely unlocked. |
| Broker authentication | Same-UID unapproved code and root fixture clients were denied. Rebuilt resident code was denied until explicit reinstall approved its new hash. Temporary privileged fixture authorization was restored in finally-style cleanup. |
| Grant validation | Twenty-two checks used the production validator in a separate root-only fixture directory: missing, malformed, expired, reused, wrong purpose/session/user/boot/epoch, dead process, excessive/future lifetime, unsafe permissions, symlink/hardlink, and disabled policy. Eight competing consumers produced exactly one success while the OS remained locked. |
| Revocation/restarts | Armed-client disconnect and a no-trigger timeout revoked the grant without unlocking. Helper/resident restarts invalidated generations. Cold boot recovered both services and no grant survived. Ordinary desktop readiness preceded helper readiness briefly; tests waited on both independent dimensions without repair. |
| Installation/recovery | Repeated install and resident-hash upgrade converged. An actual policy-readback failure during development disabled the provider and restored stock policy before correction. Disable/re-enable passed. External policy drift and missing plug-in files reported inconsistent health; conflicting installation refused, and restoring the owned state recovered health. |
| Password/removal | With an already-connected native viewing channel, unarmed empty Return remained locked and the manifest dummy password unlocked normally, both with the plug-in installed and after uninstall. The original screensaver policy matched the saved baseline ignoring OS timestamps; the dedicated right and owned files were removed. |
| Ordinary authorization | Native administrator-sheet cancellation and credential submission still passed, with independent authorized/read-only command-completed fixture evidence. Credentials used the existing dedicated socket transport. |
| Repository checks | Portable repository checks, 91 common client tests, macOS static smoke/native builds, observer parser fixtures, and four doctor projection fixtures passed. No controller desktop was operated. |
| Cleanup | Removed fixtures and owned unlock policy/components, verified protection state and ordinary doctor readiness, stopped/disposed the exact task VM, and released its claim. The prepared source image was unchanged. |

Portable verification used `WINVM_TARGET_FILE=/dev/null bin/check --portable`
to isolate an existing Windows missing-identity fixture from the controller's
private target pin. The initial unisolated run failed that fixture; the isolated
full suite passed. Native verification used `platforms/macos/tests/smoke.sh
--static`, which performs no desktop control.

### Explicit limits and follow-up

The provider advertises `experimental` despite this bounded acceptance. The
callback grants the next matching evaluation in a short session-wide window;
it cannot authenticate the agent that initiated the request. Atomic one-use
consumption is tested, not adversarial loginwindow attribution. Kernel peer
identity plus code-hash pinning authenticates the broker connection and does
not contain an agent with the same-user shell or sudo.

The observer/notification checks do not make global input atomic with OS
transitions. Multiple users, localization, physical display/wake differences,
full system sleep, extended stress, and process termination at every installer
write boundary need additional acceptance. The display-off reporting cell ran
after removal; the installed helper's inactive-display blocker has source and
preflight coverage rather than a separate successful wake/unlock cycle.
Fresh login, preboot, and screen covering remain outside this slice.

The installer uses an explicit root executable and LaunchDaemon, with no
installer GUI or distribution package. Developer ID signing, notarization,
download quarantine assessment, and an authorized physical SIP-enabled Mac
remain separate follow-ups. Root setup does not replace normal TCC consent.
No evidence here claims broad personal-workstation deployment acceptance.

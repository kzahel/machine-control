# Session state and authorized unlock

The macOS resident reports actual screen-lock state and offers an explicitly
installed password-free unlock route for an existing console session. Normal
application interaction resumes after unlock. The desktop becomes visible and
stays unlocked; no screen cover or automatic relock is provided.

## Observe first

```bash
mc=bin/machine-control
$mc --target macos target doctor
$mc --target macos --claim "$claim_id" desktop status
$mc --target macos --claim "$claim_id" desktop capabilities
```

Doctor is read-only and remains available without a target-use claim. Acquire
an exact exclusive claim before target operations, carry it throughout work,
renew it as needed, and release it in cleanup. The examples assume an existing
claim and use only a logical target selector.

`states.desktop` in doctor and `data.desktopState` in resident status describe
`locked`, `unlocked`, `no_session`, or `unknown`. Display state, administration,
resident reachability, capture, and ordinary input/semantics are separate.
Console ownership alone never proves unlocked. Unknown/unreachable observations
remain unknown. A locked but unlockable target still has ordinary desktop
`ready: false`; administration can remain ready.

Doctor's `extensions.unlock` and resident `data.unlock` share the typed
[unlock status schema](../../../contracts/unlock-status-v0.schema.json).
Inspect `support`, `installation`, `policy`, `callerEligibility`, `readiness`,
and `reasons`. Installation alone is insufficient. An unlocked session reports
`not_needed` while preserving installation/permission blockers for future use.
Status and doctor never arm a grant, wake the display, or prompt for consent.

## Lock-screen observation and keyboard permission

Doctor's `extensions.lockScreen` and resident status/capabilities `data.lockScreen`
report native lock-screen prerequisites separately from ordinary app readiness
and the optional root helper. The [schema](../../../contracts/lock-screen-status-v0.schema.json)
distinguishes:

- `captureState`: full-display capture preflight while locked, requiring normal
  Screen Recording consent and an active display. Use `capture` with display
  scope and the native provider. Window pixels under the lock screen are a
  different observation and do not prove an interactive app.
- `accessibilityState`: `unverified` when Accessibility consent permits a
  native `snapshot` targeted at `loginwindow`; status does not traverse its AX
  tree. Earlier VM tests exposed limited window/user/field metadata. Permission
  is not proof that a useful tree is presently available, and it does not
  expose the password or authorize credential entry.
- `nativeKeyboardPermission`: the native event-posting consent preflight,
  independent of helper installation. `granted` is not a guarantee of event
  delivery, display readiness, or a callable lock-screen typing API.
- `ordinaryInputPolicy: blocked_while_locked` and
  `credentialEntry: not_implemented`: ordinary app input remains blocked; a
  dedicated password-entry API has not been added. The existing narrow
  `session.unlock` trigger requires the installed, enabled helper.

These read-only observations do not require the unlock helper. They preserve
ordinary `inputState`/`semanticState` as unavailable while locked, so an agent
cannot mistake native permission for permission to send app input into the
password field. An unreachable/older resident reports unknown prerequisites.
The projection is native-only; it makes no new Cua locked-session claim.

Installation is an explicit persistent opt-in, never part of ordinary resident
deployment. An enabled idle helper has **no standing unlock grant**.
`unlock.armingMode: per_request` and `grantLifetimeSeconds: 10` describe its
transaction policy, not a live assertion that a grant is currently armed.
Only an accepted `session.unlock` transaction arms a one-use grant. Consumption,
disconnect, timeout, restart, or revocation ends remaining authority. Doctor,
status, and capabilities never arm it. No automatic relock is implemented.

## Explicit appliance installation

Prepare the ordinary resident and normal Accessibility consent first. Screen
Recording is needed for screenshots, independently of the authorization
plug-in. Root installation does not silently grant either TCC permission.
An agent with an existing authorized control channel can complete the normal
setup UI within its granted scope; initial trust still needs that channel or
human participation.

```bash
$mc --target macos --claim "$claim_id" testbed -- unlock-provider install --appliance
$mc --target macos --claim "$claim_id" testbed -- unlock-provider inspect
```

The platform wrapper builds on the Mac controller, stages signed artifacts
through the selected guest transport, and invokes the installer inside the
exact claimed target using existing noninteractive sudo. It cleans staging
on completion. It never installs on the controller. Without that root route,
perform the same native installer invocation through an explicitly authorized
administrator setup flow; the wrapper does not guess credentials or automate
an unrecognized prompt.

The native administrator invocation is:

```text
mc-unlock-install install --appliance-uid <console-uid> <resident-executable>
mc-unlock-install inspect
mc-unlock-install disable
mc-unlock-install uninstall
```

The native installer ships beside `MCUnlock.bundle` and `mc-unlock-broker`.
It backs up the original policy and preserves password fallback. No reboot or
SIP change was needed in the tested guest. Local ad-hoc signing evidence does
not establish notarized distribution or physical-Mac support. Reinstall after
a resident rebuild to approve its new exact code hash; TCC consent and broker
code authorization have distinct identities and lifecycles.

## Request unlock

Take fresh resident status and use its opaque desktop and helper generations:

```bash
state="$($mc --target macos --claim "$claim_id" desktop status)"
desktop_generation="$(jq -r '.data.desktopGeneration' <<<"$state")"
helper_generation="$(jq -r '.data.unlock.helperGeneration' <<<"$state")"
$mc --target macos --claim "$claim_id" desktop session unlock \
  --expected-desktop-generation "$desktop_generation" \
  --expected-helper-generation "$helper_generation" \
  --request-id "$(uuidgen)"
```

The resident operation is `session.unlock`. Guest-local callers use the same
JSON request and resident; `desktop raw-local` exercises that placement.
There is no password, root shell, arbitrary input, or arbitrary authorization
right in the request. Use only the current authenticated session's scope.

A successful result reports trigger delivery and independent OS lock-state
readback separately. Verify a fresh application effect before continuing UI
work. Old element references and administrator-sheet leases are invalidated
by desktop transitions; rediscover them. Do not blindly replay an uncertain
request. Observe current state first; request IDs cannot create a second grant
within the same resident/helper generation. The bounded caches refuse further
requests after 4,096 identifiers instead of evicting replay history.

An already unlocked request is a no-input no-op. `stale_generation` requires
fresh status. `unlock_caller_denied` can indicate a rebuilt resident whose
hash has not been approved. Other reasons distinguish disabled policy,
installation drift, unavailable input permission, and unknown session state.
`unlock_display_unavailable` means this measured trigger route needs an active
display. An explicitly requested guest-native wake can restore that condition;
doctor and unlock do not silently change persistent power policy. Full system
sleep and loss of transport remain separate conditions.

## Disable, remove, and validate

```bash
$mc --target macos --claim "$claim_id" testbed -- unlock-provider disable
$mc --target macos --claim "$claim_id" testbed -- unlock-provider uninstall
```

An external authorization-policy change causes conflict-aware refusal instead
of overwriting another integration. Failed install/removal retains the receipt
for recovery and disables grants where possible. After removal, verify normal
password unlock through an authorized native channel. Routine maintenance audit
checks an enabled provider; maintenance repair never opts in or repins it.

The [implementation and trust boundary](../guests/macos/unlock/README.md) and
[Tactical 034](../../../docs/tactical/034-macos-session-state-and-unlock.md)
record the component design, test matrix, and remaining acceptance boundaries.
Use a disposable SIP-enabled target for reproduction. Physical-Mac evaluation
requires a separately selected and authorized target; it is not implied by
permission to operate a VM.

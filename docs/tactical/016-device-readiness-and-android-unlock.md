# Tactical 016: Device Readiness and Android Unlock

Status: complete with physical acceptance gaps recorded.

Topics: `target-lifecycle-and-readiness`, `capabilities-and-results`,
`android-family-control`, and `ios-device-control`.

## Objective

Make attached-device targets participate in the common outer target surface
without inventing a generic mobile UI abstraction. Project the existing iOS
and Quest providers into a device-capable doctor contract, add a generic
Android-handheld implementation over shared ADB transport, and prove a
secret-safe, single-attempt Android PIN-unlock route. Add an explicit iOS full
reboot and reconnect operation while continuing to report post-reboot local
authentication honestly.

## Completion conditions

- `machine-control --target <device> target status|doctor|capabilities` works
  for normalized device adapters rather than requiring `testbed --`.
- The doctor contract distinguishes target kind, connection, boot,
  interaction, and runner state without requiring device targets to claim a
  desktop or resident process.
- A canonical `platforms/android` adapter selects an exact authorized physical
  Android handheld and exposes read-only status/doctor plus bounded wake,
  keyguard dismissal, reboot, deployment, capture, log, and shell operations.
- Android and Quest use one neutral ADB discovery/transport implementation;
  phone keyguard policy and Quest headset policy remain separate.
- Android PIN unlock refuses before reading a secret unless the exact target,
  secure PIN surface, wipe policy, injection helper, and target generation are
  known. The secret travels only over dedicated standard input and one-shot
  device-helper input, never JSON, arguments, environment, logs, captures, or
  committed state. One submission is independently observed and never retried.
- The iOS adapter emits the common doctor projection and supports a full
  CoreDevice reboot that waits for the physical device to reconnect and then
  reports lock and runner readiness without attempting passcode or biometric
  entry.
- Unit tests cover projection validation, target selection, state parsing,
  refusal-before-secret behavior, single delivery, effect observation, and
  device-specific policy boundaries. Available physical targets receive
  proportionate read-only or safely bounded live validation.
- Research, living topics, platform guides, the system map, and this tactical
  state the implemented result and remaining gaps.

## Boundaries

- Do not create a generic mobile semantic/action vocabulary in this slice.
  iOS XCTest, Android UIAutomator, and Quest system UI remain distinct.
- Do not make Quest a generic Android phone or apply phone PIN/keyguard policy
  to a headset.
- Do not automate an iOS passcode, biometric prompt, account recovery, or
  protected authorization. Apple Configurator supervision and passcode-clear
  recovery require a separate evidence-backed slice.
- Do not clear, replace, store, or log an Android credential; weaken Android
  lockout, wipe, biometric, or device-policy settings; or deliberately test an
  incorrect PIN.
- Do not treat ADB authorization, a device serial, or a logical target alias as
  bearer authority.
- Do not add MDM, signing-account automation, simulator parity, UIAutomator
  semantics, or long-duration device-farm orchestration here.

## Implementation steps

### 1 — make doctor describe desktops and devices honestly

Extend `machine-control-doctor/v0` with explicit target kind and device state
dimensions. Preserve accepted desktop documents while validating device
documents according to their own connection, boot, interaction, and runner
requirements. Let the common client derive device status and capabilities from
the normalized doctor without assuming desktop lifecycle parity.

### 2 — project the adopted device providers

Add minimized common doctor documents to the iOS and Quest adapters. Preserve
their existing human-oriented native doctors and platform extensions, but keep
identifiers, configuration, and private diagnostic details out of the common
projection.

### 3 — establish the Android-family ADB boundary

Extract neutral ADB executable discovery, device enumeration, exact transport,
shell, battery, and wake-state primitives from the Quest implementation. Keep
Quest recognition and headset policy in `platforms/quest`. Build
`platforms/android` as the physical-handheld specialization with its own
selection, readiness, keyguard, and lifecycle policy.

### 4 — implement guarded Android PIN unlock

Observe boot, current-user, user-storage, keyguard, credential kind, wipe
policy, PIN field, and boot generation before opening the secret channel.
Build and stage a bounded helper that reads the PIN from standard input and
injects key events inside one device process so credential material is not
placed in an ADB or device-process argument. Submit once, clear mutable buffers
best effort, observe keyguard and user-storage state independently, and emit a
truthful common result with no automatic retry.

### 5 — add iOS reboot and reconnect readiness

Stop only testbed-owned runner state, acquire the existing device lease, issue
a full CoreDevice reboot with wait-for-device, and re-observe connection, lock,
unlocked-since-boot, and runner-cache state. Keep any XCTest local-authentication
gate visible as degraded or unavailable readiness rather than attempting to
bypass it.

### 6 — validate and publish current truth

Run shared-client, shared-ADB, Android, Quest, and iOS unit suites plus compile
and documentation checks. On already available devices, prefer read-only doctor
and helper build/preflight checks; perform reboot or real credential delivery
only when the target state and required human secret handling make it safe.
Update the owning research/topics and this tactical with exact evidence,
deviations, and remaining work.

## Validation plan

- `python3 -m unittest discover -s tests/client -v`
- shared ADB and Android platform unit/compile tests
- `python3 -m unittest discover -s platforms/quest/tests -v`
- `python3 -m compileall -q platforms/quest providers/adb platforms/android`
- `cd platforms/ios && pnpm check`
- common `targets`, Android/iOS/Quest `target doctor`, and minimized-output
  inspection against any already attached authorized devices
- Android helper build and refusal-before-secret validation without entering a
  credential into the agent transcript
- `git diff --check` and a public-data review before commit

## Result

Completed 2026-08-11.

The common client and `machine-control-doctor/v0` now distinguish desktop and
device target kinds. Android, iOS, and Quest device documents report
connection, boot, interaction, and runner state in addition to their common
administration, semantic, capture, input, power, and route dimensions. Native
device adapters expose common `target status|doctor|capabilities`; a lifecycle
mutation is dispatched only when that exact adapter declares it. Existing
desktop doctors remain compatible and desktop reboot remains a platform escape.

[`providers/adb`](../../providers/adb/README.md) is the neutral ADB boundary
used by both Android handheld and Quest. Quest retains headset recognition,
proximity, battery, lease, panel, and safe-sleep policy. The new canonical
[`platforms/android`](../../platforms/android/README.md) adapter owns eligible
physical-handheld selection, boot generation, current-user storage, keyguard,
credential and wipe-policy observation, wake/dismiss/reboot, bounded
deployment/capture/log/shell operations, and the protected PIN route.

The Android PIN implementation builds a small checked-in Java helper into
private controller state, stages it only after complete non-secret preflight,
reads 4–16 digits through dedicated non-echoing standard input, passes bytes to
one `app_process` over ADB standard input, submits once, clears mutable buffers
best effort, removes the helper, and independently re-observes keyguard and
user-storage effect. Refusals, unknown delivery, and no effect never retry.

The iOS adapter now emits the common minimized doctor and offers a leased full
CoreDevice reboot with `--wait-for-device`. Its doctor reports CoreDevice lock
facts and keeps XCTest runner authentication explicitly unverified until
launch; it does not automate passcode or biometrics.

### Validation record

- Common client: 24 dependency-free tests passed, including legacy desktop
  doctor compatibility, native-device status/capabilities, declared reboot,
  undeclared lifecycle refusal, and desktop reboot refusal.
- Shared ADB: two unit tests passed. Quest: 13 tests passed after adopting the
  shared provider and minimized doctor; unavailable hardware returned a valid
  non-ready common document without identifiers.
- Android: ten tests passed for profile selection, parsing,
  refusal-before-secret, wipe policy, exactly-one delivery, effect observation,
  timeout/unknown delivery, buffer clearing, zero retry, and result redaction.
  Compile checks passed.
- On an attached authorized physical Android handheld, the common doctor,
  status, and capabilities were ready and identifier-free. The helper built,
  staged, started as the shell identity, rejected empty input with a nonzero
  status and no output/injection, and was removed. The already-unlocked route
  confirmed state without reading a secret.
- iOS: all 19 wrapper tests passed. Before the live reboot, the physical phone
  emitted a ready minimized doctor with unlocked-since-boot and cached-runner
  state. The common full reboot was issued, but CoreDevice did not rediscover
  the phone during its bounded wait; later CoreDevice and USB observations
  reported it absent. The lease was released, doctor became unavailable, and
  no protected or outer fallback was attempted.
- JSON/compile checks, `git diff --check`, and public-data review passed.

### Deviations and remaining work

- No real PIN entered the agent transcript or test process. Correct-PIN helper
  delivery and keyguard effect are unit-tested and built, but require one
  separately supervised live acceptance before promotion to `live-tested`.
- iOS full-reboot reconnect and first XCTest launch are not accepted. The phone
  requires local inspection before a new bounded attempt can classify power,
  USB, trust/developer-services, and local-authentication state.
- The private inventory provider does not yet declare the concrete Android
  target. Live common-client validation used the portable default with exactly
  one eligible attached handheld; adding the private selector belongs in the
  private dotfiles inventory.
- UIAutomator semantics, Android emulator/ARCVM profiles, Apple Configurator
  recovery, free Personal Team signing, and generic device application/UI
  operations remain separate future slices.

# Android-Family Control

Topic: `android-family-control`

Status: active Android-handheld and Quest implementations over a shared ADB
provider; phone credential effect and broader Android profiles remain open.

## Scope

This topic owns the reusable Android/ADB family boundary and the decisions that
separate neutral transport from target-profile policy. It does not make every
ADB target a phone or impose a generic mobile semantic model on Android, Quest,
ChromeOS ARCVM, emulators, TVs, watches, or automotive systems.

## Current implementation

**Current:** [`providers/adb`](../providers/adb) owns dependency-free ADB
executable discovery, device enumeration, exact transport, shell execution,
battery parsing, and wake-state parsing. Both the canonical
[`platforms/android`](../platforms/android/README.md) handheld adapter and
[`platforms/quest`](../platforms/quest/README.md) use it.

The Android-handheld adapter adds explicit eligible-device selection, boot and
boot-generation observation, current-user storage state, keyguard and
credential-kind inspection, failed-password wipe policy, application
deployment/lifecycle, display capture, bounded logs, explicit shell, wake,
keyguard dismissal, and reboot/wait behavior. It emits a minimized common
device doctor and remains a `native` platform interface for operations below
the common target layer.

Quest remains a separate platform profile. Its ADB transport is shared, while
proximity, headset sleep/wake, battery guards, Meta panels, remote recovery
journal, and safe final state remain Quest-owned policy.

## Decisions

**Decision:** Share facilities according to actual platform ancestry:

```text
common target doctor and results
  +-- Android/ADB provider family
  |     +-- Android handheld policy
  |     +-- Quest headset policy
  |     +-- future emulator, ARCVM, TV, and other profiles
  +-- iOS CoreDevice/XCTest family
```

The common layer owns target selection, authorization, readiness dimensions,
capabilities, delivery/effect/evidence, and typed refusal. Android/ADB owns
transport primitives. Each device profile owns lifecycle, protected surfaces,
semantics, and safety policy.

**Decision:** A phone unlock is a protected handheld operation, not a generic
ADB or Quest command. Ordinary `wake` and `dismiss-keyguard` contain no secret.
Secure `unlock` supports a PIN only and must:

- establish exact device, boot generation, current user, secure PIN field, and
  zero failed-password wipe threshold before reading a secret;
- receive the PIN only from dedicated non-echoing standard input;
- inject within one staged shell-UID helper process so the credential never
  becomes a host ADB or device-process argument;
- submit at most once, clear mutable buffers and staged helper best effort, and
  independently observe keyguard and user-storage effect; and
- refuse passwords, patterns, unknown surfaces, changed generations, unsafe or
  unknown wipe policy, and automatic retry.

## Evidence

**Current — live-tested:** On an attached authorized physical Android
handheld, the adapter selected the device without exposing its serial, emitted
a ready common doctor with boot, interaction, user-storage, capture, and input
state, and returned common status/capabilities through `bin/machine-control`.
The credential helper built from source, staged over ADB, started under the
shell identity, rejected empty input with no output or key injection, and was
removed. An already-unlocked `unlock --json` path confirmed state without
opening the secret channel.

**Current — unit-tested:** Tests cover handheld/Quest selection separation,
keyguard and user-state parsing, refusal before secret read, unsafe wipe-policy
refusal, exactly one helper delivery, mutable-buffer clearing, independent
unlock observation, zero retry, and absence of the test PIN from results.

**Open:** No real credential was entered during this slice. The helper's PIN
delivery and successful keyguard effect are therefore built and unit-tested,
not yet live- or conformance-tested. Deliberately entering a wrong PIN remains
out of scope.

## Recommended next work

- Run one supervised correct-PIN acceptance through the hidden prompt and
  retain only redacted delivery/effect evidence.
- Add a compact UIAutomator semantic adapter and deterministic Android fixture,
  then compare its snapshot/action behavior with the current iOS XCTest route.
- Add physical versus emulator identity and a separate emulator lifecycle
  profile.
- Decide how ChromeOS-local ARCVM ADB projects through this provider without
  moving its lifecycle out of the ChromeOS platform.
- Add private inventory for the actual Android handheld without publishing its
  serial or controller route.

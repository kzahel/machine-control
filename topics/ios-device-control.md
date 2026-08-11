# iOS Device Control

Topic: `ios-device-control`

Status: adopted CoreDevice/XCTest physical-device control with a common outer
doctor; full unattended reboot recovery is not yet accepted.

## Scope

This topic owns the current iOS physical-device control direction beneath the
common target layer: CoreDevice lifecycle and app operations, XCTest semantics
and input, signing/readiness, exclusive leases, protected-authentication
boundaries, and unattended recovery evidence. It does not force iOS into an
Android, desktop-resident, or generic mobile implementation.

## Current implementation

**Current:** [`platforms/ios`](../platforms/ios/README.md) remains the canonical
physical-iPhone adapter over CoreDevice and pinned Agent Device XCTest. It now
emits `machine-control-doctor/v0` with device connection, boot, interaction,
runner, semantic, capture, input, and device-host route state. The common
client exposes `target status|doctor|capabilities` while application and UI
operations remain explicit native iOS commands.

The adapter also exposes a leased full `reboot`: stop only testbed-owned runner
state, issue CoreDevice's full reboot with `--wait-for-device`, verify that the
selected phone reappears, and then let the common client re-run doctor. The
doctor reports the actual passcode-required and unlocked-since-boot values and
keeps runner authentication `unverified_until_launch`; connection alone is not
claimed as XCTest readiness.

## Decisions

**Decision:** Preserve CoreDevice/XCTest/Agent Device. Share only outer target,
authorization, readiness, capability/result/evidence, artifact, and generation
vocabulary with other platforms.

**Decision:** Do not automate entry of an iOS passcode or biometric response.
For a dedicated unattended device, separately investigate and prove:

- passcode-free operation through full reboot and first XCTest launch;
- free Apple Configurator supervision and saved-token passcode clearing as a
  typed recovery operation, not passcode entry; and
- free Personal Team runner provisioning as a distinct short-lived signing
  profile from supervision or MDM.

None of those possibilities weakens Developer Mode, trust, signing, account
recovery, Apple Pay, or protected security confirmations.

## Evidence and current gap

**Current — live-tested:** Before reboot, the connected physical phone emitted
a ready minimized doctor: CoreDevice connection and unlocked-since-boot were
observed, the signed runner cache was present, and runner authentication was
explicitly unverified until launch.

**Current — live failure:** A full reboot was issued through the new common
operation. CoreDevice did not rediscover the phone before its bounded wait
failed, and subsequent CoreDevice and USB observation reported it absent. The
adapter released its lease and the common doctor truthfully became unavailable.
No outer input, passcode, biometric, or silent recovery route was attempted.

This proves that the command and failure boundary work, but not unattended
reboot recovery. The earlier accepted evidence that a cached runner survived a
reboot/update still required a first-launch local-authentication action.

## Recommended next work

- Restore and inspect the physical phone locally, determine whether the failed
  full reboot left it powered off, booted but absent from USB, or behind a new
  trust/developer-services condition, and record only sanitized evidence.
- Re-run `reboot` after the cause is understood, then launch the runner and
  classify the exact post-boot authentication gate.
- Test the passcode-free dedicated-device profile independently of the current
  paid-team signing profile.
- Source-review and live-test Apple Configurator supervision, escrowed unlock
  token storage, and clear-passcode recovery before changing the current human
  gate policy.
- Decide physical/simulator identity and capability differences only after the
  physical recovery path is stable.

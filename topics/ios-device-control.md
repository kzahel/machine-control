# iOS Device Control

Topic: `ios-device-control`

Status: adopted CoreDevice/XCTest physical-device control with passcode-free
unattended reboot recovery accepted and passcoded first unlock kept human.

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
client exposes `target status|doctor|capabilities` plus a bounded `ios` family
for runner preparation, application install/launch/termination, semantic
snapshot/press/fill, and Home. These remain explicitly iOS operations rather
than Android or desktop parity.

Read-only selection now merges the ordinary CoreDevice list with Apple's
lower-level Developer Mode inventory and deduplicates CoreDevice and hardware
identities. An explicit leased `pair` bootstraps only the exact configured phone
when Trust has not converged. A passcode-protected phone still requires its
Trust/passcode confirmation locally; the adapter never receives that secret.

The leased full `reboot` stops only testbed-owned runner state, requests a full
CoreDevice reboot, observes disappearance and return of the same phone itself,
and lets the common client re-run doctor. It no longer treats CoreDevice's
premature built-in wait failure as the final effect. Connection, current
passcode requirement, unlocked-since-boot, interaction gate, runner cache, and
runner authentication remain separate observations.

Signing account class is an operator declaration, not an inference from a team
identifier. Doctor separately reports `developer_program`, `personal_team`, or
`unspecified` policy and the matching cached runner's observed embedded-profile
lifetime. Expired profiles make the cache unavailable. A declared Personal
Team refreshes only the exact matching rebuildable cache once 48 hours or less
remain; explicit `prepare --refresh` provides the same bounded recovery.

## Decisions

**Decision:** Preserve CoreDevice/XCTest/Agent Device. Share only outer target,
authorization, readiness, capability/result/evidence, artifact, and generation
vocabulary with other platforms.

**Decision:** Use an explicitly named common `ios` family for ordinary
operations that benefit from target selection and normalized results. Do not
promote that family into a generic mobile abstraction unless another device
independently proves the same semantics useful.

**Decision:** Support two honest profiles through one native provider:

- A passcode-free dedicated device can pair, reboot, reconnect, and restart
  XCTest without local interaction once Trust and wired-accessory policy are
  prepared.
- A passcode-protected device is ready after its local first unlock. Reboot
  delivery may succeed while doctor reports connection ready, interaction
  protected, runner unavailable, and `manual_first_unlock_required`.

Do not automate entry of an iOS passcode or biometric response. Free Apple
Configurator supervision remains an optional repeatable-provisioning route,
not a prerequisite or passcode-entry mechanism. Free Personal Team runner
provisioning remains a distinct short-lived signing profile from supervision or
MDM.

None of those possibilities weakens Developer Mode, trust, signing, account
recovery, Apple Pay, or protected security confirmations.

## Evidence and current gap

**Current — live-tested, passcode-free:** Removing the passcode caused an
ordinary Trust flow not to appear immediately in CoreDevice inventory. Apple's
Developer Mode inventory still found the phone; explicit CoreDevice pairing
then reported it physical, paired, wired, tunnel-connected, and Developer Mode
enabled. Common doctor became ready with `passcodeRequired: false`,
`unlockedSinceBoot: true`, and no observed interaction gate. XCTest preparation
completed before reboot.

The corrected common full reboot then observed disconnect and reconnect in
38.5 seconds and returned `accepted: true`. Without device interaction, doctor
again reported connection ready, interaction unlocked, and unlocked-since-boot.
A second XCTest preparation installed/launched/health-checked the runner and
cleaned its lease. No blocking authentication dialog affected either launch;
whether a nonblocking presentation was briefly visible was not watched.

**Current — live-tested common facade:** Common runner preparation returned a
confirmed XCTest health-check. Common application launch, Home, interactive
SpringBoard snapshot, semantic Settings press, subsequent 17-node Settings
foreground snapshot, application termination, and owned-daemon recovery all
succeeded. The settled press had no semantic diff, so its own effect remained
`unverifiable`; the following snapshot is separate evidence. The matching
runner profile was observed as valid and long-lived. The capability result did
not emit the provider's device descriptor.

**Current — live-tested boundary, passcoded:** Before passcode removal, a full
reboot visibly required the local device passcode and the phone did not become
ordinary automation-ready before that first unlock. The new normalized
post-reboot `manual_first_unlock_required` result is unit-tested rather than
repeating a credential-bearing live reboot after converting the dedicated
phone to passcode-free operation.

## Recommended next work

- Exercise the normalized passcoded post-reboot result on a separate dedicated
  fixture if one is available; do not restore a credential merely to increase
  test coverage on the accepted passcode-free phone.
- Add a typed common bootstrap capability if more device families need pairing;
  until then keep iOS `pair` as an explicit native recovery operation.
- Live-test free Personal Team initial provisioning and automatic near-expiry
  rebuild independently of the accepted Developer Program runner cache and
  independently of passcode policy. The seven-day lifecycle and bounded cache
  refresh are implemented and unit-tested, not yet physically accepted.
- Source-review and live-test free Apple Configurator supervision only if
  repeatable erase-and-prepare or supervision-only policy becomes necessary.
- Decide physical/simulator identity and capability differences only after the
  physical recovery path is stable.

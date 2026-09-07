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
for runner preparation, development-app inventory, application install/launch/
termination/uninstall, direct URL payload delivery, transactional app-console
and system `os_log` capture, crash-report inventory/collection, bounded
app-container file exchange, semantic snapshot/press/fill, and Home. These
remain explicitly iOS operations rather than Android or desktop parity.

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

**Current — live-tested application diagnostics:** The platform wrapper and
common facade listed development applications, delivered an HTTPS payload
directly to the installed TomConnect development bundle, captured a bounded
window of application stdout/stderr, and copied one bounded file into and back
out of its application data container. The copy-to readback hash confirmed the
device-side effect; copy-from independently matched the source hash. A
following XCTest snapshot confirmed that the named application was available
for semantic observation, but direct payload delivery deliberately does not
claim that iOS system routing or an associated-domain decision was observed.

The required extension then adopted libimobiledevice 1.4.0 solely for its
physical-device `os_trace_relay` stream. A private worker retained a bounded
tail, common collection produced a create-only system-log artifact, and
transactional cleanup stopped and discarded an intentionally uncollected
stream. CoreDevice's native `systemCrashLogs` domain supplied bounded crash
inventory and copied one existing `.ips` report without removing it. Finally,
common uninstall removed the exact TomConnect development bundle and a second
CoreDevice inventory confirmed its absence and platform-owned container
removal.

**Current — live-tested boundary, passcoded:** Before passcode removal, a full
reboot visibly required the local device passcode and the phone did not become
ordinary automation-ready before that first unlock. The new normalized
post-reboot `manual_first_unlock_required` result is unit-tested rather than
repeating a credential-bearing live reboot after converting the dedicated
phone to passcode-free operation.

**Current — live-tested Personal Team:** Initial setup and ordinary control
passed with seven-day profiles; see the [provider evidence](../research/providers/agent-device.md)
and [setup fixes](../platforms/ios/docs/setup.md#first-time-setup-failures).
Automatic renewal and two-Mac handoff remain untested.

## Diagnostic operation coverage

[Tactical 031](../docs/tactical/031-ios-adb-parity-operations.md) treated the
[Android family](android-family-control.md) as a source of debugging needs, not
an API checklist. Live CoreDevice and Agent Device evidence produced this iOS
surface:

| Debugging need | Current iOS outcome | Scope and evidence |
| --- | --- | --- |
| URL or deep-link delivery | Accepted/common | Direct CoreDevice payload delivery to one exact development-app bundle; delivery confirmed, resulting app effect unverifiable, iOS system routing not observed |
| Development-app inventory | Accepted/common | Privacy-minimized CoreDevice projection of developer-built, non-default applications; bounded to 256 records |
| Application logs | Accepted/common | Transactional start/collect window for application stdout/stderr; create-only artifact outside the public repository; 1 MiB default and 16 MiB maximum |
| App-container file exchange | Accepted/common | One bounded regular file per call in `appDataContainer`; copy-to effect confirmed by device readback hash and copy-from writes create-only |
| Process inventory | Limited/not exposed | CoreDevice returned hundreds of executable/PID rows without bundle identity; launch deltas were useful experimentally but a standalone common result would be noisy and weakly attributable |
| Uninstall | Accepted/common | Exact CoreDevice developer-built/removable preflight followed by uninstall and absence readback; live-tested by removing TomConnect as explicitly authorized |
| System `os_log` | Accepted/common | libimobiledevice 1.4.0 `os_trace_relay`, held in a transactional bounded private spool and collected as a create-only artifact; abandoned capture cleanup live-tested |
| Crash reports | Accepted/common | Bounded CoreDevice `systemCrashLogs` inventory and exact `.ips`/`.log`/`.txt` collection; reports remain on the phone |
| Genuine system URL routing | Deferred | Direct payload delivery bypasses the chooser/association decision; activate a link from another application and inspect the resulting foreground state when needed |
| Wake, keyguard, and PIN unlock | Intentional boundary | The passcode-free dedicated profile needs none; a passcoded phone remains human after reboot |
| Arbitrary shell or filesystem access | Unsupported | Stock iOS has no general shell route; the facade remains typed and container-scoped |

**Decision:** Grow iOS debugging operations from demonstrated application
workflows. Do not pursue Android-shaped parity when CoreDevice reports
different semantics or when the result would not improve diagnosis.

**Decision:** Keep log capture transactional. Start clears and restarts the
current application console; collect stops it and materializes a bounded local
artifact. This makes capture lifetime and cleanup explicit and avoids inline
log content in normalized JSON.

**Decision:** Compose one narrow libimobiledevice route with CoreDevice/XCTest.
Stable Homebrew libimobiledevice 1.4.0 exposes the missing `os_trace_relay`
service over the existing paired USB connection. It avoids the broader Python
runtime and iOS 17+ developer-tunnel surface of pymobiledevice3 for this use
case. Keep crash reports on CoreDevice rather than duplicating them through the
new dependency.

**Decision:** Treat direct URL payload delivery as a named-app launch input,
not proof of universal-link registration or iOS system routing. Preserve that
limitation in capabilities and results.

**Decision:** Treat wake, keyguard, PIN unlock, arbitrary shell, and
filesystem-wide access as intentionally without iOS counterparts.

**Open:** Correlate a newly induced TomConnect crash with its resulting `.ips`
report when a reinstallable debug build is available. Inventory and collection
are live-proven against an existing device report; deliberate crash generation
is consuming-application work.

## Recommended next work

- Use URL payloads, application logs, system logs, crash reports, inventory,
  lifecycle, and container exchange together in real TomConnect investigations.
- Add filters or logarchive capture only when an observed system-log workflow
  needs them; the accepted first surface deliberately captures a bounded raw
  window.
- Keep independently attributable process inventory deferred until a provider
  returns stable bundle association.
- Exercise the normalized passcoded post-reboot result on a separate dedicated
  fixture if one is available; do not restore a credential merely to increase
  test coverage on the accepted passcode-free phone.
- Add a typed common bootstrap capability if more device families need pairing;
  until then keep iOS `pair` as an explicit native recovery operation.
- Live-test Personal Team automatic near-expiry rebuild. Initial provisioning
  and ordinary control have passed; bounded cache refresh remains unit-tested
  rather than physically accepted.
- Source-review and live-test free Apple Configurator supervision only if
  repeatable erase-and-prepare or supervision-only policy becomes necessary.
- Decide physical/simulator identity and capability differences only after the
  physical recovery path is stable.

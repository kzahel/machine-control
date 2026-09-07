# iOS Control Research

Status: adopted physical-device testbed with a native device-hosted provider
shape.

## Current stack

**Current — adopted:** The authoritative
[`platforms/ios`](../../platforms/ios/README.md) keeps the agent on
an authorized Mac and treats the phone as a distinct target. CoreDevice and
`devicectl` own device discovery, lifecycle, application and file operations.
A signed persistent XCTest runner, currently driven through
[Agent Device](../providers/agent-device.md), supplies compact semantic
snapshots and actions; screenshots and gestures provide observation/action
fallbacks. Leases and recovery remain testbed responsibilities.

This placement is a first-class North Star implementation. A stock phone
cannot host the same resident process as a desktop VM, and forcing that shape
would discard mature platform-native facilities.

Apple's [physical pairing security
model](https://support.apple.com/en-gb/guide/security/secadb5b6434/1/web/1)
documents the ordinary local unlock, Trust, and passcode-confirmation path.
Apple's [Developer Mode automation
session](https://developer.apple.com/videos/play/wwdc2022/110344/?time=218)
separately identifies passcode-free devices as the supported automated setup
case. [Apple Configurator manual
preparation](https://support.apple.com/en-ca/guide/apple-configurator-mac/cad99bc2a859/mac)
can supervise without enrolling in device management, but that optional
erase-and-prepare route is not required for ordinary CoreDevice/XCTest control.
Apple's [developer-account
overview](https://developer.apple.com/help/account/basics/about-your-developer-account)
documents free Personal Team testing and its current seven-day App ID, device,
and installation-profile lifetime plus resource limits.

## Current direction

**Decision:** Preserve CoreDevice/XCTest/Agent Device rather than building a
replacement. Normalize inventory, authorization, target selection,
capabilities, results, evidence, and artifact handling with the desktop
experience.

**Current — live-tested:** The canonical adapter emits the common device-shaped
doctor, merges ordinary CoreDevice discovery with lower-level `devmodectl`
bootstrap visibility, and provides an exact-device pairing operation. A
passcode-free physical phone was explicitly paired, reported physical/paired/
wired/tunnel-connected with Developer Mode enabled, and completed XCTest runner
preparation.

The corrected leased full reboot does not delegate effect observation to
CoreDevice's premature `--wait-for-device` result. It separately observed the
same phone disconnect and reconnect in 38.5 seconds; the common operation
returned accepted with `passcodeRequired: false`, `unlockedSinceBoot: true`, no
interaction gate, and ready connection/interaction. XCTest preparation passed
again without local device interaction. Passcode-free unattended reboot
recovery is therefore accepted for this combination.

**Current — live-tested common operations:** A bounded `ios` family now maps
common target selection to typed CoreDevice/XCTest operations. Runner prepare,
Settings launch, Home, interactive semantic snapshot, a Settings selector
press, a separate foreground snapshot, termination, and daemon recovery passed
on the passcode-free phone. Results kept delivery separate from effect and did
not expose the provider's device descriptor. Development-app inventory, direct
URL payload delivery to TomConnect, transactional application-console capture,
and bounded app-container copy also passed through both the platform wrapper
and common facade. Copy-to effect was confirmed by device readback hash;
copy-from independently matched the source file.

**Current — source-reviewed and unit-tested signing lifecycle:** The adapter
observes the exact matching cached runner's embedded provisioning dates.
Personal Team policy refreshes matching rebuildable derived products within 48
hours of expiry because Agent Device 0.20.5's cache key does not include profile
expiration. The current accepted runner uses a long-lived Developer Program
profile. Personal Team initial provisioning and ordinary control are now
live-tested through the [adopted provider](../providers/agent-device.md);
automatic renewal remains a live-test gap.

**Current — boundary:** A passcode-protected phone remains supported after its
local first unlock. Its full reboot restores Apple's local passcode gate; the
adapter does not enter the credential and reports protected interaction plus
`manual_first_unlock_required`. That normalized post-reboot projection is
unit-tested; the earlier phone state live-demonstrated the passcode screen and
need for local first unlock.

## Route comparison for diagnostic operations

The [Android family](android.md) supplied diagnostic use cases, while live iOS
evidence determined the actual surface. See the accepted, limited, and deferred
outcomes in the
[topic](../../topics/ios-device-control.md#diagnostic-operation-coverage).
Available routes per operation are:

| Operation | CoreDevice `devicectl` | Agent Device 0.20.5 | libimobiledevice / pymobiledevice3 |
| --- | --- | --- | --- |
| URL / deep-link payload | `device process launch --payload-url URL BUNDLE_ID`; requires the target bundle | `open <url>` wraps the same flag once the app bundle is known; XCTest-backed open rejects URLs | Not needed |
| App stdout/stderr | `device process launch --console` attaches and waits | `logs clear --restart` relaunches through `--console`; `logs stop` returns a file | Not needed |
| System `os_log` stream | None | None | `idevicesyslog` or `pymobiledevice3 syslog live`; both stream from a paired USB device |
| Uninstall | `device uninstall app BUNDLE_ID` | Not exposed for physical iOS | Alternative exists, not needed |
| Installed apps / processes | `device info apps`, `device info processes` | Session-scoped only | Alternative exists, not needed |
| File copy | `device copy to|from` with `--domain-type appDataContainer --domain-identifier BUNDLE_ID` | None | AFC routes; broader but a second dependency |
| Arbitrary shell | None | None | None on stock iOS |
| Crash and diagnostics bundle | `device sysdiagnose`, `device notification` | Crash-log helpers exist, unreviewed | Crash report pull routes exist |

Evidence levels:

- CoreDevice development-app inventory and app-container copy:
  `live-tested` through the platform wrapper and common facade on the accepted
  phone. Process inventory remains `live-tested` only as an exploratory route;
  its rows lacked bundle identity and were not adopted. Uninstall remains
  `source-reviewed` because no safely reinstallable fixture was available.
- Agent Device URL payload delivery and application-console capture:
  `live-tested` through the platform wrapper and common facade with TomConnect.
  Direct payload delivery does not observe iOS system routing, and the console
  contains application stdout/stderr rather than system `os_log`.
- libimobiledevice and pymobiledevice3: `discovered` only. Neither is
  installed on the controller and neither has a provider dossier.

**Decision:** Prefer CoreDevice for every useful operation it covers, reached
through Agent Device where the pinned provider already owns the session and
wraps the same flag. Keep the common surface use-case driven: do not expose
weakly attributable process rows merely because the provider returns them.
Add a second provider dependency only if a concrete diagnosis proves that
application stdout/stderr is insufficient and system `os_log` is necessary.

**Open:** Decide whether physical and simulator routes share one stable
device-family identity with capability differences. Keep passcode, biometrics,
payments, account recovery, signing, and protected authorization visible as
distinct gates. Test a fresh passcoded post-reboot projection on a separate
fixture when available, and separately evaluate optional Apple Configurator
supervision. Physically accept free Personal Team near-expiry reprovisioning without conflating it with supervision or passcode
policy. Neither is required for the accepted passcode-free CoreDevice/XCTest
route.

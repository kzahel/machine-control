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

**Current — boundary:** A passcode-protected phone remains supported after its
local first unlock. Its full reboot restores Apple's local passcode gate; the
adapter does not enter the credential and reports protected interaction plus
`manual_first_unlock_required`. That normalized post-reboot projection is
unit-tested; the earlier phone state live-demonstrated the passcode screen and
need for local first unlock.

**Open:** Decide whether physical and simulator routes share one stable
device-family identity with capability differences. Keep passcode, biometrics,
payments, account recovery, signing, and protected authorization visible as
distinct gates. Test a fresh passcoded post-reboot projection on a separate
fixture when available, and separately evaluate optional Apple Configurator
supervision and free Personal Team signing/reprovisioning. Neither is required
for the accepted passcode-free CoreDevice/XCTest route.

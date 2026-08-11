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

## Current direction

**Decision:** Preserve CoreDevice/XCTest/Agent Device rather than building a
replacement. Normalize inventory, authorization, target selection,
capabilities, results, evidence, and artifact handling with the desktop
experience.

**Current — live-tested:** The canonical adapter now emits the common
device-shaped doctor and supports a leased full CoreDevice reboot with
wait-for-device. Pre-reboot physical observation was ready and minimized. The
first live common reboot did not rediscover the phone before the bounded wait;
subsequent CoreDevice and USB observation reported it absent. The lease was
released, readiness became unavailable, and no protected or outer fallback was
attempted. Unattended reboot recovery is therefore not accepted yet.

**Open:** Decide whether physical and simulator routes share one stable
device-family identity with capability differences. Keep passcode, biometrics,
payments, account recovery, signing, and protected authorization visible as
distinct gates. Diagnose the physical reconnect failure, classify the first
post-reboot XCTest authentication gate, and separately test passcode-free,
Apple Configurator-supervised recovery, and free Personal Team signing
profiles.

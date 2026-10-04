# UTM

Status: adopted macOS-hosted VM lifecycle provider; bounded source review and
live failure diagnosis of the bundled CLI.

## Scope and license

[UTM](https://github.com/utmapp/UTM) hosts virtual machines on macOS and iOS.
Machine Control uses its macOS CLI/AppleScript and QEMU guest-agent routes for
Windows and Linux appliances. It is a controller-host provider, not the
ordinary target-native semantic desktop provider.

The repository declares [Apache-2.0](https://github.com/utmapp/UTM/blob/main/LICENSE).
Its [license notice](https://github.com/utmapp/UTM#license) also identifies
(L)GPL dependencies, statically linked GStreamer plugins, QEMU-derived code,
and MIT/BSD frontend dependencies. The top-level license is not a blanket
license for all bundled components. No upstream code is copied here.

## Architecture and evidence

**Current — source-reviewed:** The
[CLI](https://github.com/utmapp/UTM/blob/v4.7.5/utmctl/UTMCtl.swift) uses Apple's
ScriptingBridge to access UTM. Per-VM commands first request the application's
`virtualMachines` collection. Failure here precedes guest dispatch and can
therefore affect unrelated commands and guests through the same host bridge.

**Current — live-tested failure:** The installed 4.7.5 CLI on macOS 26.6.2
aborted during read-only inventory after failing to load the scripting
definition. The installed dictionary remained readable using Apple's `sdef`.
Historical status-call reports showed the same `virtualMachines` selector
failure. The observed process carried an App Sandbox entitlement; whether
sandboxing, application registration, or another OS interaction causes the
load failure has not been isolated. Provider-owned diagnosis and reproduction
instructions live in [UTM diagnostics](../../providers/utm/README.md).

**Decision:** Retain metadata at the subprocess boundary, including signal and
child PID, rather than losing failures in readiness probes that suppress
stderr. Preserve guest-effect verification, exact target claims, and existing
outer-route boundaries.

**Open:** Isolate the scripting-definition failure across UTM/macOS versions
and launch contexts. Establish a tested repair before recommending upgrades,
registration changes, or process restarts. Diagnostic coverage currently
excludes direct CLI calls, AppleScript, and Python factory-stage probes.

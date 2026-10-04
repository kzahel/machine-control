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
failure. Direct AppleScript inventory and a background LaunchServices reopen also
returned `-600` while the UTM process remained alive with an idle event loop.
This places the failure at the host application automation endpoint rather
than a particular guest power state. The reason for that endpoint failure
has not been isolated. Provider-owned diagnosis and reproduction
instructions live in [UTM diagnostics](../../providers/utm/README.md).

**Decision:** Retain metadata at the subprocess boundary, including signal and
child PID, rather than losing failures in readiness probes that suppress
stderr. Preserve guest-effect verification, exact target claims, and existing
outer-route boundaries.

**Current — live-tested mitigation:** An AppleScript inventory-health probe
refuses the observed broken endpoint before launching the CLI. Common doctor
completed without new CLI crash reports. Library recovery no longer equates
every failed status query with an unloaded library or repeats a crashing CLI.
Python factory-stage probes share the health guard.

**Current — retained-appliance control:** A fresh ARM64 Linux deployment
observed an operation-unavailable execution error followed by an absent
completion record even though pinned SSH remained usable. This does not
identify an upstream root cause. The owned Linux adapter can explicitly
select UUID-pinned SSH administration/transfer after exact guest-agent key
discovery; UTM retains lifecycle and address discovery. Fresh Windows and
Linux appliances passed disk-only boot and common resident conformance, and
remain retained. See [Tactical 090](../../docs/tactical/090-retained-desktop-appliance-rebuild.md).

**Open:** Isolate the endpoint failure across versions and launch contexts.
The guard does not restore automation or eliminate a failure between probe
and dispatch. Establish a tested repair before recommending upgrades,
registration changes, or process restarts. Diagnostic logging still excludes
direct CLI calls, AppleScript, and Python factory-stage probes.

# iOS Device Testbed

`ios-device-testbed` is a project-neutral CLI for diagnosing and safely driving
a stock physical iPhone from a Mac. It wraps a pinned
[Agent Device](https://github.com/callstack/agent-device) XCTest runner with
explicit hardware selection, paid-team signing settings, isolated daemon state,
private configuration, and a recoverable exclusive lease.

This directory is the canonical public source. The former
`ios-device-testbed` repository is retained only as legacy history and a
possible future generated distribution.

Consuming repositories own their application builds, fixtures, and assertions.
This repository owns physical-device selection, readiness, installation,
automation sessions, screenshots, input, and recovery.

The validated local target is an iPhone SE (3rd generation) on iOS 26.6,
controlled from Apple-silicon macOS with Xcode 26.6 and a paid Apple Developer
Program team. The CLI is intentionally macOS-only because physical-iOS XCTest
automation depends on Xcode.

## Install

Prerequisites and one-time phone preparation are in [docs/setup.md](docs/setup.md).
Install the pinned host dependency:

```bash
cd ~/code/machine-control/platforms/ios
pnpm install
cp config.example config.local
```

Edit ignored `config.local` with a unique device name, Apple Developer team ID,
and dedicated runner bundle ID. Do not put the phone's UDID, account details,
profiles, certificates, private keys, or local signed products in Git.

Then validate and prepare the runner:

```bash
bin/ios-device probe
bin/ios-device doctor
bin/ios-device prepare
bin/ios-device doctor
```

`probe`, `status`, and `doctor` are read-only with respect to the phone.
`prepare` builds, signs, installs, starts, and health-checks the XCTest runner,
then stops the dedicated daemon while retaining its cached signed products.

## Normal agent workflow

Use one transactional session for a multi-step flow. It holds the device lease,
provides one Agent Device session name to child commands, and cleans up the
runner and daemon on exit:

```bash
~/code/machine-control/platforms/ios/bin/ios-device session -- bash -lc '
  set -euo pipefail
  ios="$IOS_DEVICE_TESTBED_ROOT/bin/ios-device"
  "$ios" launch com.example.app
  "$ios" snapshot -i
  "$ios" press "role=button label=Settings" --settle
  "$ios" screenshot /tmp/example-settings.png
'
```

Prefer accessibility snapshots, refs, selectors, waits, and assertions. Use an
on-demand screenshot and coordinate `tap` only when the UI has insufficient
semantics:

```bash
bin/ios-device snapshot -i
bin/ios-device tap 300 500
bin/ios-device swipe 300 900 300 300
```

Agent Device's refs are snapshot-scoped. Take a fresh snapshot after navigation
and do not guess stale refs.

## Project-owned build and testbed-owned install

Build the `.app` in its consuming repository. Pass the already-signed device
product to the testbed:

```bash
bin/ios-device install /absolute/path/Debug-iphoneos/Example.app
```

`install` accepts an explicit `.app` directory only. The testbed does not run a
project's build, release, or publishing scripts.

Use `launch` when an agent needs XCTest control. It opens the app in the active
automation session. Use `normal-launch` after a session when a human should see
the application outside Apple's **Automation Running** presentation:

```bash
bin/ios-device normal-launch com.example.app
```

## Commands

```text
probe [--json]                 Stable read-only connection state
status [--json]                Device, matching build-cache, and lease status
doctor [--json]                Xcode, signing, device, unlock, and runner checks
prepare                        Build/sign/install/health-check the XCTest runner
reboot [--timeout SECONDS]     Full CoreDevice reboot and reconnect wait
session -- COMMAND             Run under an exclusive recoverable device lease
recover [--force]              Stop the dedicated daemon and clear a stale lease

install PATH.app               Install an already-built signed application
normal-launch BUNDLE_ID        Launch outside XCTest automation

launch APP                     Open and bind an app for automation
terminate [APP]                Close the active or named app
snapshot / find / get          Inspect semantic UI
wait / assert                  Verify state
press / tap / fill / type      Interact by ref, selector, text, or coordinates
scroll / swipe / longpress     Gesture input
home / app-switcher            System navigation
screenshot / record / logs     Evidence and diagnostics
agent -- ARGS                  Explicit pinned Agent Device passthrough
```

The common commands add `--platform ios` and the selected physical device
automatically. The `agent` escape hatch does the same; use it only when the
pinned Agent Device help documents a command that the wrapper does not alias.

`doctor --json` emits the minimized `machine-control-doctor/v0` device
projection used by common `target status`, `target doctor`, and `target
capabilities` calls. `reboot` stops only testbed-owned runner state,
holds the device lease, requests a full CoreDevice reboot, and waits for the
physical phone to return. Reconnection does not imply that XCTest is usable:
the common doctor keeps runner authentication `unverified_until_launch` and
does not automate a passcode or biometric gate.

## State and trust boundary

The wrapper uses `~/.ios-device-testbed` by default:

```text
~/.ios-device-testbed/
  lease.json                   private exclusive-device journal
  agent-device/                isolated daemon, session, and log state
```

This is deliberately separate from `~/.agent-device`. The daemon inherits
signing variables only when it starts, so isolating and owning its lifecycle
prevents an unrelated bare `agent-device` invocation from reusing the wrong
Apple team or runner bundle configuration.

Agent Device 0.20.5 keeps its signed Apple build products in the user-wide
`~/.agent-device/apple-runner/derived` cache. Its cache key separates relevant
build/signing inputs; the testbed owns daemon and lease isolation, not that
upstream compilation cache. `recover` never deletes the shared cache.

Screenshots, recordings, logs, and session state may contain private UI,
credentials, device identifiers, or request data. Keep them local and review
before sharing. The CLI redacts identifiers from its own summaries, but raw
Agent Device passthrough output may contain provider details.

Protected authentication and security surfaces remain human gates: passcodes,
biometrics, Apple Pay, CAPTCHAs, account recovery, and safety-warning bypasses.
See [docs/capabilities.md](docs/capabilities.md),
[docs/known-issues.md](docs/known-issues.md), and
[docs/recovery.md](docs/recovery.md).

The first standalone physical-device acceptance after the wrapper refactor is
recorded in
[docs/standalone-device-validation-2026-08-04.md](docs/standalone-device-validation-2026-08-04.md).

## Development

```bash
pnpm check
bin/ios-device probe
bin/ios-device doctor
```

Physical-device lifecycle changes also require `prepare` and one transactional
session. Keep Agent Device pinned until an upgrade has been tested against an
ordinary app, SpringBoard, keyboard input, screenshots, runner recovery, and a
rebooted physical phone.

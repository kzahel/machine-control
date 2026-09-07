---
name: ios-device
description: Safely inspect, install, launch, diagnose, and automate applications on a physical iPhone testbed from macOS. Use for real-device iOS QA, accessibility-driven UI control, URL delivery, bounded application and system logs, crash reports, uninstall, app-container file exchange, SpringBoard interaction, screenshots, input, app installation, device readiness diagnosis, or recovery of the dedicated XCTest runner.
---

# iOS Device Testbed

Operate the selected stock iPhone through the project-neutral wrapper in this
repository. Keep app builds and product assertions in the consuming project;
use this testbed for device readiness, installation, UI automation, evidence,
and recovery.

## Enter the testbed

Resolve the testbed root as two directories above this file. Invoke
`<testbed-root>/bin/ios-device`; never invoke bare `agent-device`. The wrapper
pins the tested version, selects the physical phone explicitly, supplies the
configured-team signing environment, isolates daemon state, and enforces one
owner.

Start every task with:

```bash
<testbed-root>/bin/ios-device probe
<testbed-root>/bin/ios-device doctor
```

If readiness is missing, read `<testbed-root>/docs/setup.md`. Read
`<testbed-root>/docs/known-issues.md` for a known symptom and
`<testbed-root>/docs/recovery.md` before manual runner cleanup. Do not
substitute a simulator when the task requires hardware.

If Developer Mode discovery sees the selected phone but CoreDevice pairing has
not converged, run `<testbed-root>/bin/ios-device pair`. Pair only the exact
configured device. Leave Trust confirmation and any configured passcode to the
human; never request the passcode through the agent transcript.

## Run an automation flow

Use one transactional session for every multi-step or mutating flow:

```bash
<testbed-root>/bin/ios-device session -- bash -lc '
  set -euo pipefail
  ios="$IOS_DEVICE_TESTBED_ROOT/bin/ios-device"
  "$ios" launch com.example.app
  "$ios" snapshot -i
  "$ios" press "role=button label=Settings" --settle
  "$ios" wait "label=Settings"
  "$ios" screenshot /tmp/example-settings.png
'
```

The session holds the exclusive lease, gives all child commands one upstream
session, and closes the runner and daemon on exit. Run mutating commands
serially. Use `recover` only after confirming the recorded owner is gone; use
`recover --force` only with explicit knowledge that interrupting it is safe.

## Build, install, and launch

Build and sign the device `.app` in its owning project. Install only the
explicit product:

```bash
<testbed-root>/bin/ios-device install /absolute/path/Example.app
```

Use `launch <bundle-id-or-app>` inside a session for XCTest automation. Use
`normal-launch <bundle-id>` after the session when a human needs the ordinary
non-automation presentation. Do not make the testbed run consuming-project
build, release, or publishing scripts.

## Diagnose an application

Use the common `ios` family for normalized development-app inventory, direct
URL payload delivery, bounded application stdout/stderr and system `os_log`,
crash reports, uninstall, and single-file container exchange. Keep live log
capture inside the surrounding transactional session:

```bash
mc=/path/to/machine-control/bin/machine-control
"$mc" --target ios ios application list
"$mc" --target ios ios application open-url com.example.app \
  'https://example.test/debug' --relaunch
"$mc" --target ios ios logs start
"$mc" --target ios ios snapshot --interactive
"$mc" --target ios ios logs collect /tmp/example-app.log
"$mc" --target ios ios system-logs start
"$mc" --target ios ios system-logs collect /tmp/ios-system.log
"$mc" --target ios ios crashes list --match Example
"$mc" --target ios ios crashes collect \
  DiagnosticLogs/Example.ips /tmp/Example.ips
"$mc" --target ios ios application copy-from com.example.app \
  /tmp/export.json /tmp/export.json
```

`open-url` sends a payload to the named bundle; it is not evidence that iOS
selected that bundle through universal-link routing. Application logs exclude
system `os_log`, while `system-logs` captures the broader and much noisier
`os_trace_relay`. Crash reports come from CoreDevice's `systemCrashLogs`
domain and remain on the phone after collection. Container operations are
fixed to `appDataContainer`, accept one bounded file, and never provide general
device filesystem access. Keep all diagnostic output outside source
repositories.

## Inspect and interact

Prefer semantic control in this order:

1. Read with `snapshot`, `get`, `find`, or `assert`.
2. Refresh interactive refs with `snapshot -i` only when refs are needed.
3. Act with a stable selector or current ref using `press`, `fill`, `scroll`,
   `swipe`, `longpress`, or `type`.
4. Use `--settle` on planned `press`, `fill`, or `longpress` actions.
5. Wait for expected state, then take a fresh snapshot after navigation.
6. Capture an on-demand `screenshot` when visual evidence is useful.
7. Fall back to coordinate `tap` or `swipe` only when accessibility semantics
   are insufficient.

Treat upstream refs as snapshot-scoped; never mutate through a stale ref. If a
keyboard obscures a target and dismissal is unsupported, scroll the target
into view. Use `agent -- <documented-command>` only for a pinned Agent Device
capability not exposed as a wrapper alias.

## Respect security and privacy boundaries

Leave passcodes, Touch ID, Face ID, Apple Pay, CAPTCHAs, account recovery,
developer trust prompts, and security-warning bypasses to a human. Do not
weaken Developer Mode, pairing, signing, Keychain, or macOS privacy controls.
For a deliberately passcode-free test phone, unattended reboot is an authorized
device profile rather than an authentication bypass. For a passcode-protected
phone, stop when doctor reports `manual_first_unlock_required` and request the
one local first unlock.

Never commit or publish a device identifier, Apple account, signing team,
certificate, private key, provisioning profile, signed app, `config.local`,
session state, log, screenshot, or recording. Captured evidence can contain
private UI and request data; review it before sharing. Keep screenshots and
other temporary evidence outside source repositories unless the user
explicitly requests a reviewed fixture.

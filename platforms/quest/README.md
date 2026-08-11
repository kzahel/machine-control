# Quest Testbed

`quest-testbed` is a project-neutral CLI for diagnosing and safely driving a
physical Meta Quest over Android Debug Bridge. It selects an authorized Quest,
reports device and battery state, installs and launches already-built APKs,
collects screenshots and logs, and wraps tests in a recoverable headset lease.

This directory is the canonical public source. The former `quest-testbed`
repository is retained only as legacy history and a possible future generated
distribution.

The consuming project owns its build, application arguments, assets, host XR
runtime, and acceptance assertions. This repository owns the physical-device
contract: authorization, selection, power/proximity preparation, recovery,
and teardown.

## Prerequisites

1. Enable Developer Mode and USB debugging on the Quest.
2. Install Android SDK Platform Tools on the controller.
3. Connect the headset over USB. On Linux, install the appropriate Oculus USB
   udev rule and ensure the user can access the device.
4. Put on the headset, accept the controller's RSA prompt, and choose
   **Always allow from this computer**.
5. Install Python 3.10 or later.

Android documents the RSA authorization and serial-selection behavior in its
[ADB guide](https://developer.android.com/tools/adb). ADB authorization is
per controller; this repository contains no device credentials or serials.

## Start safely

```bash
~/code/machine-control/platforms/quest/bin/quest doctor
~/code/machine-control/platforms/quest/bin/quest status
~/code/machine-control/platforms/quest/bin/quest probe
```

On Windows PowerShell:

```powershell
& "$HOME\code\machine-control\platforms\quest\bin\quest.ps1" doctor
```

Pass `--serial SERIAL` or set `QUEST_TESTBED_SERIAL` when multiple Quest
headsets may be attached. The CLI rejects emulators and unrelated Android
devices rather than operating the first device returned by ADB.

## Transactional test session

The preferred interface is `session`. It records the original Android
settings on the Quest before changing them, installs any requested reverse
ports, wakes the headset, runs the project command, and restores the settings,
proximity sensor, package state, reverse ports, and headset sleep state on
every ordinary exit path.

```bash
bin/quest session \
  --stop-package com.example.game \
  --reverse tcp:9757=tcp:9757 \
  -- ./project-owned-headset-test.sh
```

The child receives `QUEST_TESTBED_SERIAL`, `ANDROID_SERIAL`,
`QUEST_TESTBED_ADB`, and `QUEST_TESTBED_SESSION_ACTIVE=1`.

For a project script that must build before waking the headset, use an external
lease and pass the script's PID. Always arrange `end` in the script's cleanup
trap or `finally` block:

```bash
quest=~/code/machine-control/platforms/quest/bin/quest
serial="$($quest serial)"
$quest --serial "$serial" begin --owner-pid "$$" \
  --stop-package com.example.game
trap '$quest --serial "$serial" end' EXIT INT TERM
```

If a controller or script dies after preparation, the journal remains at
`/data/local/tmp/quest-testbed-session.json`. `doctor` reports it. A later
lease from the same controller automatically repairs a dead-PID external or
transactional lease. Use `recover` explicitly for other cases; recovering a
foreign-controller journal requires `--force` so an active test is not
silently disrupted.

## Device commands

```text
serial                         Print the selected Quest ADB serial
probe                          Print one stable lifecycle state
status [--json]                Report device, battery, settings, and lease state
doctor [--json]                Diagnose ADB, authorization, safety, and recovery
session [options] -- COMMAND   Run a transactional headset test
begin [options]                Start a recoverable external-script lease
end                            Restore this controller's lease and sleep
recover [--force]              Restore an interrupted lease
wake | sleep                   Standard Android wake/sleep keys
dismiss-dialogs                Dismiss known Meta test-blocking system panels
install APK                    Install an already-built APK
launch PACKAGE [options]       Launch by component, intent, URI, or launcher
stop PACKAGE                   Force-stop one explicit package
screenshot OUTPUT              Capture the current headset display
logcat OUTPUT [--package P]    Save a bounded log snapshot
push LOCAL REMOTE              Copy a file or directory to the Quest
pull REMOTE [LOCAL]            Copy a file or directory from the Quest
reverse LOCAL REMOTE           Install an ADB reverse mapping
reverse-remove LOCAL           Remove an ADB reverse mapping
shell [--] COMMAND [ARG...]    Run an explicit Quest shell command
```

`sleep` means Android sleep/standby, not a full shutdown. Android defines
`KEYCODE_SLEEP` and `KEYCODE_WAKEUP` as idempotent sleep and wake keys. A full
shutdown is intentionally absent because ADB cannot power a shut-down Quest
back on.

## Safety policy

- The default minimum battery threshold is 15% when the headset is not
  charging. Override it with `--min-battery` or
  `QUEST_TESTBED_MIN_BATTERY` only for a deliberate test.
- Cleanup always normalizes `debug.oculus.disableProximity` to `0`, broadcasts
  proximity-open, and sleeps unless `--keep-awake` was explicit.
- Package cleanup is opt-in and exact. There is no generic process-name sweep.
- The Oculus proximity property and VR power-manager broadcasts are
  Meta-specific shell hooks rather than stable public Android APIs. They are
  capability-probed and best effort; standard ADB transport and key events
  remain the recovery path.
- Do not commit serials, account data, private APKs, or controller-local
  configuration. `config.local` is ignored for environment overrides.

## Environment

| Variable | Purpose |
| --- | --- |
| `QUEST_TESTBED_SERIAL` | Preferred Quest ADB serial |
| `ANDROID_SERIAL` | Standard ADB serial fallback |
| `QUEST_TESTBED_ADB` | Explicit ADB executable |
| `QUEST_TESTBED_MIN_BATTERY` | Default unpowered battery threshold |
| `QUEST_TESTBED_STATE_DIR` | Controller-local lock directory |

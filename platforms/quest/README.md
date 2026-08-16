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

### Recover a missing ADB authorization prompt

An `unauthorized` ADB state proves that the controller has requested
authorization; it does not prove that Horizon OS actually displayed the RSA
dialog. If the headset is visible over USB and `quest doctor` reports
`unauthorized`, but no prompt appears after reconnecting or restarting ADB:

1. Disconnect USB.
2. In the Meta Horizon mobile app, turn Developer Mode off for the headset and
   then turn it on again.
3. Reconnect USB while the headset is awake and at the Home environment.
4. Re-run `quest doctor`, accept the RSA prompt, and select **Always allow from
   this computer**.
5. Re-run `quest doctor` and require the authorization check to pass. If the
   prompt is still absent, reboot the headset and repeat the reconnect once.

Do not delete or regenerate the controller's `~/.android/adbkey` as a routine
recovery step. That changes the controller identity and invalidates its grants
on every Android-family target that uses the same key.

**Current — live-tested 2026-08-16:** A Quest enumerated over USB and remained
`unauthorized` while repeated device reconnects, ADB server restarts, and a
Horizon OS system update failed to display the RSA dialog. The controller key
had not changed. Turning Developer Mode off and on in the Meta Horizon mobile
app restored the prompt; accepting it returned every Quest doctor check to
pass.

AOSP expires inactive user-approved ADB keys according to
`adb_allowed_connection_time`; its
[framework default is `604800000` ms (seven days)](https://android.googlesource.com/platform/frameworks/base/+/4e984e55033439223fb45e91a561b85e57248067/core/java/android/provider/Settings.java),
and its
[ADB key store applies that window to “Always allow” grants](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/adb/AdbDebuggingManager.java).
The live Quest returned an unset value for that global setting, consistent
with using a framework default. The incident did not measure the idle period
or inspect Meta's framework build, so seven-day expiration is a plausible
trigger, not a proven Horizon OS cause.

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

## Authenticated wireless ADB

Quest 3 can use Android's standard ADB-over-TCP route without root. Bootstrap
and bind it to the exact headset over an authorized USB connection:

```bash
quest wireless status
quest wireless enable
# USB may now be disconnected.
quest doctor
quest wireless disable
```

`wireless enable` requires the selected transport to be USB, confirms that
Horizon OS reports wireless ADB support and `ro.adb.secure=1`, refuses while a
Quest lease is active, accepts only a private non-link-local `wlan0` address,
starts port 5555, connects, and requires the network endpoint to report the
same device identity and Quest profile. It then writes the endpoint and
identity to a mode-`0600` controller-local record under
`QUEST_TESTBED_STATE_DIR`; no address or serial enters the repository.

When the configured USB serial is absent, ordinary Quest commands reconnect
the recorded endpoint and revalidate its authorization, identity, and headset
profile before using it. A missing, unauthorized, changed, or non-Quest
endpoint fails closed. `wireless disable` returns `adbd` to USB mode and clears
the local record. Enable and disable both refuse during an active test lease so
transport changes cannot strand lease cleanup.

This is a temporary trusted-LAN route. The current Quest exposes neither a
persistent TCP port nor a supported Horizon OS pairing workflow through this
CLI; after an `adbd` or headset restart, reconnect USB and run `wireless
enable` again. Android documents the underlying
[`adb tcpip 5555` workflow](https://developer.android.com/tools/adb#wireless).
Do not forward the listener beyond a trusted local network.

**Current — live-tested 2026-08-16:** The updated Quest reported wireless and
QR-pairing support, secure ADB, no active wireless setting, and no persistent
TCP property. `wireless enable` established port 5555, matched the wireless
endpoint to the USB-observed device identity, and passed the full Quest doctor
through that endpoint. The controller-local state file had mode `0600`.
An isolated host ADB server with no USB transport then ran the ordinary pinned
common doctor: it reconnected the receipt, reported `transport: wireless`, and
passed every check. The physical cable remained attached during that isolated
inventory proof.

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
wireless status [--json]       Report support, transport, and verified state
wireless enable [--json]       Enable and verify temporary secure ADB over Wi-Fi
wireless disable [--json]      Return to USB-only ADB and clear local state
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

`doctor --json` emits a minimized `machine-control-doctor/v0` document for the
common outer `target status|doctor|capabilities` surface. It identifies Quest
as an Android-family XR headset while preserving headset-specific lifecycle,
proximity, battery, and lease policy here. It omits the serial, controller, and
lease-owner details retained by the human-oriented doctor.

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
| `QUEST_TESTBED_STATE_DIR` | Controller-local locks and private wireless endpoint state |

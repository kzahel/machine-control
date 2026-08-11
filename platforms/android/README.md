# Android Handheld Testbed

`android-device` is the canonical project-neutral adapter for an authorized
physical Android phone or tablet. It keeps Android Debug Bridge as the native
transport and adds exact handheld selection, minimized common readiness,
keyguard/user-storage observation, bounded lifecycle and deployment commands,
and a dedicated one-shot PIN unlock path.

This is an Android-handheld profile, not a generic policy for every ADB target.
Quest retains headset policy in [`../quest`](../quest/README.md); ChromeOS ARCVM,
emulators, TVs, watches, and automotive targets require their own lifecycle and
safety profiles. Neutral executable discovery, device enumeration, shell, and
power parsing live in [`../../providers/adb`](../../providers/adb).

## Setup

Install Android SDK Platform Tools and authorize the controller's ADB RSA key
on the dedicated test device. When more than one eligible handheld can be
attached, set `ANDROID_TESTBED_SERIAL` in ignored private inventory or pass
`--serial` locally. `ANDROID_SERIAL` is accepted as the standard fallback.

For PIN unlock, install a JDK and Android SDK platform/build tools. The adapter
builds the checked-in one-shot helper into the private state directory before
opening the secret channel. No compiled helper, credential, serial, or signed
application belongs in Git.

```bash
platforms/android/bin/android-device probe
platforms/android/bin/android-device doctor
platforms/android/bin/android-device status
```

The common outer surface is:

```bash
bin/machine-control --target android target status
bin/machine-control --target android target doctor
bin/machine-control --target android target capabilities
bin/machine-control --target android target reboot
```

Concrete target availability and selectors remain private inventory. When no
private provider is active, the portable default can select exactly one
authorized eligible handheld.

## Commands

```text
probe [--json]                 Stable read-only availability
status [--json]                Boot, wake, user-storage, and keyguard state
doctor [--json]                Human checks or machine-control-doctor/v0
serial                         Print the locally selected ADB serial
reboot [--timeout SECONDS]     Full reboot, wait, and prove a new boot generation
wake                           Send Android's idempotent wake key
dismiss-keyguard               Request ordinary keyguard dismissal
unlock [--json]                Read and submit one PIN through dedicated stdin
install PATH.apk               Install or replace one explicit APK
launch PACKAGE                 Resolve and launch one explicit package
stop PACKAGE                   Force-stop one explicit package
screenshot OUTPUT              Save one device-local display capture
logcat OUTPUT                  Save a bounded recent log snapshot
shell -- COMMAND [ARG...]      Run one explicit ADB shell command
```

`dismiss-keyguard` only asks Android to dismiss the keyguard; a secure lock
screen still requires its credential. `unlock` is the protected operation.

## PIN unlock boundary

Run `unlock` directly from a supervised terminal or pipe it from an authorized
secret source. Never put the PIN on the command line:

```bash
platforms/android/bin/android-device unlock --json
```

Before reading anything from standard input, the adapter requires:

- one exact authorized physical handheld and a stable boot generation;
- completed boot and a secure PIN credential type;
- a visible PIN field discovered through UIAutomator;
- an observed zero failed-password wipe threshold; and
- a successfully built and staged one-shot helper.

The helper runs once as the already-authorized Android shell identity, reads 4
to 16 ASCII digits from standard input, injects digit and Enter key events in
that process, emits no output, and clears its mutable buffer best effort. The
host clears its buffer and removes the staged helper. The result reports only
delivery, independently re-observed keyguard/user-storage effect, uncertainty,
and zero retries. A failed or unknown outcome is never submitted again
automatically.

This route does not clear or replace the credential, modify device policy,
weaken lockout/biometrics, bypass ADB authorization, or support password and
pattern credentials.

## State and safety

Private controller state defaults to
`~/.local/state/android-device-testbed` (or the platform equivalent) and
contains only a local mutation lease and compiled helper cache. Override it
with `ANDROID_TESTBED_STATE_DIR` in private configuration.

Screenshots, logcat, shell output, applications, and UI state can contain
private data. Keep artifacts local and review them before sharing. Common
doctor output deliberately omits the serial, model, account/user names,
controller paths, and configuration values.

## Development

```bash
cd platforms/android
python3 -m unittest discover -s tests -v
python3 -m compileall -q android_device.py tests ../../providers/adb
```

Credential changes require helper build/start validation and refusal tests.
Real PIN delivery requires a supervised dedicated test device and the correct
credential; never add a wrong-PIN acceptance case.

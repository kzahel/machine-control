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
unlock [--stdin] [--json]      Submit one PIN from its configured file or stdin
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

Private inventory can declare a `pin` credential locator and expose its path
as `ANDROID_TESTBED_PIN_FILE`. The value belongs in an untracked controller-local
file, mode `0600`, inside a caller-owned mode-`0700` directory on POSIX. The
adapter requires an explicit device selector, rejects symlinks and unsafe or
nonregular files, and opens the secret only after unlock preflight. It accepts
one 4–16 digit PIN with an optional newline. Only the path enters the environment;
neither the path nor the credential appears in the unlock result.

With that locator configured, an agent can request unlock by target name:

```bash
bin/machine-control --target phone testbed -- unlock --json
```

Without a locator, `unlock` uses a hidden terminal prompt or dedicated stdin.
Use `--stdin` to explicitly override a configured file. Never put the PIN on the
command line:

```bash
platforms/android/bin/android-device unlock --stdin --json
```

Before opening a configured secret file or reading standard input, the adapter
requires:

- one exact authorized physical handheld and a stable boot generation;
- completed boot and a secure PIN credential type;
- a visible PIN field discovered through UIAutomator;
- an observed zero failed-password wipe threshold; and
- a successfully built and staged one-shot helper.

When the legacy policy dump omits the threshold, a temporary read-only
shell-UID probe queries `DevicePolicyManager` for the exact foreground user.
Unknown, denied, changed-user, and nonzero results still refuse before the PIN
is read. UIAutomator discovery uses a mode-0600 temporary hierarchy, removed
in `finally`, and requires one known SystemUI password field with no text.
Non-secret ADB and build subprocesses receive no stdin; only explicit helper
delivery receives the credential bytes. Explicitly redirecting a private PIN file
into `unlock --stdin` therefore preserves it through preflight too.

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

**Current — live-tested, 2026-10-25:** on a physical API-37 handheld, the common
CLI adapter escape hatch unlocked a secure PIN keyguard using a private host
file redirected into dedicated stdin. The corrected helper delivered once;
keyguard and user-storage observations confirmed unlock, and a subsequent
read-only doctor independently reported interaction unlocked. The PIN was never
displayed or retained in evidence, and device-side temporary files were removed.
This validates ordinary screen unlock after user storage is available, not
first unlock after reboot or broader OEM coverage.

## Reboot and first unlock

`reboot` waits for ADB reconnection, completed OS boot and a new boot generation.
It does not automatically unlock the screen. A configured controller-held PIN
remains available while the phone's credential-encrypted user storage is locked.
The unlock operation does not require that storage to be unlocked beforehand;
it can attempt first unlock once authorized ADB, native policy observation and
the known PIN surface are available. Successful effect requires both keyguard
and user storage to report unlocked afterward.

This route is unit-tested for initially locked user storage, but first unlock
after a real reboot has not been accepted on hardware. ADB availability and
protected-surface behavior still need that separate physical test. Boot
completion alone is not evidence that applications or user storage are ready.

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

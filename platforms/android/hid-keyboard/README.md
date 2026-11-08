# Android handheld as a Bluetooth keyboard and mouse

`MC HID` turns an unrooted Android 12+ handheld into a classic Bluetooth HID
keyboard and mouse for another machine, driven by agents over ADB. It exists
so an agent can type into a target that has no other input path during
bootstrap or recovery, without a person at the target's keyboard. The app is
agent-first: a person gets only a status line, a Discoverable button, and an
in-a-pinch touchpad. It has no text field, so no IME, suggestion strip, or
autofill ever sees agent text.

An independent review through a separate agent session found 16 issues
(two high: no host binding, Caps Lock ignored) and a re-review found 7 more;
all are addressed above. Design notes and the 2026-11-08 trials live in
[`topics/android-family-control.md`](../../../topics/android-family-control.md#planned-handheld-as-a-bluetooth-hid-keyboard).

## Pieces

- `HidService`: a `connectedDevice` foreground service. It registers one
  `BluetoothHidDevice` app with a combined descriptor (report 1: boot-style
  keyboard with LED output; report 2: five-button mouse with X, Y, wheel and
  horizontal pan), reconnects to the last host on start, and serves a
  loopback control socket.
- `MainActivity` and `TouchpadView`: status, Discoverable, Stop, and a
  touchpad. One finger moves, a tap left-clicks, two fingers scroll, a
  two-finger tap right-clicks; Left and Right are press-and-hold buttons for
  drags. Launching it from the launcher is a person's action: it starts the
  service and, with no saved host, requests two minutes of discoverability.
- `ArmActivity`: an invisible entry point for agents. Starting it requires
  `android.permission.DUMP`, which the ADB shell holds and ordinary apps do
  not, so other apps cannot rotate the grant or raise discoverability prompts.
- `Keymap` and `Reports`: pure Java, unit-tested. Text is translated in full
  before anything is sent, so unsupported characters are refused with no
  partial typing. Layouts: `us` and `dvorak` (the host's configured layout).
- `hidctl.py`: the host CLI. Text comes only from standard input.

## Authority and secrets

ADB access is the authority. On start, and on each `ARM` from the shell, the service
writes `{port, token, generation}` to `files/bridge.json` (mode 0600) in its
private storage. `hidctl.py` reads it with `run-as` (debug build), reaches the
port through `adb forward`, sends the token with each request, and removes the
forward afterwards. The token lasts one hour and is never printed, logged or
put in process arguments; nor is typed text.

Stop, in the notification or the app, is the operator's kill switch. It revokes
the grant and stops the service, and agents cannot re-arm (`stopped_by_operator`)
until a person taps Start in the app or someone runs `arm --override`
deliberately. Launching the app does not clear it, because any app can send
the launcher intent.

Every command first challenges the listener through a fresh forward: it sends
a random nonce without the token, and only a service holding the current
token can answer with `HMAC-SHA256(token, nonce)`. A grant left by a killed
process (for example after reinstalling) points at a dead port that another
app could even bind; the challenge fails there, nothing secret is sent, the
CLI re-arms, and the real request is sent exactly once. A listener that
answers but cannot prove the token is reported as a
`listener_failed_challenge` warning, since it may be a hostile app. Unauthenticated
connections get five seconds and one challenge, and any failure before
authentication closes them. Up to four connections are served at once, so
`status`, `cancel` and `release` work while a long `type` runs. Keyboard
requests never queue: a second `type` or `key` is refused with `busy`, and the
CLI sends `cancel` if its own request times out, so text is never typed after
the caller gave up.

## Build and install

JDK 17 and Android SDK 36. AGP 8.10.1 runs on Gradle 8.11.1 or later; any
existing wrapper works:

```sh
"$GRADLE_WRAPPER" -p platforms/android/hid-keyboard :app:testDebugUnitTest :app:assembleDebug :app:lint
python3 -m unittest discover -s platforms/android/hid-keyboard -p 'test_*.py' -v
platforms/android/hid-keyboard/hidctl.py --serial "$ANDROID_TEST_SERIAL" install
```

`install` replaces the debug APK, clears any stale grant, and grants the
Bluetooth and notification runtime permissions with `pm grant`. Stop other
HID-device apps first; Android allows one registered HID app at a time.

## Pairing

Pair once per host. Discoverability lasts two minutes; any device can try to
pair in that window, so keep it short and pair only on a controlled bench. ChromeOS (Floss) hides phone-class devices from its own
pairing UI and does not accept a first HID connection that the device starts,
so on a ChromeOS testbed with root SSH the host does the work:

```sh
hidctl.py --serial "$ANDROID_TEST_SERIAL" pair-floss --ssh CHROMEOS_ROOT_ALIAS
```

The sequence is: make the handheld discoverable (the CLI accepts the system
consent dialog), run inquiry on the host so Floss can page the handheld,
`CreateBond`, tap Pair on the handheld and `SetPairingConfirmation` on the
host, then `ConnectAllEnabledProfiles` so the host opens HID itself. It
taps Pair only on a prompt that names the host's adapter, and succeeds only if
the connected host is that adapter. It still accepts numeric comparison
without a person reading both codes, which is only appropriate on a controlled
testbed; the code is reported for the record.
Hosts whose pairing UI lists phones can instead pair from their own UI while
the handheld is discoverable.

After that the app reconnects to the saved host by itself when it starts.
`connect ADDRESS` asks for a connection explicitly.

`unplug --confirm-unpair` disconnects the host. Android implements HID
disconnect as a virtual-cable unplug, which also removes the bond on the
handheld, so pairing is needed again. There is deliberately no plain
`disconnect`.

## Use

`--host ADDRESS` (or `MC_HID_HOST`) makes every input request name the host it
is meant for; the service refuses with `wrong_host` if another bonded device is
the one connected. `type` and `key` require it unless `--any-host` is passed.
`release` and `cancel` work whichever host is connected.

```sh
S="--serial $ANDROID_TEST_SERIAL --host $HOST_BT_ADDR"
hidctl.py $S status --wait-host 10      # registered, host, scan mode, Caps Lock
printf 'echo hello\n' | hidctl.py $S type
hidctl.py $S type --layout dvorak < notes.txt
hidctl.py $S key ctrl+l                  # chords; also enter, tab, f5, search
hidctl.py $S move 200 -50
hidctl.py $S click --button right
hidctl.py $S scroll -- -3                # positive scrolls up
hidctl.py $S button left down; hidctl.py $S move 100 0; hidctl.py $S button left up
hidctl.py $S cancel                      # stop a type or key request in progress
hidctl.py $S release                     # cancel, then release every key and button
```

A button held with `button down` is released automatically after 15 seconds
without agent pointer activity (moves and scrolls keep it held), so a crashed
agent cannot leave a drag in progress; replies report `buttonsHeld`. Only the
agent's buttons are released, never a person's touchpad drag. `type` is refused with
`caps_lock_on` when the host reports Caps Lock, because every letter would
arrive inverted (for a password, a failed attempt). Caps Lock is `unknown`
until the host sends its LED state after connecting; after toggling it with
`key capslock`, check `status` before typing.

Every reply is JSON. `delivery: sent` means the Bluetooth stack accepted the
reports; the effect on the host is `unverified` until checked independently
(for example by reading a field back). A partial or cancelled `type` reports
`strokesSent` of `strokesTotal` and whether every key was released
(`confirmed` or `unknown`). Strokes are not text offsets (CRLF is one Enter),
so do not resume from the count; observe the target and decide.

Typing defaults to a 12 ms hold and 12 ms gap. An unshifted character costs one
hold plus the gap and a shifted one three holds plus the gap, so random
printable text measured about 20 characters per second. Use `--hold-ms` and
`--gap-ms` to slow down for sluggish hosts.

## Verified on the ChromeOS testbed (2026-11-08)

- Fresh `pair-floss` pairing in about 13 seconds; reconnection after an app
  restart within about 5 seconds without host action.
- 1000 random printable ASCII characters typed at default pacing into a
  textarea, read back exactly, on two separate bonds.
- Wrong-host refusal, Caps Lock refusal (the host's LED report round-trips),
  `busy` refusal and `cancel` during a 1000-character `type` with keys
  released, a 20-second agent drag kept alive by moves, held-button
  auto-release seen as `mouseup` on the host, and an operator Stop that a
  launcher intent cannot undo.
- Pointer motion (with ChromeOS acceleration), left and right click, and wheel
  in both directions, through the CLI. Touchpad drag, tap-to-click, and the
  Left and Right buttons through the on-screen touchpad. Two-finger scroll is
  not covered because ADB input injects only one pointer.

ChromeOS autocorrects physical-keyboard text in ordinary fields ("teh" became
"the" and a lone "i" became "I"). This is host behaviour, not HID loss: type
into fields with `autocorrect=off`, a terminal, or turn off physical keyboard
autocorrect on the target when exact text matters.

## Limits

- Needs the target OS running with Bluetooth, and a pairing that a powerwash
  or recovery erases. It does not reach firmware, recovery, BIOS or UEFI
  screens; those need a USB HID gadget.
- Boot protocol is refused rather than emulated (`boot_protocol`).
- Characters outside printable ASCII, tab and newline are refused.

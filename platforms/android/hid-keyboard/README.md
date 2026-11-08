# Android handheld as a Bluetooth keyboard and mouse

`MC HID` turns an unrooted Android 12+ handheld into a Bluetooth keyboard and
mouse for another machine, driven by agents over ADB. It speaks classic
Bluetooth HID by default and HID over GATT (Bluetooth LE) on request. It exists
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
- `BleHid`: the LE transport. A GATT server with the HID, Battery and Device
  Information services and the same report map, plus a connectable
  advertisement carrying the HID service UUID. Hosts that hide phones from
  their classic pairing lists, ChromeOS among them, list it.
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
pair in that window, so keep it short and pair only on a controlled bench.
How each host pairs:

| Host | Lists the handheld? | First HID connection | Notes |
| --- | --- | --- | --- |
| macOS | Yes, under Nearby Devices | Either side | Quit Keyboard Setup Assistant when it appears. |
| SteamOS (BlueZ) | Only with **Show all devices** on | Host: `bluetoothctl connect ADDR` | A first connection from the handheld is dropped by BlueZ. |
| ChromeOS (Floss), classic | No: phones are filtered out | Host | Needs root; use `pair-floss`. |
| ChromeOS (Floss), LE | Yes, as a game controller | Host, automatically | No root; see the LE transport below. |

After the first connection, the app reconnects to the saved classic host by
itself when it starts, and `connect ADDRESS` asks for a connection
explicitly. The first host to connect wins, and macOS reconnects on its own as
soon as the app registers. With several bonded hosts in range, turn
Bluetooth off on the hosts that should stay out.

### ChromeOS with root (classic)

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

### ChromeOS without root (LE transport)

```sh
hidctl.py --serial "$ANDROID_TEST_SERIAL" transport ble
hidctl.py --serial "$ANDROID_TEST_SERIAL" discoverable   # so Android shows its code dialog
```

Then on the host choose **Pair new device**, pick the handheld, and confirm
the same six-digit code on both screens. If the host reports "Couldn't pair",
select the device again; the first attempt sometimes fails before the
handheld sees it. `transport classic` switches back, and the choice persists
across restarts.

LE pairing follows the same consent gate as classic. A new host can take the
handheld only while it is discoverable (the system dialog, which `discoverable`
accepts). Only then does the app advertise discoverably with its name, and
Android shows its code dialog instead of a notification that times out
quickly. A device whose bond completes during that window and that
subscribes to an input report (within the window, or 30 seconds after the
bond) becomes the host and is pinned (`leHost` in
`status`). Afterwards only that host can claim the handheld, and the app
advertises, slowly, connectably but not discoverably and without its name,
only while the pinned host is away. Devices that were already bonded (a
laptop or a watch reconnecting for its own reasons, even while the handheld
is discoverable) can read the GATT database but cannot become the host.
Pairing a different host in a later window replaces the pin, and
`transport ble --unpin` clears it and drops input to the current host at once. Android's own Bluetooth settings page also
makes the handheld discoverable while it is open. On Android 13 and earlier,
every connectable advertisement is discoverable.

A host becomes the host again only by writing its subscription. ChromeOS does
that on every connection; a host that relies on the subscription stored from
an earlier connection would get `no_host`. macOS and BlueZ are untested in LE
mode.

`status` reports `pairing`, `advertising`, `leHost` and `subscribed`
(keyboard and mouse). A report counts as sent only if the host subscribed to
it and Android reported the notification sent. After a timeout the next
report first waits for the late confirmation, which narrows but does not
fully close the chance of matching it to the wrong report.

This is good for one session, such as initial setup by an agent watching the
screen, but the pairing does not recover from a dropped link. Android apps
advertise from a rotating private address, and Floss does not reconnect to
it after the handheld's Bluetooth restarts. To use it again, forget the device
on both sides, turn Bluetooth off and on on both, and pair from a fresh
dialog. Killing the app while the link is up (for example `install`) can also
leave the host with a dead HID session on a live link. Check `host` in
`status` and read typed text back.

### Unplug

`unplug --confirm-unpair` disconnects a classic host. Android implements HID
disconnect as a virtual-cable unplug, which removed the bond on the handheld
with ChromeOS, so pairing was needed again (with macOS the bond was still
listed afterwards). There is deliberately no plain `disconnect`.

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
hidctl.py $S scroll -- -3                # notches; positive scrolls up
hidctl.py $S button left down; hidctl.py $S move 100 0; hidctl.py $S button left up
hidctl.py $S cancel                      # stop a type or key request in progress
hidctl.py $S release                     # cancel, then release every key and button
hidctl.py --serial "$ANDROID_TEST_SERIAL" transport ble   # or classic
```

Scrolling sends one report per notch, 15 ms apart (at most 200 notches), because
macOS counts each wheel report as one notch whatever its value. Typing uses
the host's own keyboard layout: pass `--layout dvorak` when the host's input
source is Dvorak, whatever the handheld uses.

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

## Verified hosts (2026-11-08)

ChromeOS testbed, classic transport:

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

ChromeOS testbed, LE transport: listed in and paired from the normal
**Pair new device** dialog without root, 1000 random characters exact at about
17 per second, click, right click, moves and wheel. The link stayed up for 44
minutes idle with the handheld's screen off. No reconnection after the
handheld's Bluetooth restarted (see above).

Steam Deck in Gaming Mode: paired from Steam's settings with
**Show all devices**, all printable ASCII exact in Steam's search field,
one-to-one pointer moves, click and wheel in Steam's settings. The handheld
reconnected by itself after an app restart.

macOS: paired from System Settings; 1000 random characters exact into a text
view with substitutions off, with `--layout dvorak` on a Dvorak Mac. Click,
right click, moves and per-notch wheel (accelerated by macOS) worked. macOS's
"add period with double-space" turns two spaces into ". " unless it is off,
the macOS counterpart of ChromeOS autocorrect.

## Limits

- Needs the target OS running with Bluetooth, and a pairing that a powerwash
  or recovery erases. It does not reach firmware, recovery, BIOS or UEFI
  screens; those need a USB HID gadget.
- Boot protocol is refused rather than emulated (`boot_protocol`).
- Characters outside printable ASCII, tab and newline are refused.
- The LE transport's pairing does not survive a dropped link on ChromeOS.
  Android requires `BLUETOOTH_PRIVILEGED` for a fixed advertising address.
  ChromeOS's `#bluetooth-use-llprivacy` flag gets the host's controller to
  reconnect, but Floss then drops the link. Registering classic HID during
  the LE pairing does not help either: Floss still refuses classic HID
  connections the handheld starts (see the topic notes). Also,
  Android apps cannot set the LE appearance, so hosts show a generic or
  game-controller icon.
- `delivery: sent` means the handheld's stack sent the report (over LE, as a
  notification the host had subscribed to). A host whose HID session died on a
  live link still receives notifications and ignores them, so verify effects.

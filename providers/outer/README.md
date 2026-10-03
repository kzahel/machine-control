# Controller desktop outer input

The Mac [typed bridge](macos.py) reserves the same native desktop as physical
host use. It borrows the authoritative adapter's existing disruptive VM claim;
it does not acquire another VM lease or extend that lease's deadline. Claim
release/replacement and native activation/effects use the same claim-store
operation lock. Waiting holds no host desktop reservation while blocked by
approval, quiet, Pause or another owner.

Tart global keyboard/pointer input and UTM global drag use this bridge. UTM's
VM-directed AppleScript keyboard/click injection and capture-only routes do
not move the host foreground/cursor and retain their existing exact claim and
policy checks. Resident VM routes remain independent of the controller desktop.
Absolute provider prohibitions and declared attendance remain stronger than a
queue offer. There is no silent outer fallback.

Native input is typed and bounded. Tart runner arguments bind its window to the
exact claimed VM. The UTM adapter verifies its UUID/name before requesting a
finite window/process/geometry binding. Each primitive rechecks that binding,
console state, live VM lease and desktop owner generation before posting an
event. Pause/disconnect releases this handler's held drag button. Resumption
requires a fresh window reference; interrupted input is never replayed.

This remains the explicit cooperative same-user profile. Caller labels and
claim IDs do not authenticate an integration, and an unrestricted same-user
shell can bypass the adapters. Multiple controller authorities are not a
supported distributed transaction.

`type-secret` refuses with `secret_safe_outer_transport_unavailable` before
reading credential bytes. A verified credential field and dedicated one-shot
transport must be implemented before that outer route can participate; the old
unfenced global HID helper is not a Pause bypass. Ordinary printable US-keyboard
text and Command/Shift physical chords remain typed input, not credential
transport. Control/Option/Fn diagnostic chords are not advertised by this bridge.

The [tactical](../../docs/tactical/084-native-outer-desktop-admission.md)
separates source/socket fixtures from live provider and physical acceptance.

# Keyboard fixture

Independent effect oracles for layout-aware resident keyboard input.
[Tactical 126](../../../../../docs/tactical/126-macos-keyboard-layout-input.md)
owns the contract, bounded acceptance and remaining coverage.

Run the real-resident suite from the repository root against an already
healthy, running, claimed Tart VM:

```sh
python3 tests/macos/keyboard-layouts.py --target macos --claim CLAIM
```

The runner builds and stages a unique fixture, switches three layouts with
two modifier profiles, checks actual effects, restores the previous input
source and complete HID mapping, and removes its process/files. Add
`--install-profile` to persist plain Dvorak, Command/Option swapped on both
sides and Caps→Control after success. Add `--browser-smoke` for real Chrome for Testing shortcuts and text using
the existing separate test browser with a disposable profile and mock keychain.
The browser is reaped afterward. The caller owns power and claim cleanup.
Ordinary testing prohibits outer UI and leaves controller settings untouched.
Passive host samples report equality or an unattributed change;
`--require-host-unchanged` enables a strict gate for a deliberately quiet host.

`KeyboardFixture.swift` has an AppKit text view, shortcut and Edit menus, a
secure field and a WKWebView. `--log PATH` records key/menu/web/pointer events;
`--state PATH` records independent effects. A scratch JSON file passed with
`--commands PATH` selects text, secure or web mode and resets the fixture.
Each command includes a monotonically increasing `revision`, which the state
acknowledges before input begins. Secure-field state retains a boolean match
against a fixed public dummy, never the field value.

`credential-probe.swift` links the production `KeyboardInput.swift` planner
and emitter. It sends only the fixed public dummy and refuses unless the
keyboard fixture is frontmost. Both process and session delivery are tested.
It does not open a real authorization sheet, consume real credentials or
qualify the one-shot authentication transport.

`environment.swift` reports the input source and modifier state. Its mutations
require Apple's virtual-Mac hardware model. It enables/selects layouts,
applies numeric HID mappings and can install an Aqua login profile.
`macvm keyboard-profile install|status|standard|alternate` exposes it through
the claimed testbed. HID mapping snapshots must normalize OpenStep numeric
strings to JSON integers before restoration; sending strings can crash the
system's keyboard filter. A pure regression test covers this conversion and
invalid-property refusal.

`keysend.swift` remains the historical replica sender used for the original
investigation. Its `ansi` and `credential` modes reproduce the old fixed-U.S.
behavior; they are not the current resident implementation or an acceptance
route. Use only fake values, only against the fixture. The HID route refuses
unless the fixture is frontmost.

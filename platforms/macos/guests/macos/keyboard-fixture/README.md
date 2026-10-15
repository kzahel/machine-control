# Keyboard fixture

Reproduces keyboard-layout and modifier-state behavior of synthesized input.
[Tactical 126](../../../../../docs/tactical/126-macos-keyboard-layout-input.md)
owns the findings and plan.

`KeyboardFixture.swift` is an AppKit app (bundle ID
`org.machine-control.keyboard-fixture`) with a text view, a Probe menu of
command shortcuts and, with `--web`, a WKWebView window. It appends one JSON
line per observation to `--log PATH` (default `/tmp/keyboard-fixture.jsonl`):
`keyDown` and `performKeyEquivalent` with key code, `characters` and
`charactersIgnoringModifiers`; `menu` with the shortcut item that fired; and
`web` with DOM `key` and `code`.

`keysend.swift` reproduces the resident's event construction without an
access grant, so routes can be compared directly. Post only to the fixture.

```sh
swiftc -O KeyboardFixture.swift -o /tmp/kf/KeyboardFixture
mkdir -p /tmp/kf/KF.app/Contents/MacOS && cp /tmp/kf/KeyboardFixture /tmp/kf/KF.app/Contents/MacOS/
cp Info.plist /tmp/kf/KF.app/Contents/ && open -a /tmp/kf/KF.app --args --web
swiftc -O keysend.swift -o /tmp/kf/keysend
/tmp/kf/keysend "$(pgrep -x KeyboardFixture)" ansi cmd+l      # resident today
/tmp/kf/keysend "$(pgrep -x KeyboardFixture)" layout cmd+l    # candidate fix
/tmp/kf/keysend "$(pgrep -x KeyboardFixture)" credential Fake2Pass
/tmp/kf/keysend - modifiers            # add `release` to clear stuck state
```

Use only fake values with `credential`. The HID route (`PID` 0) refuses
unless the fixture is frontmost.

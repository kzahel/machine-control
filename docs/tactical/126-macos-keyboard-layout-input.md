# 126 — macOS keyboard-layout-correct input

Status: proposed. Investigation recorded; no resident code changed yet.
Owning topic: [macOS resident control](../../topics/macos-resident-control.md).
Origin: friction recorded in
[117](117-chrome-web-store-extension.md#result) while driving Chrome on a Mac
whose input source is Dvorak.

## Objective and completion conditions

Make synthesized keyboard input on macOS mean the same thing on every
keyboard layout, and stop synthesized chords from leaking modifier state.
Complete when:

- `desktop input key` chords produce the requested character and modifiers
  under U.S., Dvorak, Dvorak – QWERTY ⌘, at least one ISO Latin layout
  (German or French) and one non-Latin layout (Russian or similar), and
  report the resolved key code and layout;
- credential entry types exactly the stored bytes on those layouts, or refuses
  before reading the secret when the active layout cannot produce them;
- no route leaves Command, Shift, Option or Control set in the session
  modifier state, and resident pointer events never inherit modifiers they
  were not asked for; and
- the keyboard fixture covers these cases in a repeatable live suite.

## Boundaries

- Never switch the input source of a person's workstation for testing. Layout
  matrices run in a disposable macOS Tart guest.
- Credential experiments use fake values and the keyboard fixture only; never
  a real login, authorization or unlock sheet with a guessed or real secret.
- `input.text` (Unicode route) already ignores layout; change it only if the
  investigation shows a consumer that needs real key codes.
- Windows and Linux are audited here but fixed under their own topics if
  they need code changes.

## Findings

All **Current**, observed on 2026-10-14 on a macOS 26 workstation with the
plain Dvorak layout selected and U.S. enabled, using the
[keyboard fixture](../../platforms/macos/guests/macos/keyboard-fixture/README.md)
and a replica of the resident's event code. The resident itself was not
exercised in the matrix because its access request timed out unanswered.

### 1 — chords use physical US-ANSI positions

`Resident.keyCode`/`sendKey` (`platforms/macos/resident/Sources/macui/Resident.swift`)
map key names to fixed US-ANSI virtual key codes. CoreGraphics stamps each
event's characters from the *current* layout when the event is created, so:

| Requested | Key code | Dvorak characters | Menu item fired |
| --- | --- | --- | --- |
| `cmd+l` | 37 | `n` | ⌘N (Chrome: new window) |
| `cmd+w` | 13 | `,` | ⌘, (Chrome: Settings) |
| `cmd+t` | 17 | `y` | ⌘Y (Chrome: History) |
| `cmd+,` | 43 | `w` | ⌘W |
| `cmd+shift+l` | 37 | `n` / ignoring `N` | ⇧⌘N |

- Process-targeted (`--target`, `postToPid`) and HID-tap (no target) routes
  behave identically.
- Every consumer agreed: AppKit menu key equivalents, `performKeyEquivalent`,
  `keyDown`, and WKWebView DOM events (`key: "n"`, `code: "KeyL"`). This is
  exactly what a real Dvorak user pressing the physical QWERTY key gets; it is
  not specific to a window type or application.
- Setting `flags` after event creation does not update the stamped
  characters: with Shift, `characters` stays lower case while
  `charactersIgnoringModifiers` is upper case.
- Results reported `delivery: confirmed` with `effect: unverifiable`, so the
  wrong action was not visible to the caller.
- Text typing works because `literalTextEvents` (`TextInput.swift`) sends a
  Unicode string on key code 0 with cleared flags.

**Candidate fix, verified in the replica:** resolve the requested character
to a key code by scanning `UCKeyTranslate` over the current keyboard layout
(unshifted, then shifted), falling back to
`TISCopyCurrentASCIICapableKeyboardLayoutInputSource`. Under Dvorak this sent
`cmd+l` as key code 35, firing ⌘L with web `key: "l"`, `code: "KeyP"`; `cmd+w`,
`cmd+t`, `cmd+,`, `cmd+shift+w`, `cmd+.` and `cmd+]` all fired their intended
items, and `cmd+?` resolved to Shift plus the `/` key.

### 2 — HID chords leave modifiers set; pointer events inherit them

- After a chord posted to the HID tap with `maskCommand` (the resident's
  untargeted route), `CGEventSource.flagsState(.hidSystemState)` and
  `.combinedSessionState` both report Command held until a real modifier
  release. The process-targeted route leaves the state clean.
- A nil-source `CGEvent` created afterwards inherits Command. The resident's
  `input.move`, `input.click` and `input.drag` create nil-source mouse events
  and never set `flags`, so the next resident click can be a ⌘-click (for
  example, opening a link in a new tab). A private-state event source did not
  inherit the flag.
- Posting a `flagsChanged` key-up for Command with empty flags cleared it.
- **Open:** whether the stuck state changes a person's physical typing was not
  tested; it would require physical input.

### 3 — credential entry types US-ANSI positions

`Resident.physicalKey`/`sendCredential` map credential bytes through the same
US-ANSI table. The replica typed the fake value `Fake2Pass` into the fixture
and the fixture received `Uat.2Laoo`. On a real authorization or unlock sheet
under Dvorak every attempt would be a wrong password, and retries could reach
account lockout. This is the most severe finding.

### Side notes

- `postToPid` delivers asynchronously; a short-lived sender that exits right
  after posting can lose the events. This affected only the replica harness,
  not the long-lived resident, but explains flaky one-shot tools.
- `OuterRecovery.swift` posts fixed key codes into a VM window; the guest's
  layout, not the host's, decides the characters. It needs the same audit.
- `ConsoleUnlockTrigger.swift` posts Return (code 36), which is
  layout-independent.

## Open questions

- Which macOS consumers read the raw key code rather than characters
  (Terminal, Electron accelerators, Java, games)? Does sending text on key
  code 0 confuse any of them?
- Does the login window or a locked session use a different input source from
  the user session (affects locked-use credential entry)?
- Behavior under "Dvorak – QWERTY ⌘", which keeps QWERTY positions while
  Command is held, and under layouts with dead keys or AltGr/Option
  characters.
- Should a chord be able to request a *physical* key when that is what a
  caller means? **Proposal:** chord names keep character semantics; an
  explicit physical form (for example `code:KeyL`) can be added later only
  if a real consumer needs it.
- Windows: letter chords use virtual-key codes (layout-semantic for letters),
  but `DesktopController` also has a scan-code path (physical). Linux sends
  portal keysyms and has a noted Unicode/keymap edge in `provider.py`. Both
  need a layout audit with their own fixtures.

## Ordered work

### 1 — characterize the remaining matrix in a Tart guest

In a disposable macOS guest, switch input sources programmatically and run
the fixture matrix for U.S., Dvorak, Dvorak – QWERTY ⌘, German or French, and
Russian. Add Terminal, an Electron app and the Java fixture as consumers.
Record which consumers follow characters and which follow key codes.

### 2 — resolve chords through the active layout

Replace the fixed table in `sendKey` with a resolver: named keys (Return,
Tab, arrows, Escape, Delete, Space, function keys) keep fixed codes; single
characters resolve through the current layout, then the ASCII-capable
layout; unresolvable characters refuse with a typed error. Create events from
a private-state `CGEventSource` with explicit flags. Report the resolved key
code, the layout ID and whether a fallback layout was used in the result
data. Unit-test the resolver with injected layout tables.

### 3 — fix modifier hygiene

After any HID-route chord with modifiers, post explicit modifier releases (or
otherwise prove the session state is unchanged), and verify with
`flagsState` in tests. Give pointer events explicit flags from a private-state
source. Audit `OuterRecovery` and any other nil-source event creation.

### 4 — make credential entry layout-correct

Before reading the secret, confirm the active layout for the target sheet can
produce every needed character class; after reading, resolve each byte
through that layout and refuse without typing if any byte cannot be produced
or would require a dead key. Never fall back to US-ANSI positions. Add a
fixture test with fake values across the layout matrix.

### 5 — add a live conformance suite

Package the fixture for the Tart guest like the other fixtures, drive it
through the real resident (`desktop input key`, `input.text`, credential
route, pointer after chord), and assert menu, key and web observations per
layout. Run it on the workstation only for the current layout, without
switching it.

### 6 — audit Windows and Linux

Repeat the matrix with platform fixtures under each platform's topic. Record
results here; file separate tacticals if code changes are needed.

## Validation

- Resolver unit tests and the live suite in step 5.
- `platforms/macos/tests/smoke.sh` typechecks the fixture and replica.
- Manual reproduction: [fixture README](../../platforms/macos/guests/macos/keyboard-fixture/README.md).

## Result

Investigation complete for findings 1–3 on one Dvorak workstation; private
usage notes record the same observations with session attribution. Steps
1–6 have not started.

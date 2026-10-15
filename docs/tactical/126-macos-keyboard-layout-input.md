# 126 — macOS keyboard-layout-correct input

Status: complete for the bounded ordinary-session macOS milestone.
Owning topic: [macOS resident control](../../topics/macos-resident-control.md).
Origin: friction recorded in
[117](117-chrome-web-store-extension.md#result) while driving Chrome on a Mac
whose input source is Dvorak.

## Objective and completion conditions

Make ordinary macOS keyboard input correct under alternate layouts and
modifier remappings. The first acceptance milestone uses the existing Tart
appliance, with U.S., plain Dvorak and Dvorak – QWERTY ⌘, each with default
modifiers and Command/Option swapped plus Caps Lock mapped to Control.

Complete this milestone when:

- the actual resident produces intended menu actions, editing shortcuts,
  character keys, shifted punctuation, Control/Option navigation and exact
  Unicode text under all six configurations;
- the production credential planner/emitter types a fixed public dummy into
  the fixture's secure field through both session and process routes, and
  refuses unsupported alphabets before requesting secret bytes;
- keyboard chords leave session/HID modifier state clean and subsequent
  pointer events and ordinary typing have no inherited modifiers;
- layout/mapping changes take effect without restarting the resident, and
  both guest-local and outside callers reach the same implementation; and
- the existing VM retains the alternate profile across login/reboot, with a
  repeatable runner that temporarily switches settings and restores them.

German/French, non-Latin input methods, additional app frameworks and the
Windows/Linux layout audits remain follow-ups rather than blocking this
bounded macOS milestone.

## Boundaries and input semantics

- Never switch the input source or modifier mappings of a person's
  workstation for testing. Reuse the claimed Tart appliance; no extra VM is
  needed. The configuration helper refuses mutations outside a virtual Mac.
- Chord modifiers name logical Command, Option, Control and Shift. Hardware
  modifier remappings must not be applied a second time by the injector.
  Caps → Control is tested as an active mapping alongside logical Control
  operations; this is not a physical-keyboard hardware test.
- Resolve character keys using the effective Command mapping, so plain
  Dvorak and Dvorak – QWERTY ⌘ can resolve the same shortcut differently.
  Named navigation/function keys retain fixed virtual key codes.
- The ordinary keyboard suite's credential probe uses a public dummy in the
  secure fixture. Real authorization is a separate explicitly selected runner
  against the claimed appliance's ordinary SecurityAgent sheet, using only the
  canonical stored credential transport and independent privileged effect.
  No failed/uncertain credential is retried. Loginwindow, unlock and other
  authorization sheet profiles require separate qualification.
- Keep Unicode text separate from character-key/chord input. Preserve native
  key codes for shortcuts; overriding their Unicode payload can prevent
  AppKit menu equivalents from firing.
- Refuse unresolvable keys and composition input methods rather than using
  an unqualified underlying or fallback ASCII layout.
  Exact credential entry requires the entire printable-ASCII alphabet before
  the one-shot transport requests bytes, then resolves the entire credential
  before clearing the field or sending any prefix. Dead keys are refused.
- Ordinary acceptance prohibits outer UI. Separately claimed recovery
  observation is recorded independently and cannot count as a suite pass.

## Findings

Historical **Current** observations from 2026-10-14 on a macOS 26 workstation with the
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

- Which additional macOS consumers read the raw key code rather than
  characters (Java, games, other editors)? Terminal/readline and a standalone
  Electron editor are now covered by the six-cell application matrix; that
  does not qualify every app or custom keybinding configuration.
- Does the login window or a locked session use a different input source from
  the user session (affects locked-use credential entry)?
- Broader behavior under layouts with dead keys or AltGr/Option characters.
  Dvorak – QWERTY ⌘ is covered by the completed six-cell matrix.
- Should a chord be able to request a *physical* key when that is what a
  caller means? **Proposal:** chord names keep character semantics; an
  explicit physical form (for example `code:KeyL`) can be added later only
  if a real consumer needs it.
- Windows: letter chords use virtual-key codes (layout-semantic for letters),
  but `DesktopController` also has a scan-code path (physical). Linux sends
  portal keysyms and has a noted Unicode/keymap edge in `provider.py`. Both
  need a layout audit with their own fixtures.

## Implementation and repeatable validation

### 1 — use the selected layout in the real resident

`KeyboardInput.swift` owns Carbon layout snapshots, Command-aware character
resolution, typed unavailable-layout/key refusals, real key-code events and
shared credential planning. Each request reads the current selection; a
credential preflight binds the selection and keyboard type through secret
receipt and every subsequent character. No U.S. positional fallback remains
in the ordinary resident or credential path.

### 2 — isolate event state and release modifiers

Keyboard, text, pointer and scroll events use private-state sources. Pointer
and scroll flags are explicitly empty. Session chords release their own
modifiers while preserving flags already present before dispatch. Cancellation
before dispatch emits nothing; key/button releases still complete once down
has been sent. The separately guarded host/Tart recovery sender remains a
physical U.S.-position route; it is not covered by this resident acceptance.

### 3 — keep an alternate profile in the existing appliance

`macvm keyboard-profile install` enables the three layouts, selects Dvorak,
swaps left/right Command with Option, and maps Caps Lock to left Control.
An Aqua LaunchAgent reapplies the profile at login. `standard` temporarily
selects U.S. with default modifiers; `alternate` reapplies the Dvorak profile;
`status` reports the active settings. These commands run inside the selected
claimed guest and never change the controller's settings.

### 4 — run live effects through the production facade

[`tests/macos/keyboard-layouts.py`](../../tests/macos/keyboard-layouts.py)
builds and stages a unique AppKit/WebKit fixture, then uses the actual resident
client for six configuration cells without restarting the resident. Independent
fixture state proves menu, text, editing, Control/Option, web and pointer
behavior. The public-dummy credential probe links the same production planner
and emitter and tests session and process delivery into a secure field.
Secure state retains only a match boolean. Settings and fixture processes are
restored/removed in cleanup. Passive host samples record equality or an
unattributed change; `--require-host-unchanged` is the explicit strict gate
for a deliberately quiet controller. A change during ordinary controller use
cannot be attributed from those two samples alone. `--install-profile`
installs the persistent alternate setup after success. The caller owns power state and claim cleanup.

### 5 — prove Terminal and Electron application effects

`--apps-smoke` adds six configurations of native Terminal/readline and a
standalone Electron editor; `--apps-only` runs that matrix separately. It
requires the checksum-pinned Electron framework runtime and checks the guest
version against the staged repository manifest. The Terminal PTY runs `read -e`
and records NUL-delimited lines, never evaluating typed bytes. Exact text after
Control-A/E/U and Option-Left, plus native new/close-tab effects, are the oracles.
The real Electron app uses standard native Edit menu roles and Save/Find
accelerators; independent file state proves exact Unicode text, copy/paste,
undo, saved text and Find-field focus/query.

Each app occupies an owned process and scratch files; Electron uses a copied,
locally signed runtime and disposable profile with mock keychain. The resident
must retain its generation and report the selected layout for every key. Input
settings and owned processes are restored/reaped in cleanup. The application
wrapper streams progress, allows ten minutes, and interrupts Python before
escalating on timeout so its cleanup can run. These are bounded fixture tests,
not qualification of arbitrary editors or terminal settings.

### 6 — prove real administrator authorization

[`tests/macos/keyboard-authorization.py`](../../tests/macos/keyboard-authorization.py)
uses the existing administrator fixture, which invokes macOS authorization to
run only `/usr/bin/id -u`. Each of the six keyboard cells requires a fresh
fixture request and a real matching SecurityAgent sheet. A wrong requester is
refused before a valid generation-bound lease is issued. The runner selects
and reads back the exact layout after sheet discovery, then calls the common
CLI's `authorization-submit --stored` once. It never handles the password in
Python, JSON, arguments, environment variables or evidence.

The normal owner-process credential route must confirm delivery and sheet
dismissal. The independent fixture must report the same request authorized and
the root command completed. Lease reuse is refused, resident generation stays
stable, and HID/session modifiers remain clean. A failed or uncertain attempt
stops the matrix. Cleanup removes the owned fixture and restores the selected
input source and complete numeric HID mapping. The caller owns power/claims.
This qualifies real ordinary SecurityAgent authorization, not System Settings'
session-keyboard variant, loginwindow, unlock or every password prompt.

### 7 — validation and remaining coverage

- Swift tests cover Dvorak versus Command-specific lookup, punctuation and
  separators, named keys, complete credential preflight, refusal without a
  partial plan, stale layout detection, explicit event flags and cancellation.
- `platforms/macos/tests/smoke.sh --static` typechecks the production source
  and keyboard fixture/configuration/probe, alongside existing native checks.
- The live six-cell suite proves actual fixture effects. `--browser-smoke`
  adds an isolated Chrome for Testing profile, independently observes page
  navigation/text/clipboard and new/close-tab effects, and reaps the browser.
  Its mock-keychain flags match the existing browser harness, keeping ordinary
  keychain prompts out of this disposable profile. Separate outside
  caller checks and reboot/profile readback qualify transport parity and
  persistence. Real authentication belongs to the separate administrator
  runner above, not the ordinary keyboard/browser suite.
- Java and additional editors, broader layouts,
  login-window layout selection, outer recovery layout translation and other
  platforms remain explicitly unqualified follow-ups.

## Result

**Current (2026-10-15), ARM64 Tart, macOS 26.6.2, unreleased candidate:** the
real resident passes all six layout/remapping cells, with 210 resident
operations and independent AppKit/WebKit effects. It stays running across the
configuration changes. The real Chrome for Testing smoke passes Command-L
navigation, exact Unicode text, copy/paste, Command-T and Command-W under
plain Dvorak with the alternate modifier mapping. It uses its own disposable
profile and the existing harness's mock-keychain flags; without those flags,
the first browser run entered the correct URL but never fetched the page.

The follow-up Terminal/Electron application matrix passes all six cells
through 206 real resident operations on the same candidate. Terminal proves
readline editing, exact Unicode/punctuation and native new/close-tab shortcuts;
the standalone Electron 43.2.0 editor proves text, copy/paste, undo and native
Save/Find accelerators. An initial run exceeded the inherited three-minute
child timeout; its exact owned processes were reaped and the alternate profile
restored before rerunning with the corrected bounded wrapper. This expanded
acceptance required no further production input changes.

A real bounded Tart stop/start changed the guest boot-session UUID. On the
new boot, the Aqua profile had selected Dvorak, enabled all three layouts and
restored all five numeric HID remappings. Normal `target shutdown` refused
its administrator preflight, so it was not counted as reboot evidence. The
documented bounded stop/start was used instead. A fresh outside caller then
proved Command-L (resolved key code 35), exact Unicode text and an unsupported
key refusal with no text prefix through the same deployed resident. Doctor
reported healthy native desktop, semantics, capture and input afterward.

The shared credential planner/emitter passes the public dummy in the secure
fixture through session and process delivery in every cell. The separate
real-authorization matrix additionally passes all six cells through the normal
SecurityAgent owner-process route, using the canonical stored appliance
credential. Each dialog dismisses and each matching fixture request confirms
successful root-command completion. Wrong-requester and used-lease refusals
pass, with clean modifier state and stable resident generation. No credential
failed or was retried. No workstation password or login/unlock transaction was
involved. Unit tests separately cover the full supported alphabet, composition
refusal and whole-value validation; the appliance's real credential does not
prove every possible password character. System Settings' session-keyboard
profile and other real authorization profiles remain unqualified under these
alternate layouts.

Validation passed: 191 Swift tests, five Python mapping/host-observation
regressions, portable checks, macOS native static checks and ARM64/x86_64 app
builds with local signature verification. GUI execution is ARM64 only. The
candidate is deployed in the existing guest; the installed workstation app
and published packages were not replaced.

One early cleanup sent OpenStep numeric strings back to HID mapping APIs;
the guest WindowServer report aborted inside its keyboard-filter mapping
routine. Recovery used a bounded stop/start and one separately claimed
read-only outer screenshot, with no outer input. The corrected helper emits
numeric JSON mappings; restoration of the nonempty alternate map passed.
The final suite's input routes remained target-native with outer UI forbidden.

One complete matrix observed unchanged controller focus/cursor. A later
combined run passed every keyboard/browser effect but its old final strict
host-equality assertion failed. Those two passive samples cannot attribute a
change while the controller is in use. The runner now reports an unattributed
change by default, retaining `--require-host-unchanged` for a deliberately
quiet host; pure regressions cover both outcomes. Private usage notes retain
session-attributed friction and recovery evidence.

Java and additional editor keyboard-specific runs, German/French and non-Latin
layouts, login-window layout selection, physical Caps-key behavior, and outer
recovery layout translation remain follow-ups. The outer secret path must
not be used against an unknown or alternate guest layout. The controller's
keyboard settings were never changed. Acceptance cleanup powered down the
guest and released its target-use claim; the private usage summary records
the operational outcome.

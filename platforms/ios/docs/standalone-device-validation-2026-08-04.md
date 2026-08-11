# Standalone Physical-Device Validation — 2026-08-04

## Scope

First post-refactor standalone run of this repository against the attached
iPhone SE (3rd generation). The demonstration target is JSTorrent: open the
app and add a legal test magnet published by WebTorrent.

Private device identifiers, signing details, raw session logs, and screenshots
are intentionally excluded from this note.

## Running notes

### Read-only discovery and readiness

- `bin/ios-device probe` returned `connected` with exit status 0.
- `bin/ios-device doctor` returned `doctor: ready` with exit status 0.
- The wrapper selected one wired iPhone SE (3rd generation) on iOS 26.6.
- The phone was unlocked, Developer Mode was enabled, signing was available,
  Developer Tools security was enabled, and the XCTest build cache was present.
- Friction: none. Standalone discovery was fast and did not expose device
  ambiguity, pairing, trust, signing, or runner-readiness problems.

### JSTorrent demonstration

- `session` acquired the exclusive lease and `launch jstorrent` resolved and
  opened the installed app by name without a hard-coded bundle identifier.
- The first interactive snapshot returned 25 visible nodes and clearly exposed
  the empty-state text plus Search, Settings, and Add torrent buttons.
- Friction: a selector written as `role=button label=Add torrent` was rejected
  because a selector value containing spaces must be internally quoted as
  `label="Add torrent"`. The rejection happened before input and did not mutate
  the UI. This quoting rule is present in the runtime error, but is easy to miss
  when adapting the shorter README selector example.
- Friction: the compact interactive snapshot of the Add Torrent sheet omitted
  the SwiftUI text field. A 76-node raw snapshot exposed it, but
  `role=text-field` did not match. The flow therefore had to use the fresh raw
  snapshot ref for the field. The two failed lookups were observation/input
  validation failures and did not change the UI.
- The 524-character Big Buck Bunny magnet was taken from WebTorrent's current
  [Free Torrents](https://webtorrent.io/free-torrents) page, which identifies
  the listed torrents as public-domain or Creative Commons test material.
- Filling the fresh text-field ref succeeded and reported `Filled 524 chars`.
- Friction: `scroll --help` calls the second positional argument `amount` but
  does not describe its units or numeric range. A descriptive value (`small`)
  was rejected. The explicit and self-documenting `--pixels` form worked; two
  downward scrolls exposed Add while keeping the keyboard open.
- Pressing the freshly snapshotted Add cell returned to JSTorrent's main view.
  A fresh snapshot showed Runtime Running and Big Buck Bunny at 100% Seeding.
- Friction: a broad `find "Big Buck Bunny"` was ambiguous because the same
  content was represented by three accessibility layers. A fresh interactive
  snapshot provided a clear exact-state assertion instead.
- Unexpected app state: when JSTorrent's runtime started, a separate
  `testdata_100mb.bin` entry appeared even though the initial UI reported zero
  torrents. It was left untouched because it was outside this demonstration.
- A temporary screenshot was captured outside the repository and reviewed. It
  visually confirmed JSTorrent Running, Big Buck Bunny at 100%, and Seeding.
- The transactional shell exited normally. `bin/ios-device status` then showed
  the phone connected and `lease active: no`.
- `normal-launch com.jstorrent.ios` succeeded after cleanup, leaving JSTorrent
  visible outside the XCTest automation presentation.
- Post-run verification passed: `pnpm check` ran all 17 tests successfully,
  `probe` still returned `connected`, and `doctor` still returned
  `doctor: ready`.

## Result

Pass. Standalone discovery, readiness diagnosis, device selection, runner
session setup, app-name resolution, semantic navigation, long text input,
scrolling, app-state verification, evidence capture, lease cleanup, and normal
post-session launch all worked on the attached physical phone.

The main opportunities are documentation and accessibility ergonomics: show a
selector with a quoted multi-word value in the README, document numeric scroll
amount semantics, and investigate why the Add Torrent text field is absent
from compact interactive snapshots and does not match `role=text-field`.

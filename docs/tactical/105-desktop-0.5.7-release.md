# 105 — Desktop 0.5.7 release

Status: complete; published on 2026-10-06.
Owning topics: [native distribution](../../topics/native-distribution.md) and
[Windows desktop](../../topics/windows-desktop.md).

## Objective and completion conditions

Release the current desktop changes as one public version for Mac Apple
silicon/Intel, Windows x64/ARM64, and Linux x64/ARM64. Require meaningful notes,
passing source checks, authenticated packages, immutable publication, and
verified public downloads and production update metadata.

## Boundaries

Use the unified release workflow and promote its exact verified candidate
bytes. Preserve published tags and assets. Package verification does not add
signed installed feature, ARM64 GUI, physical hardware, or protected-helper
execution evidence. Existing feature tacticals retain their exact acceptance
scope. No accepted test appliances or controller installations are changed.

## Ordered work

### 1 — prepare notes and resolve qualification blockers

Version the accumulated pointer, human-activity pause, covered locked-use,
browser upload/CDP, and optional UAC changes. Run release tests and source
checks. Correct defects exposed by qualification without weakening production
policy or authenticity checks.

### 2 — build and authenticate all six targets

Build a complete unified candidate on main. Require native publisher signing,
Mac notarization/staples, updater signatures and signed versions, installed
payload inventories, relocated CLI checks, and tamper rejection. Bind all
receipts to one source revision and workflow attempt.

### 3 — publish exact bytes and verify delivery

Create an annotated immutable tag and promote the successful candidate.
Verify uploaded asset hashes before publication, then independently download
and authenticate all assets. Check the downloads page, eight redirects, and
both production metadata services for all six updater targets.

## Validation and final result

**Current:** [Public desktop 0.5.7](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.7)
uses source `befba6ea8205935ddbf41e00096a12db8a34c58d`.
[Candidate 37419835062](https://github.com/kzahel/machine-control/actions/runs/37419835062),
attempt 1, built and authenticated all six targets.
[Promotion 37423018182](https://github.com/kzahel/machine-control/actions/runs/37423018182)
published those exact bytes without rebuilding. The exact-source
[cross-platform checks](https://github.com/kzahel/machine-control/actions/runs/37419834954)
pass on macOS, Windows, and Linux.

All 29 independently downloaded public assets match GitHub SHA-256 digests
and sizes. All six package receipts bind version, source, run and attempt.
Windows/Linux updater signatures, signed versions and payload inventories
pass; Mac nested publisher signatures, Gatekeeper, notarization and staples
pass. Modified packages are rejected. Hosted installed CLI relocation passes
for every target. This is package/CLI evidence, not a new installed GUI or
protected-feature acceptance campaign.

The public manifest contains exactly six signed updater entries and the
required changelog. The downloads page and all eight redirects select 0.5.7.
All 24 production responses across the website proxy and shared service match
the signed manifest for 0.5.5 clients and return HTTP 204 for 0.5.7 clients.
Public delivery checks use curl; the website rejected Python's default HTTP
client with 403, while curl verified the same page and routes successfully.

Release regression tests pass (74 tests, one platform-specific skip).
Desktop contracts and format verification pass locally; native Windows
contracts, format verification and x64/ARM64 publishes pass in hosted checks.
The prior feature execution evidence remains in tacticals 097–104 and the
[acceptance matrix](../desktop-acceptance.md).

### Qualification failures resolved before publication

- `875bbda` fixes anonymous-object formatting rejected by Windows checks.
- The unpublished immutable `desktop-v0.5.6` attempt exposed a reproducible
  CDP fixture race: HTTP upgrade can finish before provider initialization.
  `c9d95af` checks root routing after the correlated command response. Release
  0.5.7 replaces that attempt; the old tag is not moved or published.
- The first 0.5.7 candidate built signed Linux containers, then rejected the
  new shared `browser_cdp.js` as unexpected. `4bc2162` requires that exact
  module from 0.5.7 onward, preserves historical inventories, and tests both
  complete and missing-module payloads.
- The next candidate hit the five-second production SQLite busy timeout in
  a three-writer Windows journal fixture. `befba6e` gives only fixture child
  connections a bounded twenty-second busy wait and sixty-second process
  deadline. Production journal timeout and failure policy stay unchanged.
  All twenty journal tests and final hosted portable checks pass.

Failed candidates are cancelled before promotion. Redundant automatic Mac
checks are cancelled when they block the unified workflow's exact-source
check. Original tags, signed bytes and receipt identities remain intact.

# 058 — Browser tab indicators and desktop 0.4.10

Status: complete

Owning topics: [browser control](../../topics/browser-control.md) and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

The user observed Codex's colored tab groups and favicon markers, requested
source investigation for inspiration, then authorized implementation, VM tests,
a commit, and a new desktop release. Ship owned markers for actually controlled
tabs and groups for newly created agent tabs.

- Existing user grouping and pinned tabs remain intact.
- Navigation and site-icon changes retain the marker; cleanup restores the
  latest site icon and preserves user group edits.
- Release, ended/replaced grants, disconnect, debugger cancellation, and worker
  recovery cannot leave permanent owned indicators or infer new authority.
- Real Chrome for Testing in a claimed Mac VM proves browser effects and a
  target-native capture proves tab-strip presentation.
- Authenticate all four Mac/Windows candidate packages, exercise the exact
  packaged extension, publish those bytes, and verify public metadata.

## Boundaries

Use interaction inspiration from the source-reviewed
[Codex dossier](../../research/providers/codex-browser-extension.md); adopt no
third-party code or artwork. No new completed-work or handoff API, broad page
permissions, Web Store publication, Linux release, or unrelated VM operations.
Keep claims, target identities, login credentials, raw logs, and captures private.
Restore the VM's initial power state and remove owned test state.

## Ordered work

### 1 — mark controlled browser tabs

Use the already authorized per-tab debugger to render owned SVG favicon badges
in an isolated world. Group only new, ungrouped, unpinned tabs. Report group and
indicator state in tab enumeration. Persist only cleanup metadata, fence queued
work by generation, and expire page markers without the worker heartbeat.

### 2 — prove lifecycle and visible effects

Exercise manager and actual-worker lifecycles, including replaced grants with
unchanged scopes. Use an independent HTTP page oracle and Chrome tab/group API
observations in a headed test browser on the target. Verify navigation, icon
mutation, group edits, release, cancelled debugger expiry, and worker recovery.
Use a separately identified browser and reap it after every run.

### 3 — publish the accepted desktop patch

Build the signed Mac ARM64/Intel and Windows x64/ARM64 matrix at one source.
Authenticate candidate packages and verify the exact installed extension before
promoting the same bytes. Check release asset digests, downloads, and production
update metadata; keep unexecuted architecture coverage explicit.

## Validation and result

Source checks pass: eight Node lifecycle tests, 49 Swift resident tests,
51 release-package tests, portable repository checks, and Mac native static
checks. Chrome for Testing 154 on an Apple silicon Mac VM passes 20 live
checks with the real native host/resident and independent HTTP/Chrome oracles.
A target-native window capture confirms blue groups and pointer favicons.
The run covers navigation, site icon changes, missing-icon cache cleanup,
site adoption of the fallback, renamed/user groups, release, debugger-cancel
expiry, extension reload recovery, native reconnect, and resumed control.

Desktop `0.4.10` is published from source
`2331c5bb963155613745da945edd76e14cbca7a2`:

- [Candidate run 36997242156](https://github.com/kzahel/machine-control/actions/runs/36997242156)
  builds and authenticates Mac ARM64/Intel and Windows x64/ARM64. All receipts
  bind workflow attempt `36997242156.1`. Local verification passes both Mac
  publisher signatures, Gatekeeper, notarization/stapling, signed updater
  version, and tamper rejection; both Windows installers pass updater
  signatures, signed version, provenance, inventory, and tamper rejection.
- The exact signed ARM64 app, embedded resident, and bundled extension pass
  the same 20 live checks in the Mac VM under its standing appliance policy.
  Packaged extension bytes match source. A fresh native window capture confirms
  the pointers and blue group. The runner activates the browser immediately
  before capture and allows Chrome to repaint after an earlier stale frame.
- [Promotion run 36999819339](https://github.com/kzahel/machine-control/actions/runs/36999819339)
  publishes those bytes without rebuilding. All 17 re-downloaded public assets
  match candidate bytes and GitHub SHA-256 digests; `latest.json` matches
  apart from its publication timestamp.
- All four website download redirects select `desktop-v0.4.10`. Production
  update routes return matching signed metadata and notes for `0.4.9`, and
  HTTP 204 for current `0.4.10` clients.
- The original appliance app, policy, and resident are restored and doctor is
  ready. Owned fixture/candidate state is removed, all test processes are
  reaped, the initial suspended power state is restored, and the claim is
  released. The stored login credential remains ready and owner-only; no
  credential changes. Unrelated working changes are preserved.

[Public release](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.4.10)
contains all four Mac/Windows targets. This targeted run does not establish
workstation browser approval UX, live same-scope grant replacement, Intel,
Windows marker execution, or physical-Mac acceptance. Worker and Swift tests
cover grant replacement/revocation; prior operator/grant acceptance remains
separate in the [matrix](../desktop-acceptance.md). Linux publication remains
with `0.5.0`. No controller desktop input or outer VM UI is used.

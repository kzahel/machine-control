# 058 — Browser tab indicators and desktop 0.4.10

Status: active

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
Exact signed-candidate and publication results remain pending.

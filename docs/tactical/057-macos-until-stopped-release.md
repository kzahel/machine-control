# 057 — Mac access until stopped and desktop 0.4.9

Status: active

Owning topics: [host control](../../topics/host-control.md),
[native distribution](../../topics/native-distribution.md), and
[macOS resident control](../../topics/macos-resident-control.md).

## Objective and completion conditions

The user installed the stable Tauri app on physical Mac hardware and requested
manually enabled access without the one-hour dropdown limit, then explicitly
requested a commit and new stable release. Ship desktop 0.4.9 with a Mac
**Until I turn it off** choice, selected scopes, visible status, and Stop.

- No timer for manually enabled until-stopped access; bounded agent approvals.
- Stop, session loss, exit, and restart retain their revocation behavior.
- Native/front-end checks pass; exact signed Mac candidates pass targeted VM
  acceptance without manipulating the user's physical desktop.
- All four Mac/Windows packages authenticate at one source and version.
- Publish immutable verified assets and check public downloads/update metadata.

## Boundaries

No remembered access across restart, standing appliance policy, protected host
control, physical-host input during the user's work, or Linux publication.
Use claimed target-native VM control and restore all owned guest test state.
Keep credentials, target selectors, claims, raw captures, and logs private.

## Ordered work

### 1 — implement manual access without a timer

Use a null native grant expiry and explicit `until_stopped` lifetime. The
private local operator advertises support and arms selected scopes. Public
approval requests keep bounded durations. Preserve scope and policy checks,
Stop, session-transition revocation, and access-off startup.

### 2 — authenticate and exercise the signed Mac app

Build all release candidates from clean main. Authenticate both Mac packages,
then test visible manual selection, no-expiry status, fixture effect, Stop,
restart, and bounded agent approval in a claimed Tart VM. Restore the original
app, policy, permissions, fixture state, and initial power state.

### 3 — publish the stable patch

Promote exact accepted candidate bytes through the release script. Verify the
complete public asset set, receipts, signatures, updater version, download
redirects, and production metadata. Tags and published bytes stay immutable.

## Validation and result

Source checks pass: 48 Swift tests including no-timer, scope/revocation and
bounded public-request regressions; frontend production build; strict Tauri
Clippy including the native Swift bridge; portable repository checks.

The earlier public 0.4.8 physical smoke established consent/readiness, visible
approval, off-state refusal, independent AX counter effect, exact-window
capture, keyboard delivery, and caller revocation. Concurrent human input
prevented exact text equality; full physical product acceptance remains open.
The [host topic](../../topics/host-control.md) owns that bounded current result.

Signed 0.4.9 acceptance and publication are pending.

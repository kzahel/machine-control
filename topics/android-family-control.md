# Android-Family Control

Topic: `android-family-control`

Status: active Android-handheld and Quest implementations over a shared ADB
provider; phone credential effect and broader Android profiles remain open.

## Scope

This topic owns the reusable Android/ADB family boundary and the decisions that
separate neutral transport from target-profile policy. It does not make every
ADB target a phone or impose a generic mobile semantic model on Android, Quest,
ChromeOS ARCVM, emulators, TVs, watches, or automotive systems.

## Current implementation

**Current:** [`providers/adb`](../providers/adb) owns dependency-free ADB
executable discovery, device enumeration, exact transport, shell execution,
battery parsing, and wake-state parsing. Both the canonical
[`platforms/android`](../platforms/android/README.md) handheld adapter and
[`platforms/quest`](../platforms/quest/README.md) use it.

The Android-handheld adapter adds explicit eligible-device selection, boot and
boot-generation observation, current-user storage state, keyguard and
credential-kind inspection, failed-password wipe policy, application
deployment/lifecycle, display capture, bounded logs, explicit shell, wake,
keyguard dismissal, and reboot/wait behavior. It emits a minimized common
device doctor and remains a `native` platform interface for operations below
the common target layer.

Quest remains a separate platform profile. Its ADB transport is shared, while
proximity, headset sleep/wake, battery guards, Meta panels, remote recovery
journal, safe final state, and guarded USB-to-wireless transition remain
Quest-owned policy. The Quest adapter supports temporary authenticated
ADB-over-TCP without changing the common target vocabulary. It stores a
private controller-local endpoint receipt and reports the selected transport,
but keeps the address and USB identity out of the common doctor.

## Decisions

**Decision:** Share facilities according to actual platform ancestry:

```text
common target doctor and results
  +-- Android/ADB provider family
  |     +-- Android handheld policy
  |     +-- Quest headset policy
  |     +-- future emulator, ARCVM, TV, and other profiles
  +-- iOS CoreDevice/XCTest family
```

The common layer owns target selection, authorization, readiness dimensions,
capabilities, delivery/effect/evidence, and typed refusal. Android/ADB owns
transport primitives. Each device profile owns lifecycle, protected surfaces,
semantics, and safety policy.

**Decision:** Wireless ADB is an alternate device-host transport, not a second
target identity or weaker authorization route. Quest activation must begin
from the pinned authorized USB device, require secure ADB and a private LAN
address, bind the resulting endpoint to the independently observed device
identity, and refuse identity drift. Controller-local endpoint state may
restore convenience after USB removal, but it is neither repository inventory
nor bearer authority. Transport changes are prohibited during an active Quest
lease and are expected to expire across `adbd` or headset restart.

**Decision:** A phone unlock is a protected handheld operation, not a generic
ADB or Quest command. Ordinary `wake` and `dismiss-keyguard` contain no secret.
Secure `unlock` supports a PIN only and must:

- establish exact device, boot generation, current user, secure PIN field, and
  zero failed-password wipe threshold before reading a secret;
- receive the PIN only from dedicated non-echoing standard input;
- inject within one staged shell-UID helper process so the credential never
  becomes a host ADB or device-process argument;
- submit at most once, clear mutable buffers and staged helper best effort, and
  independently observe keyguard and user-storage effect; and
- refuse passwords, patterns, unknown surfaces, changed generations, unsafe or
  unknown wipe policy, and automatic retry.

## Evidence

**Current — live-tested:** On an attached authorized physical Android
handheld, the adapter selected the device without exposing its serial, emitted
a ready common doctor with boot, interaction, user-storage, capture, and input
state, and returned common status/capabilities through `bin/machine-control`.
The credential helper built from source, staged over ADB, started under the
shell identity, rejected empty input with no output or key injection, and was
removed. An already-unlocked `unlock --json` path confirmed state without
opening the secret channel.

On a physical Quest, the controller independently observed USB enumeration
and ADB `unauthorized` state while Horizon OS failed to render the requested
RSA dialog. Reconnects, ADB server restarts, and a system update did not restore
the dialog. Toggling Developer Mode off and on in the Meta Horizon mobile app
did; after the user accepted the prompt, the common doctor returned ready with
every Quest check passing. AOSP's seven-day inactive-grant default is a
plausible explanation, but the exact Horizon OS expiration behavior and the
incident's idle interval were not measured.

The same Quest live-reported Android API 34, secure ADB, wireless and QR
pairing capability, disabled wireless state, and no persistent TCP property.
The guarded Quest command enabled Android's documented TCP port 5555 route,
connected to the private endpoint, matched its device identity to the USB
observation, and passed the full Quest doctor over Wi-Fi. The local endpoint
receipt was mode `0600`; no serial or address entered the common result or
repository. With an isolated host ADB server exposing no USB transport, the
ordinary pinned common doctor reconnected the receipt, reported its transport
as wireless, and passed every check. Missing, unauthorized, identity-changed,
and non-Quest fallback routes fail closed in unit tests.

**Current — unit-tested:** Tests cover handheld/Quest selection separation,
keyguard and user-state parsing, refusal before secret read, unsafe wipe-policy
refusal, exactly one helper delivery, mutable-buffer clearing, independent
unlock observation, zero retry, absence of the test PIN from results, wireless
private-address and secure-ADB gates, active-lease refusal, exact endpoint
binding, recorded fallback, identity-drift refusal, and observed disable.

**Open:** No real credential was entered during this slice. The helper's PIN
delivery and successful keyguard effect are therefore built and unit-tested,
not yet live- or conformance-tested. Deliberately entering a wrong PIN remains
out of scope.

## Recommended next work

### App-resident provider exploration

**Direction discussed 2026-10-17; not implemented or a scheduled delivery
commitment.** Add a complementary Android app-resident provider that is useful
without developer mode or an armed ADB listener. Preserve the existing richer
ADB route and report the actual provider per operation. The
[Android research](../research/platforms/android.md#app-resident-capabilities-without-adb)
owns source findings, Android API options and limitations.

The ChromeOS composition is a useful architectural reference: several native
facilities supply different capabilities behind one ergonomic facade. On
Android, accessibility, document providers, media, intents and optional ADB
similarly need honest per-operation routing rather than one universal privilege.

- MC owns reusable Android operations, capability/readiness reporting and
  delivery/effect results. YA owns provider sessions, full work UI and product
  entry points; its [Android-host topic](../../yepanywhere/topics/android-host.md#phone-capabilities-and-assistant-entry-points)
  owns that product direction. APK/module packaging is not selected yet.
- Both MCP and a small CLI can call one native implementation. Agents may run
  on the phone or reach it through authenticated transport; neither a local YA
  agent nor a new on-device worker is required for remote control.
- User enablement and grants are separate capabilities: accessibility, chosen
  folders, photos, contacts/calendar, camera/mic, location, notifications and
  optional assistant role. Query only relevant records; do not automatically
  place whole personal databases into provider context.
- Use document tools and explicit workspace import/export for arbitrary SAF
  providers. The separate local primary-storage route now has a live-tested
  resolver with optional all-files authority; see the workspace qualification
  below. Ordinary FUSE mounting and access to other apps' private databases are
  not assumptions.
- Report locked screens, revoked grants, sparse semantic trees, secure capture
  failures and foreground-only facilities explicitly. Do not equate push wake,
  assistant-service liveness, runtime readiness and ADB readiness.
- PRoot and same-UID IPC are not containment from an unrestricted app-UID
  shell. Strong isolation of permission enforcement would need a separate
  identity or authority outside that shell; packaging remains an open question.

A candidate first experiment is for both real provider CLIs, with ADB disabled,
to process a selected/shared document using ordinary Linux tools, perform a
semantic app action, and export a result to an Android app. Use deterministic
fixtures and independently observe effects. Camera and broader shared-storage
access can follow. This records fertile ground without reprioritizing the
existing device implementation work.

**Authorized spike, 2026-10-17:** reuse the persistent Python session's
`Session`/`App` presentation and typed `Transport` boundary. Add a standalone
Android accessibility provider and deterministic native fixture under
`platforms/android/resident-spike`, with a narrow authenticated transport.
Python/model code stays outside the Android service. The service supplies
snapshots, actions and screenshots; it rejects stale references and revoked
authority before dispatch. The first scope is the owned fixture, not arbitrary
personal apps. Preserve existing ADB listeners and accessibility services.

The Python namespace, Android service generation, current observation/action
references and durable provider transcript have separate lifetimes. A service
restart invalidates handles; it does not resume or replay a snippet. Reuse the
current compact output and image sink, but do not claim desktop admission,
claims/audit, screenshot-coordinate control or remote acceptance from the spike.
The prototype transport must disclose those integration limits.

Verify on an explicitly selected attached handheld or emulator: semantic read,
text entry and click with an independent fixture-file oracle; an actual PNG
capture; stale-node and revoked-session refusal; separate interpreter calls
retaining a handle; and phone-local Python execution without an ADB command in
the operation path. ADB may provision and independently observe the test. Real
provider acceptance is a further check, distinct from deterministic Python
execution. Keep concrete selectors, grants, captures and logs private.

**Current — bounded live acceptance:** the
[resident spike](../platforms/android/resident-spike/README.md#acceptance) passes
the persistent Python, semantic effect, PNG, stale-reference, wrong-grant,
outside-scope and live-revocation checks on a physical Pixel 7a. Real on-phone
Codex and Claude sessions also passed through that bridge with independent
fixture effects and inline images. Content events alone no longer expire every
reference; dispatch rechecks live native node membership. Recoverable stale
refusals preserve ownership for an explicit fresh observation. The provider is
fixture-scoped and does not replace the existing Android adapter or qualify
broader phone capabilities, remote use or production session integration.

### Planned session cleanup and independent data capabilities

**Direction, 2026-10-18; production integration remains future work.** Keep
one native Android broker with separate client interpreters per provider
conversation. Interpreter state, Android permission grants, active resource
ownership and historical audit are distinct. YA session end/reaping must close
or kill its MCP/interpreter process tree; native EOF releases ownership without
requiring the agent to call a cleanup tool. A broker watchdog/heartbeat and
bounded lease expiry cover lost connections or failed cleanup. An orphan MCP
process must not renew ownership forever after its YA session ends.

The native MC broker owns authoritative active leases and terminal reasons;
YA's session database must not become the device lock authority. Existing MC
adapters use private JSON resource/queue records and SQLite audit history. An
Android SQLite lease/history store is a candidate, not a selected or implemented
migration. Persisted active rows must be fenced by runtime generation and live
ownership; they cannot keep a resource reserved after owner loss. Record normal
release, session end/reap, disconnect, heartbeat loss, expiry and revocation as
distinct terminal reasons. Audit-store failure must not prevent release.

Acquire UI ownership for a coherent action sequence, not for the lifetime of
an idle conversation. Releasing that ownership should not require destroying
Python variables. Reacquisition requires a fresh observation; uncertain actions
are never replayed. Phone users retain physical control.

Photo/document reads are a separate capability plane and must not acquire the
exclusive UI claim. Several authorized sessions may read selected media and
SAF documents concurrently. Onboarding pickers still require user interaction;
subsequent reads use native providers without UI automation or accessibility.
Write coordination, if later added, should address a particular document or
workspace rather than reserving the whole phone.

**Current — live-tested data spike, 2026-10-18:** the separate native data
service uses selected photos, a persistable read-only SAF tree, ContentResolver
and explicit Linux workspace export. JSTorrent informed the grant lifecycle;
no source or storage engine was copied. Physical acceptance established
concurrent independent readers without accessibility, original-byte export and
inline thumbnails, app-restart permission persistence and live revocation.
[The spike acceptance](../platforms/android/resident-spike/README.md#acceptance)
owns details and limits. Broad gallery permissions, arbitrary URIs, writable
trees and filesystem mounting remain outside this experiment. Production YA
onboarding, per-session capability grants, lease/audit integration and exported
file retention remain future work. Revocation cannot erase copies already
exported into an agent workspace.

### Durable local workspace qualification

**Current — built and live-tested, 2026-10-18:**
[`platforms/android/storage`](../platforms/android/storage/README.md) owns the
reusable, dependency-free `LocalWorkspace` resolver. It qualifies a persisted
read/write tree from Android's built-in primary external-storage provider,
checks actual all-files authority and verifies an accessible canonical folder.
It is not a generic SAF-to-path converter or a mount implementation.

YA's separate disposable fixture consumed this source and bound the selected
folder directly at `/workspace` in its existing Alpine/PRoot payload. On Pixel
7a/API 37, both real provider CLIs wrote through normal file tools and shell;
independent hashes survived restart, fixture data clear and reinstall followed
by real reselection. SAF and broad authority were revoked/repaired separately.
See the [YA acceptance and filesystem limits](../../yepanywhere/packages/android-host/workspace-spike/README.md#evidence).
The signed-in host and existing documents were preserved; fixture cleanup passed.

**Decision:** Keep this direct local-folder route distinct from future bucket-like
SAF CLI/document operations for arbitrary providers. SAF selection alone does not
grant raw access. PRoot does not confine broad app-UID authority to one directory;
SAF revocation only blocks resolver admission while all-files remains active.
Runtime binaries, credentials and internal live databases remain private.
Production packaging, YA onboarding/session lifecycle, running-handle revocation
and per-session grants/audit remain open. The existing read-only resident-data
service remains a separate experiment.

### Existing device implementation follow-ups

- Run one supervised correct-PIN acceptance through the hidden prompt and
  retain only redacted delivery/effect evidence.
- Add a compact UIAutomator semantic adapter and deterministic Android fixture,
  then compare its snapshot/action behavior with the current iOS XCTest route.
- Add physical versus emulator identity and a separate emulator lifecycle
  profile.
- Decide how ChromeOS-local ARCVM ADB projects through this provider without
  moving its lifecycle out of the ChromeOS platform.
- Add private inventory for the actual Android handheld without publishing its
  serial or controller route.

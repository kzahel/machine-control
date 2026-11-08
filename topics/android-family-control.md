# Android-Family Control

Topic: `android-family-control`

Status: active Android-handheld and Quest implementations over a shared ADB
provider; ordinary phone PIN unlock is live-tested on one physical profile.
Unlock with initially locked user storage and broader Android profiles remain
open.

## Scope

This topic owns the reusable Android/ADB family boundary and the decisions that
separate neutral transport from target-profile policy. It does not make every
ADB target a phone or impose a generic mobile semantic model on Android, Quest,
ChromeOS ARCVM, emulators, TVs, watches, or automotive systems.

## Current implementation

**Current (2026-11-01), confirmed defect:** unavailable-device doctor
formatting references an undefined `status` and raises `NameError`, reproduced
offline without device operations. The
[journal review](../gaps/2026-11-01-usage-journal-review.md#android-unavailable-state-doctor)
owns the source finding and proposed regression coverage; this remains unfixed.

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
- read the PIN only after preflight, from a private inventory file locator or
  dedicated non-echoing standard input;
- inject within one staged shell-UID helper process so the credential never
  becomes a host ADB or device-process argument;
- submit at most once, clear mutable buffers and staged helper best effort, and
  independently observe keyguard and user-storage effect; and
- refuse passwords, patterns, unknown surfaces, changed generations, unsafe or
  unknown wipe policy, and automatic retry.

**Current:** `ANDROID_TESTBED_PIN_FILE` carries only the controller-local
locator from private inventory. `unlock` uses it automatically; `--stdin`
explicitly overrides it. The source remains unopened until preflight succeeds.
Configured files require an explicit device selector and are checked for type,
ownership and permissions. See the [Android setup](../platforms/android/README.md#pin-unlock-boundary).

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

**Current — physical PIN unlock, live-tested 2026-10-25:** the common CLI's
native adapter escape hatch unlocked a physical API-37 handheld using both
dedicated stdin and its inventory-configured host PIN file. The configured-file
acceptance followed an owner-reported reboot with a changed boot generation;
user storage was already available before that attempt. Each accepted attempt
confirmed delivery and keyguard/user-storage effect with one submission and
zero retries; subsequent read-only doctors also reported unlocked interaction.
The credential never appeared in output or retained evidence, and temporary
device files were removed.
The [Android research](../research/platforms/android.md#existing-adb-implementation)
owns the observation, stdin-isolation and helper-initialization findings.

**Open:** First unlock from initially locked user storage, broader OEM coverage
and full credential conformance remain unaccepted. Deliberately entering a wrong
PIN remains out of scope. An uncertain credential delivery still prohibits
automatic retry.

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

**Open (2026-11-01), observed coordination gap:** the current common Android
ADB target declares claims unsupported. Interactive testing reported unrelated
foreground changes and stopped rather than guessing another caller's ownership.
Concurrent-agent interference is suspected, not attributed. Extend the native
ownership contract to the actual device UI across participating routes, with
exact-device identity, bounded ownership and loss/cleanup semantics. YA remains
the session coordinator, not the authoritative device lock. The
[journal review](../gaps/2026-11-01-usage-journal-review.md) records the triage.

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

**Decision:** Support multiple named folder registrations with optional direct
local-folder access and explicit bucket-like SAF CLI/document operations for
arbitrary providers. One root may support both methods; permission and health
remain distinct per method/root. Broad storage access is optional, and SAF tools
must work without it. YA owns shortcut names, UI, project/runtime integration and
reselection; MC owns reusable native qualification and document operations. See
[YA's workspace contract](../../yepanywhere/packages/android-host/docs/workspaces.md).
**Current:** MC now supplies bounded writable `SafDocuments` operations; the
experimental YA host consumes them for `ya saf` against its named roots and
uses `LocalWorkspace` for independent optional direct mappings. YA packages MC's
MIT notice. [Storage API and acceptance](../platforms/android/storage/README.md)
record ownership, limits and physical evidence. No reference-project source was
copied. The resident-data experiment has not been extended with these mutations.

SAF selection alone does not grant raw access. PRoot does not confine broad
app-UID authority to chosen directories; SAF revocation only blocks resolver
admission while all-files remains active.
Runtime binaries, credentials and internal live databases remain private.
Store-policy acceptance, running-handle revocation and per-session grants/audit
remain open. YA now owns experimental onboarding and project/session integration. The existing read-only resident-data
service remains a separate experiment.

### Existing device implementation follow-ups

- Qualify first unlock after reboot and broader OEM PIN surfaces separately
  from the accepted ordinary host-file screen-unlock route.
- Add a compact UIAutomator semantic adapter and deterministic Android fixture,
  then compare its snapshot/action behavior with the current iOS XCTest route.
- Add physical versus emulator identity and a separate emulator lifecycle
  profile.
- Decide how ChromeOS-local ARCVM ADB projects through this provider without
  moving its lifecycle out of the ChromeOS platform.
- Add private inventory for the actual Android handheld without publishing its
  serial or controller route.

### Planned: handheld as a Bluetooth HID keyboard

**First implementation (2026-11-08):**
[`platforms/android/hid-keyboard`](../platforms/android/hid-keyboard/README.md).
The proposal below is kept as the original design; see "Implementation results"
after the trial for what changed.

Let an attached Android handheld act as a
Bluetooth keyboard for other targets, so tedious typing during bootstrap and
recovery (for example the ChromeOS VT2 download-and-activate commands) no longer
needs a human at the target's keyboard. Android 9 and later expose this through
the public `BluetoothHidDevice` API; no root is required.

Proposed shape:

- A small Kotlin app under `platforms/android/`, beside the resident spike's
  Gradle build: a foreground service registers a keyboard (later possibly a
  mouse) HID descriptor, pairs once per target, and reconnects to bonded hosts.
- Control through a token-authenticated loopback socket reached by
  `adb forward`, following the resident-spike transport, exposed as a target
  command such as `testbed -- hid type --stdin`. Secrets travel only on stdin
  or that socket, never in process arguments, matching the PIN boundary.
- HID sends key positions, so the target's layout decides the characters.
  Carry a per-target layout (QWERTY, Dvorak, ...) and reuse the ChromeOS
  client's layout tables rather than assuming US QWERTY.
- Operator arming with expiry, a visible notification, and Stop, as in the
  resident spike; typing into other machines is a powerful capability.

Limits to record honestly: Bluetooth keyboards need the target OS running and
a prior pairing through the target's own UI, which recovery or powerwash
erases. They generally do not work in firmware, recovery, developer-mode, BIOS,
or UEFI screens. Those need a USB HID gadget (for example a Pico or Pi Zero
class device); an unrooted handheld cannot be a USB keyboard.

References, licenses checked 2026-11-08: `ginkage/wearmouse` (Apache-2.0,
Google sample for the HID Device API) as the primary plumbing reference and
`raghavk92/Kontroller` (Apache-2.0, phone as keyboard and mouse) for keyboard
reports; Apache-2.0 code may be adapted here with its notice retained.
`arnav-kr/Bluke` (AGPL-3.0) and Bluetooth Remote (GPL-3.0) are behavior
references only; do not copy their code into this MIT repository.

#### Trial: commercial HID app against the ChromeOS testbed (2026-11-08)

Before building anything we paired the closed-source "Bluetooth Keyboard &
Mouse" app (`io.appground.blek` 6.25.2) on an unrooted Android 16 handheld with
the signed-in ChromeOS LTC testbed, which runs the Floss Bluetooth stack.
The phone was driven over ADB; the Chromebook through `testbed --`.

How each of the app's connection options fared:

| App option | Who starts | Result on ChromeOS |
| --- | --- | --- |
| A, "Search device" | Phone scans | The Chromebook never showed up in the phone's system device chooser, which listed only a nearby BLE light. ChromeOS was not discoverable even with Bluetooth settings or its pairing dialog open (Floss `GetDiscoverable` returned false). |
| B, "Turn on discoverability" | Chromebook scans | `btmon` on the Chromebook received the phone's inquiry results (class `0x5a020c`, Phone / Smart phone), but "Pair new device" never listed it in over 30 seconds. ChromeOS appears to filter phone-class devices out of that list. After bonding, Settings calls it "Device is a phone." |
| C, MAC address | Phone pages | Failed with HCI reason 4 (Page Timeout). No connection request reached the Chromebook's HCI. |

What worked: put the app in mode B, then start the bond from the Chromebook as
root through Floss D-Bus:

```sh
gdbus call --system --dest org.chromium.bluetooth \
  --object-path /org/chromium/bluetooth/hci0/adapter \
  --method org.chromium.bluetooth.Bluetooth.CreateBond \
  "{'address': <'PHONE_BT_ADDR'>, 'name': <'PHONE_NAME'>}" 1
```

Pairing used numeric comparison: the phone showed a six-digit code, we tapped
Pair on the phone, and confirmed on the Chromebook with `SetPairingConfirmation`
(same device dict, `true`). The bond completed and HID connected right away.

What worked once connected:

- **Typing:** keys typed one at a time arrived exactly.
- **Burst typing lost text:** the app's "Direct" mode diffs Android IME text.
  A single fast `adb shell input text` burst lost whole words: "QUICK brown fox
  jumps 99" arrived as "QUICK own jumps " and "hello btkb test 123" as
  "hello test".
- **Touchpad:** pointer movement, left click, and the scroll strip all worked;
  a test page received `mousemove`, `click`, and `wheel` events.

Implications for our app:

- Phone-class devices are effectively undiscoverable to the ChromeOS pairing
  UI, and an unrooted app cannot change the adapter's class of device.
  Classic `BluetoothHidDevice` therefore needs the host to start pairing:
  - on a testbed we already control, the Floss D-Bus bond above (scriptable,
    and worth adding as a ChromeOS target command);
  - otherwise a host whose UI still lists phones.

  For an unpaired, uncontrolled ChromeOS target, investigate a BLE HOGP
  peripheral with a keyboard appearance, or the USB HID gadget already noted.
- Defaulting to "discoverable and waiting" is the right default (option B).
  The search flow (option A) depends on the host being discoverable, which
  ChromeOS is not. The app should still show the handheld's name and status
  prominently.
- Never route agent text through an IME diff. Accept text over the control
  socket and emit paced key-down/key-up HID reports. Then confirm a round
  trip, for example by reading a field back on targets that allow it.
- Gboard suggested the operator's account emails above the app's text field,
  so an agent-only app should avoid showing an IME at all.
- The app's own MAC entry uses a custom hex keypad that dropped fast ADB taps.
  An agent-facing app should take addresses through its API, not through
  on-screen widgets.

#### Implementation results (2026-11-08)

The `MC HID` app and `hidctl.py` follow the proposal. The differences:

- **Language:** it is written in Java with no AndroidX, matching the resident
  spike.
- **Minimum Android version:** minSdk is 31, because the Bluetooth runtime
  permissions start there.
- **Layout and mouse:** layouts are `us` and `dvorak`, and the mouse is in the
  first version.

Against the same testbed:

- **Exact typing:** 1000 random printable characters typed at about 20 per
  second read back exactly, on two separate bonds. Pointer, click, wheel and
  the on-screen touchpad all worked.
- **Autocorrect:** ChromeOS autocorrects physical-keyboard text in ordinary
  fields, Bluetooth keyboards included ("teh" became "the", a lone "i" became
  "I", and "ym" became "my"). These looked like lost or reordered keystrokes
  until an `autocorrect=off` textarea read back exactly. Exact-text checks
  need such a field or a terminal.
- **First HID connection must come from the host:** on a fresh bond, Floss
  rejects a first HID connection that the device opens ("Unexpected incoming
  HID connection, wait for local connect request"), and the half-open state
  then also broke host-initiated attempts until the bond was redone. After
  bonding, the host must call `ConnectAllEnabledProfiles` itself. Once that
  has happened, the device reconnects on its own after restarts.
- **Inquiry before bonding:** after `RemoveBond`, `CreateBond` without a prior
  inquiry failed with a connection timeout. `StartDiscovery` while the
  handheld is discoverable fixed it.
- **Disconnect unpairs:** Android implements
  `BluetoothHidDevice.disconnect()` as a virtual-cable unplug, which removes
  the bond on the handheld. The API therefore offers only an explicitly
  confirmed `unplug`, not a plain disconnect.
- **Review:** an independent agent review shaped the safety model. Input
  can be bound to an expected host, and `type` refuses while the host reports
  Caps Lock. The CLI challenges the listener before sending the token, and
  keyboard requests never queue. Agent-held buttons release themselves, and
  only the ADB shell can arm. An operator Stop sticks until a person taps
  Start.
- **Scripted pairing:** `hidctl.py pair-floss --ssh ALIAS` runs inquiry,
  `CreateBond`, both numeric-comparison confirmations and the host-side HID
  connect in about 13 seconds. It accepts the comparison without a person
  reading both codes, so it is only for controlled testbeds.

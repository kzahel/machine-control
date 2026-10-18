# Android Control Research

Status: adopted shared ADB provider and physical-handheld adapter; credential
effect and broader semantic/device-profile conformance remain open.

## Native foundation

ADB already provides discovery, transport, shell, installation, lifecycle,
files, screenshots, input, logs, port forwarding, and debugging. UIAutomator or
an accessibility helper supplies semantic trees and actions when needed. The
agent normally runs on an authorized device host; specialized Android-hosted
agents remain an optional placement.

ARCVM on ChromeOS, phones/tablets, emulators, Quest, TVs, and other derivatives
share ADB ancestry but have different lifecycle, wake, display, protected UI,
and recovery constraints.

## Candidate routes

| Route | Evidence | Current role |
| --- | --- | --- |
| ADB | mature platform facility; adopted by several testbeds | Administration, lifecycle, debug, capture/input baseline |
| UIAutomator/accessibility | established platform semantic route | Preferred semantic layer where available |
| [Agent Device](../providers/agent-device.md) | `upstream-claimed` generally; adopted through the iOS family rather than generic Android here | Candidate compact workflow/adapter over Android facilities |
| [native-devtools-mcp](../providers/native-devtools-mcp.md) | `source-reviewed` integration | ADB/tool aggregation reference |

## Current direction

### App-resident capabilities without ADB

**Source-reviewed reference, 2026-10-17:**
[Buddy's Android tool implementation](https://github.com/ghorbelhamdi/buddy-android/blob/dc6c0a965c8d72042a12d07ffa5203ccbd541cd2/app/src/main/java/app/buddy/assistant/Tools.java)
walks accessibility windows/nodes, invokes semantic actions and gestures, and
captures screenshots through `AccessibilityService`. Its
[MCP server](https://github.com/ghorbelhamdi/buddy-android/blob/dc6c0a965c8d72042a12d07ffa5203ccbd541cd2/app/src/main/java/app/buddy/assistant/McpServer.java)
binds loopback and checks a bearer token. MCP exposes native Android authority;
it does not supply that authority. This is source inspection, not an MC
implementation or physical-device acceptance of these operations.

**Platform-documented candidates, not MC-tested:**

| Facility | Useful scope and material boundary |
| --- | --- |
| [Accessibility service](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService) | Semantic observations/actions, gestures and screenshots after user enablement; sparse trees and secure content remain limitations. |
| [Storage Access Framework](https://developer.android.com/training/data-storage/shared/documents-files) | Persistable access to chosen documents/trees through content URIs; not automatic POSIX paths, with restricted directory choices. |
| [All-files access](https://developer.android.com/training/data-storage/manage-all-files) | Optional broad shared-storage access through real paths; excludes other apps' private storage. Primary-volume PRoot route live-tested below. |
| [Photo picker](https://developer.android.com/training/data-storage/shared/photo-picker) and [MediaStore](https://developer.android.com/training/data-storage/shared/media) | Selected images/videos, including supported cloud selections, or permission-backed media queries; not unrestricted cloud-library access. |
| [Contacts](https://developer.android.com/identity/providers/contacts-provider) and [calendar](https://developer.android.com/identity/providers/calendar-provider) | Query/mutate shared providers with appropriate permissions; system intents can hand individual edits to their owning apps. |
| [Common intents](https://developer.android.com/guide/components/intents-common) | Compose messages, open the dialer/maps, create alarms/timers and share results; handing off an intent is not proof of the resulting action. |
| Camera, microphone and [location](https://developer.android.com/develop/sensors-and-location/location/permissions) | Physical-world observations and voice input, subject to individual grants and [foreground/while-in-use restrictions](https://developer.android.com/develop/background-work/services/fgs/restrictions-bg-start). |
| [Notification listener](https://developer.android.com/reference/android/service/notification/NotificationListenerService) | Observe exposed notifications/actions after separate user enablement; not universal message history. |
| [Assistant role](https://developer.android.com/training/articles/assistant) | System invocation and app-provided assist structure/screenshots; custom hotword, locked-screen and heavy-runtime survival remain separate experiments. |
| [Health Connect](https://developer.android.com/health-and-fitness/health-connect/get-started) | Optional access to available health records under data-type-specific grants. |

For SAF, start with document tools and explicit import/export to an ordinary
Linux workspace. A real FUSE mount is not the baseline: AOSP's
[untrusted-app policy](https://android.googlesource.com/platform/system/sepolicy/+/refs/heads/main/private/app_neverallows.te)
denies ordinary apps access to `/dev/fuse`, and PRoot does not change that.
An inverse [DocumentsProvider](https://developer.android.com/guide/topics/providers/create-document-provider)
could expose selected agent workspace files to Android document-aware apps.
[Termux:API](https://github.com/termux/termux-api) is a reference for bridging
native device facilities into command-line programs, not an adopted dependency.

See the [resident-provider exploration](../../topics/android-family-control.md#app-resident-provider-exploration)
for proposed ownership and validation. Existing ADB implementation status below
is unchanged.

**Built/live-tested, 2026-10-17:** the owned
[fixture-scoped resident spike](../../platforms/android/resident-spike/README.md)
reuses MC's unchanged Python session/interpreter with a native accessibility
provider. A physical Pixel 7a/API 37 passed eight persistent snippets, semantic
text/click with an independent fixture-file witness, window PNG capture,
same-label replacement/stale-reference refusal, invalid-grant refusal and
outside-package refusal. Python ran inside the YA app's Alpine/PRoot under its
ordinary kernel app UID/SELinux domain; the fixture service had its own app UID.
ADB provisioned and independently observed the test, but the phone-local control
channel used direct authenticated loopback with no ADB command or forwarding.
This is bounded deterministic acceptance, not real-provider, remote, reboot,
background, desktop-claims/audit or stable-observation-ID/diff qualification.

**Real-provider follow-up:** Codex and Claude subsequently passed the same
phone-local bridge with seven and six actual MCP calls respectively, separate
interpreter calls retaining state, independently verified fixture effects and
one actual inline PNG result each. Inference used temporary AAR subscription
grants and an owned USB reverse; native control still used direct phone
loopback. Live operator revocation closed ownership and refused re-admission,
and an externally replaced same-label input rejected its outstanding reference.
Ordinary content events had initially over-invalidated references; the provider
now rechecks live node membership and preserves ownership on recoverable stale
refusals. The [spike acceptance](../../platforms/android/resident-spike/README.md#acceptance)
owns the evidence limits. This does not establish remote, reboot/background,
general app, claims/audit or stable-ID/diff acceptance.

### Selected media and SAF reference study (2026-10-18)

Read-only source study of the MIT-licensed sibling JSTorrent checkout at
`0cd892064cd772cc6a71f9eec793d5878578e04b`:

- `clients/android/app/src/main/java/org/rstorrent/bootstrap/MainActivity.kt`:
  accept actual picker results and persist only returned grant flags.
- `ProductSafDocuments.kt`: recheck persisted grants; use ContentResolver and
  DocumentsContract rather than inventing filesystem paths; validate path
  components and reject ambiguous duplicate child names; support cancellation.
- `ProductSafRootRegistry.kt`: durable root identity is distinct from grant
  health, so revoked roots remain understandable and repairable.
- `experiments/android-storage-probe/run_probe.py`: use a dedicated child of
  Downloads, exercise the actual system tree picker, then verify persistence
  after process restart and release only the owned grant/fixtures.

Adopt these boundary/lifecycle lessons without copying source or its storage
engine. The MC experiment starts narrower: selected-photo and SAF read access,
opaque document handles, bounded listings/transfers, native thumbnail export,
and concurrent readers without a UI claim. Photo selection uses Android's
system picker, not a broad gallery permission. A tree grant stays a content URI;
Linux tools receive explicit exported bytes. Provider mutation, duplicate-name
path resolution and descriptor-based random-write integration remain outside
this first read-only slice.

**Current — live-tested, 2026-10-18:** the physical Pixel 7a passed actual photo
and SAF picker consent, simultaneous independent readers under the YA app UID,
Linux byte export/thumbnail presentation, persisted grants after app restart
and live per-capability revocation. Accessibility settings were unchanged;
the data service does not require the accessibility service or a UI owner.
[Acceptance and limits](../../platforms/android/resident-spike/README.md#acceptance)
remain scoped to local synthetic media and documents. Cloud/provider availability,
reboot/Doze, writable access and production lifecycle integration are unqualified.

### Direct local shared-folder workspace (2026-10-18)

**Current — source-reviewed, built and live-tested:** the sibling MIT-licensed
Web Server Chrome reference keeps SAF content URIs separate from filesystem
roots and checks actual all-files access. JSTorrent's writable document creation,
seekable-descriptor handoff and native positional I/O demonstrate document
operations without supplying a POSIX namespace for unmodified programs. No
reference-project code was copied into this implementation.

MC now owns a narrow [local workspace resolver](../../platforms/android/storage/README.md).
YA owns its disposable Android fixture, shared Alpine/PRoot mapping and physical
acceptance. Pixel 7a/API 37 passed actual picker plus separate Settings consent,
SAF/raw sentinel agreement, both real Codex/Claude file-edit and shell writes,
external SHA-256 checks, process restart, grant revocation/repair and recovery
after fixture data clear and reinstall. The
[YA evidence](../../../yepanywhere/packages/android-host/workspace-spike/README.md#evidence)
owns commands, measured semantics and cleanup.

The tested shared storage is case-insensitive, rejects symlinks/execution,
ignores executable mode changes and returns ENOSYS for `flock`. POSIX record
locks and bounded SQLite WAL contention passed. Git required rename-based object
publication and explicit repository trust under simulated root. This qualifies
ordinary file editing, not a general Linux filesystem or crash/power-loss safety.
All-files authority outlives SAF grant revocation and is broader than PRoot's
visible workspace; fresh raw access failed when all-files was disabled. Existing
handles and running-session revocation remain unqualified. Arbitrary SAF
providers, removable volumes, production YA integration and store-policy
acceptance were not tested.

### Existing ADB implementation

**Decision:** Do not reimplement ADB. Add consistent target selection,
capability/result vocabulary, semantic adapters, leases, and evidence around
it. Keep Quest- and device-specific policy in their authoritative testbeds.

**Current — built and live-tested:** [`providers/adb`](../../providers/adb)
now supplies neutral ADB discovery, enumeration, transport, shell, battery, and
wake parsing to both [`platforms/android`](../../platforms/android/README.md)
and [`platforms/quest`](../../platforms/quest/README.md). The physical-handheld
adapter is live-tested for exact selection, common doctor/status/capabilities,
boot/user-storage/keyguard observation, and secret-helper build/start/refusal.
Quest retains separate headset lifecycle and safety policy.

**Current — Quest authorization recovery, live-tested 2026-08-16:** The Quest
USB device remained present and ADB reported the exact target as
`unauthorized`, but Horizon OS rendered no RSA confirmation after USB
reconnects, ADB server restarts, or a system update. The controller's ADB key
had not changed. Turning Developer Mode off and on in the Meta Horizon mobile
app restored the prompt; user acceptance returned the minimized Quest doctor
to ready with every check passing. AOSP defines
[`604800000` ms (seven days) as the default inactive ADB grant window](https://android.googlesource.com/platform/frameworks/base/+/4e984e55033439223fb45e91a561b85e57248067/core/java/android/provider/Settings.java)
and applies it to
[`Always allow` keys](https://android.googlesource.com/platform/frameworks/base/+/master/services/core/java/com/android/server/adb/AdbDebuggingManager.java).
The live Quest's `adb_allowed_connection_time` setting was unset, but Meta's
effective framework default and the incident's idle interval were not directly
established; seven-day expiry remains a plausible trigger rather than a proven
Horizon OS cause.

**Current — Quest wireless ADB, built and live-tested 2026-08-16:** The updated
Quest's `cmd adb` service reported Wi-Fi and QR pairing support, while secure
ADB was enabled, wireless debugging was off, and service/persistent TCP port
properties were empty. The Quest adapter now wraps Android's documented
[`adb tcpip 5555` route](https://developer.android.com/tools/adb#wireless)
without root. It requires the pinned authorized USB device, a private
non-link-local address, secure ADB, no active lease, and an exact identity and
Quest-profile match at the wireless endpoint. Live enable matched the network
route to the USB-observed identity and passed the full Quest doctor over TCP;
the private endpoint receipt was mode `0600`. An isolated host ADB server with
no USB transport then proved that the ordinary pinned common doctor reconnects
the receipt, reports the wireless route, and passes every check. Disable,
endpoint drift, and refusal paths are unit-tested. The route is temporary
across `adbd` or headset restart and does not claim that Horizon OS exposes
Android's normal on-device QR-pairing UI.

**Current — unit-tested:** The phone PIN route refuses before reading a secret
unless the exact generation, secure PIN field, and zero failed-password wipe
threshold are established. It carries the PIN only through standard input to a
one-shot shell-UID helper, delivers once, clears buffers best effort, observes
keyguard/user-storage effect, and prohibits retry. No real PIN effect was
live-tested in this slice.

**Open:** Select and conformance-test the default UIAutomator/accessibility
adapter, define emulator versus physical identity, and expose ARCVM through the
ChromeOS-local ADB proxy without pretending Chrome accessibility covers Android
application internals. Run one supervised correct-PIN acceptance before
promoting credential delivery above `built`/unit-tested evidence.

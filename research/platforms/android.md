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

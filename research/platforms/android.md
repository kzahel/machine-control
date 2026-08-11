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

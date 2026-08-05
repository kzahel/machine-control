# Android Control Research

Status: mature platform foundation identified; common facade and broader device
conformance remain to be organized.

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

**Open:** Select and conformance-test the default UIAutomator/accessibility
adapter, define emulator versus physical identity, and expose ARCVM through the
ChromeOS-local ADB proxy without pretending Chrome accessibility covers Android
application internals.

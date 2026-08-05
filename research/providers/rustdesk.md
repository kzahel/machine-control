# RustDesk

Upstream: [rustdesk/rustdesk](https://github.com/rustdesk/rustdesk)

Declared license:
[AGPL-3.0](https://github.com/rustdesk/rustdesk/blob/master/LICENCE) for the
top-level project. Its bundled libraries and platform assets require their own
license review. The strong copyleft and network-use terms are material if code
is reused or a modified service is deployed.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows service/session architecture | `source-reviewed` | The recent spike inspected service, desktop switching, capture, and input paths; RustDesk was not installed or live-tested. |
| Other platforms | `upstream-claimed` in this corpus | Broad remote-desktop support is outside the current source-review conclusion. |

Exact source evidence is pinned by `machine-control-spike`; the focused result
is in the [Windows findings](../../../machine-control-spike/docs/windows-findings.md#rustdesk-comparison).

## Architecture and depth

RustDesk is a full remote-desktop product, not a narrow agent semantic provider.
Its Windows service follows the active console/RDP session, launches a
privileged server with a session token, opens and switches to the current input
desktop, and recreates input/capture paths after desktop changes. Its protocol
reports service/UAC state to the remote side.

This demonstrates why a service can reach UAC and interactive desktops in ways
an ordinary user process cannot. It also demonstrates the size of the trust,
attack, protocol, and lifecycle boundary that would be imported by treating a
remote-desktop product as the agent's protected broker.

## North Star fit

RustDesk is valuable as a reference for session services, desktop switching,
capture, input, and recovery. It lacks the compact semantic/effect contract and
has a much broader authority surface than the desired narrow protected broker.
Its AGPL-3.0 license is also materially different from the permissively
licensed provider candidates.

## Current disposition

**Decision:** Do not import RustDesk wholesale as the resident semantic or
protected-control foundation. Retain it as a source reference and possible
human remote-viewing/recovery product under an explicit independent boundary.

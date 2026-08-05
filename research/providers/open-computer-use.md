# Open Computer Use

Upstream:
[iFurySt/open-codex-computer-use](https://github.com/iFurySt/open-codex-computer-use)

Declared license:
[MIT](https://github.com/iFurySt/open-codex-computer-use/blob/main/LICENSE).
Upstream also publishes third-party notices; those must be included in a
distribution review.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| macOS | `source-reviewed` | AX, ScreenCaptureKit, app-posted input, explicit SkyLight background click, permission app, fixtures, and smoke/stress paths were inspected at the spike pin. |
| Windows | `source-reviewed` | UIA and Win32 message runtime exists; it requires the logged-in desktop session. No local live test. |
| Linux | `source-reviewed` | AT-SPI runtime and session discovery exist; Wayland capture/input remains compositor-dependent and best effort. No local live test. |

The exact review revision is already recorded in
[`machine-control-spike/reference-pins.json`](../../../machine-control-spike/reference-pins.json).

## Architecture and depth

Open Computer Use is explicitly designed as an open CLI and stdio MCP service
matching the compact Computer Use tool shape across macOS, Windows, and Linux.
It exposes application listing/state, snapshot-bound element indices, semantic
actions, text/key/scroll operations, and screenshots. It can be installed into
multiple agent runtimes rather than depending on one proprietary host.

The macOS implementation is the deepest. It uses AX and ScreenCaptureKit,
normally avoids the real pointer, and has explicit `app_post`, private
SkyLight `sky_click`, and opt-in global routes. Failed explicit methods do not
silently fall back. The background SkyLight route binds a current on-screen
window in the same Space and requires revalidation after movement, hiding,
minimization, or Space changes.

Windows uses UIA and Win32 message fallbacks. Linux uses AT-SPI through the
logged-in desktop bus. Both require a real interactive desktop session. The
public shape is primarily application/main-window oriented rather than the
full exact `(pid, window_id)` session/result contract provided by Cua.

The repository contains deterministic fixtures, smoke/stress tests, agent
smokes, a permission-onboarding application, and explicit reliability notes.

## North Star fit

Open Computer Use is an important provider-first candidate because it aims at
the exact ergonomic feeling the user values: a compact, agent-neutral Computer
Use interface backed by native accessibility on all three desktop platforms.
It is smaller and more directly Computer-Use-shaped than Cua, but currently has
less explicit authorization, remote-carrier, action/effect, session,
multi-window, and cross-platform conformance machinery.

## Current disposition

**Proposal:** Keep Open Computer Use in the first common-provider comparison
set with Cua and Touchpoint. Do not repeat broad platform exploration; compare
its compact ergonomics, exact-window boundary, result truthfulness, background
effects, fixture oracles, and embeddable/remote service posture on the Windows
acceptance cases.

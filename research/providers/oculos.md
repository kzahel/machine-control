# OculOS

Upstream: [huseyinstif/oculos](https://github.com/huseyinstif/oculos)

Declared license: [MIT](https://github.com/huseyinstif/oculos/blob/main/LICENSE)
for the repository.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `source-reviewed` | Resident REST/MCP shape and Windows automation implementation were inspected; no live test. |
| macOS | `source-reviewed` | Adapter exists, but window bounds, exact targeting, and capture/action depth are incomplete. |
| Linux | `source-reviewed` | Adapter exists, but capture and input depth do not match the advertised universal shape. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

OculOS has a useful resident-daemon concept: REST and MCP, sessions,
session-scoped element references, accessibility trees, find/actions,
screenshots, window APIs, a dashboard, and event streaming. This resembles the
service/facade boundary sought by the North Star.

The current source is materially deeper on Windows than macOS or Linux. Some
advertised per-window operations are default unsupported implementations, and
parts of macOS identity/geometry handling are incomplete. Current CI primarily
establishes buildability and SDK import behavior rather than live application
effects.

## North Star fit

The daemon and protocol layout are useful references. The implementation does
not yet justify treating the same advertised operation as equal across its
three platforms—an example of why the corpus tracks claim-specific evidence.

## Current disposition

**Decision:** Retain OculOS as a service-shape and Rust implementation
reference, not a validated common provider.

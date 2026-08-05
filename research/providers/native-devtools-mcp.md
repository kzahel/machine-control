# native-devtools-mcp

Upstream:
[sh3ll3x3c/native-devtools-mcp](https://github.com/sh3ll3x3c/native-devtools-mcp)

Declared license:
[MIT](https://github.com/sh3ll3x3c/native-devtools-mcp/blob/main/LICENSE) for
the repository.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| macOS | `source-reviewed` | Exact-window capture, AX snapshots and ref actions, OCR, input, CDP, and permission behavior were inspected. |
| Windows | `source-reviewed` | Exact HWND capture and UIA snapshots exist, but semantic reference-bound actions are not at macOS parity. |
| Android | `source-reviewed` at integration depth | ADB is integrated; no local device conformance run. |
| Linux | Unsupported | No Linux desktop backend. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

The project combines native per-window screenshots, accessibility snapshots,
OCR/visual actions, browser CDP, and ADB. macOS semantic references are
generation scoped and actions use AX directly where possible. Its macOS
System Settings examples document real AX action quirks such as controls that
require selection state instead of AXPress.

Windows can capture an exact HWND and produce UIA snapshots, but current
reference actions are not equivalent; some paths fall back to foreground text
search or coordinates. This asymmetry is another reason to record depth by
platform and operation.

## North Star fit

The project is useful for exact-window capture, coordinate reconciliation,
OCR fallback, Mac AX details, and a single tool spanning desktop and ADB. It
does not currently offer the three-desktop semantic parity or session/result
architecture needed for the common spine.

## Current disposition

**Proposal:** Retain as a macOS/Windows capture and AX implementation
reference. Compare only the subsystems that fill a demonstrated gap.

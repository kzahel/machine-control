# Touchpoint

Upstream: [Touchpoint-Labs/touchpoint](https://github.com/Touchpoint-Labs/touchpoint)

Declared license: [MIT](https://github.com/Touchpoint-Labs/touchpoint/blob/main/LICENSE)
for the repository.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `source-reviewed` | UIA, HWND/window operations, SendInput, and CDP paths exist; no local live test. |
| macOS | `source-reviewed` | AX window/element operations and CGEvent input exist; no local live test. |
| Linux | `source-reviewed` | AT-SPI semantics and X11-oriented input exist; Wayland input is not a complete solution. |
| Browser | `source-reviewed` | CDP content is merged with native browser chrome under one facade. |

No exact review pin has yet been added to `machine-control-spike`; do that
before a decision relies on source details.

## Architecture and depth

Touchpoint is a relatively small Python library and MCP server with one API for
applications, windows, elements, search, waits, actions, screenshots, and
window management. Platform backends separate semantic accessibility from raw
input. Its macOS window identity prefers native AX window numbers or
identifiers and caches a fallback; Windows combines UIA with HWND operations.

The current screenshot implementation generally captures the framebuffer and
crops it to reported window or element bounds. That is useful addressing but
not necessarily occlusion-independent capture of the selected window's own
pixels. Linux raw input is primarily X11-based.

## North Star fit

Touchpoint is the clearest small alternative for understanding how a common
AX/UIA/AT-SPI/CDP facade could be organized. It has less session,
authorization, action-result, evidence, and real-GUI conformance machinery
than Cua, but may be easier to adapt or extract from.

## Current disposition

**Proposal:** Keep Touchpoint as the second common-desktop candidate and a
readable facade reference. Do not adopt it until live tests cover window
identity, crop fidelity, stale references, transient shell surfaces,
background behavior, and explicit fallback effects.

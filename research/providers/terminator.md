# Terminator

Upstream: [mediar-ai/terminator](https://github.com/mediar-ai/terminator)

Declared license: [MIT](https://github.com/mediar-ai/terminator/blob/main/LICENSE)
for the repository. The top-level license text carries inherited copyright
language; a distribution audit should confirm the intended scope and all
packaged dependencies.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| Windows | `source-reviewed` | UIA/Rust desktop automation, windows, actions, recording, browser integration, and public facades were inspected. No local live test. |
| macOS/Linux | Unsupported as native desktop backends | Product links or hosted use must not be mistaken for equivalent local providers. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

Terminator is a substantial Windows automation implementation with Rust and
SDK/MCP surfaces. It provides semantic locators and actions, application and
window management, screenshots, recording, browser integration, and workflow
features. Its architecture is relevant when comparing mature Windows-only UIA
providers with a cross-platform core.

## North Star fit

The project could be a strong Windows adapter or implementation reference, but
it does not reduce macOS/Linux adapter divergence and has not received the
source, live, integrity, lock, or shell investigation already completed for
Cua and WinApp.

## Current disposition

**Proposal:** Keep Terminator in the Windows second-round shortlist. Promote
it to live evaluation only if Cua and WinApp expose a material Windows gap or
its API offers a clearly superior subsystem worth adopting.

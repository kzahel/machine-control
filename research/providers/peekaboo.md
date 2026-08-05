# Peekaboo

Upstream: [openclaw/Peekaboo](https://github.com/openclaw/Peekaboo)

Declared license: [MIT](https://github.com/openclaw/Peekaboo/blob/main/LICENSE)
for the repository.

Last corpus review: 2026-08-05.

## Evidence

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| macOS | `source-reviewed` | Exact-window selection/capture, AX actions, background routing, system surfaces, validation, and the native fixture were inspected. No local corpus conformance run yet. |
| Other platforms | Unsupported | Peekaboo is intentionally macOS specific. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

Peekaboo is a macOS CLI, optional MCP server, and resident application/bridge.
It reconciles `CGWindow` and AX identities and selects windows by application,
PID, native window ID, title, or index. It filters helper and non-renderable
windows and supports window-specific capture through macOS window and
ScreenCaptureKit routes.

Semantic and window actions cover applications, windows, elements, menus,
menu-bar items, Dock items, dialogs, and Spaces. Process-targeted background
input can avoid activating the application; foreground delivery is explicit.
Target identity and requested geometry are re-read and validated rather than
assuming a successful call produced the requested state.

The native Swift Playground is the strongest macOS fixture found in the
survey. It includes click, text, keyboard, scroll, drag, window, menu,
menu-bar, Dock, dialog, Space, and capture scenarios. Application-owned OSLog
counters and canaries provide effect evidence independent of the action API.

Useful upstream references:

- [automation architecture](https://github.com/openclaw/Peekaboo/blob/main/docs/automation.md)
- [window screenshot selection](https://github.com/openclaw/Peekaboo/blob/main/docs/window-screenshot-smart-select.md)
- [testing tools](https://github.com/openclaw/Peekaboo/blob/main/docs/testing/tools.md)

## North Star fit

Peekaboo is the deepest macOS-specific reference for exact-window identity,
capture fidelity, transient system surfaces, background delivery, and native
fixture design. Its platform specificity is not a defect; it may supply the
best macOS adapter or upstream patterns under a common facade.

## Current disposition

**Proposal:** Use Peekaboo as the macOS depth benchmark and fixture reference.
Compare it with Cua on the same exact-window and system-surface cases when the
macOS slice begins.

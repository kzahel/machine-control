# Agent Device

Upstream: [callstack/agent-device](https://github.com/callstack/agent-device)

Declared license: [MIT](https://github.com/callstack/agent-device/blob/main/LICENSE)
for the repository.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| iOS | `adopted` | `ios-device-testbed` uses Agent Device as its semantic XCTest provider. |
| Android and device variants | `upstream-claimed` | Broad CLI support is documented; this corpus has not independently tested the generic Android backend. |
| macOS | `source-reviewed` | Desktop helper and public command paths were inspected; exact selected-window control is absent. |
| Linux/web | `upstream-claimed` | Not candidates to replace the stronger current desktop/device foundations without platform evidence. |
| Windows desktop | Unsupported | No native Windows desktop backend was found. |

Evidence links:

- [iOS device testbed](../../../ios-device-testbed/README.md)
- [upstream repository](https://github.com/callstack/agent-device)

## Architecture and depth

Agent Device provides an agent-oriented inspect-act-verify workflow, compact
semantic snapshots, element references and selectors, actions, sessions,
replay, evidence, device lifecycle, and recovery guidance. Its bundled
Expo/React Native fixture uses deterministic flows, unique test identifiers,
accessibility labels, alerts, permissions, gestures, application state, and
replayable `.ad` scripts.

The macOS helper exposes `frontmost-app`, `desktop`, and `menubar` semantic
surfaces. It combines `NSWorkspace`, `CGWindow`, and AX state and can include
the active application menu and SystemUIServer extras. The current public
surface does not bind semantic observation, capture, and action to one exact
selected native window; the screenshot path is display scoped.

## North Star fit

Agent Device is a strong device-family workflow and the currently adopted iOS
semantic route. Its compact output, evidence, replay, and fixture patterns are
useful common-contract inputs. Its process placement on a device host for stock
iOS is fully compatible with the North Star.

## Current disposition

**Decision:** Continue adopting Agent Device through the iOS testbed. Treat its
macOS work as implementation context, not evidence that it should become the
desktop spine.

**Open:** Determine whether its Android route should wrap or complement the
project's ADB/UIAutomator adapter and whether simulator and physical-device
identities share one device-family facade.

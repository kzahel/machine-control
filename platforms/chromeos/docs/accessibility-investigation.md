# AT-SPI2 / D-Bus Accessibility on ChromeOS

Investigation date: 2026-03-02
ChromeOS version: R144-16503.74.0 (board: nami-signed-mp-v12keys)
Chrome version: 144.0.7559.172

## Goal

Determine if we can get a full desktop accessibility tree (shelf, notification tray,
window list, browser chrome, and web content) via AT-SPI2 over D-Bus on a ChromeOS
device with root SSH access.

## TL;DR

**AT-SPI2 is completely absent from ChromeOS.** The libraries, binaries, D-Bus service
files, and even compiled-in support in the Chrome binary are all missing. ChromeOS uses
its own internal accessibility system (`accessibilityPrivate` Chrome extension API)
rather than the standard Linux AT-SPI2 stack.

CDP `Accessibility.getFullAXTree` works for individual web page content but does not
cover system UI (shelf, system tray, window titles, dialogs).

## Findings

### D-Bus Tools Available

| Tool | Path | Available |
|------|------|-----------|
| dbus-send | /usr/bin/dbus-send | Yes |
| gdbus | /usr/bin/gdbus | Yes |
| dbus-monitor | /usr/bin/dbus-monitor | Yes |
| busctl | — | No |

**Note:** The default root SSH shell has `PATH=/opt/bin` only. Prepend the full path:
```bash
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/bin
```

### AT-SPI2: Not Present

- No AT-SPI2 binaries (`at-spi2-registryd`, `at-spi-bus-launcher`)
- No AT-SPI2 libraries (`libatspi`, `libatk-bridge`, `libatk`, `libgail`)
- No AT-SPI2 processes running
- No `org.a11y.Bus` on D-Bus: `Error: The name org.a11y.Bus was not provided by any .service files`
- No D-Bus service files for AT-SPI2
- No session bus for chronos user — `/run/user/1000/` does not exist
- Chrome binary contains zero references to "atspi" — compiled without AT-SPI2/ATK support
- `strings /opt/google/chrome/chrome | grep -c atspi` → 0

ChromeOS Chrome runs as a Wayland compositor (Ash/Exo), not a GTK application.
The Linux accessibility stack (ATK → AT-SPI2 → D-Bus) was never included.

### D-Bus System Bus

The system bus has ~100+ `org.chromium.*` services but none expose accessibility trees.
Introspecting them returns empty `<node/>` documents. Notable services:

- `org.chromium.SessionManager`
- `org.chromium.ChromeFeaturesService`
- `org.chromium.ScreenLockService`
- `org.chromium.DisplayService`

None have accessibility-related methods.

### Chrome Internal Accessibility

Chrome's `chrome://accessibility` page reveals:

- All accessibility modes are **disabled** by default (Native, Web, Screen reader, etc.)
- "Active assistive technology: Uninitialized"
- Chrome has built-in accessibility tree support but only activates it on demand
- Can be forced on with `--force-renderer-accessibility` flag

Chrome's runtime environment:
```
XDG_RUNTIME_DIR=/run/chrome    # not /run/user/1000
DBUS_FATAL_WARNINGS=0
```
The `/run/chrome/` directory contains only a Wayland socket and ARC subdirectory.

### ChromeVox

ChromeVox (built-in screen reader) is installed but not enabled:
```
/opt/google/chrome/resources/chromeos/accessibility/chromevox/
```

It uses the `accessibilityPrivate` Chrome extension API (not AT-SPI2). Its manifest
requests permissions including `accessibilityPrivate`, `brailleDisplayPrivate`,
`chromeosInfoPrivate`, and `commandLinePrivate`.

Other accessibility extensions installed:
- `accessibility_common` — shared utilities
- `select_to_speak` — read selected text aloud
- `switch_access` — switch-based input
- `enhanced_network_tts` — cloud TTS
- `braille_ime` — braille input

### CDP Accessibility Domain

Per-page CDP `Accessibility.getFullAXTree` works — confirmed with 56 nodes from a page
target. However:

- Does **not** work on browser-level target (`Accessibility.enable wasn't found`)
- Only covers web content within a single tab
- Does **not** include: shelf, taskbar, system tray, window list, Chrome browser
  chrome (tabs, omnibox, menus), native dialogs

### ChromeOS Preferences

Accessibility settings in `/home/chronos/user/Preferences`:
```json
{
  "accessibility": {
    "captions": {
      "headless_caption_enabled": false,
      "live_caption_language": "en-US"
    }
  }
}
```
No screen reader, magnifier, or other accessibility features enabled.

## Approaches for Full Desktop Accessibility Tree

| Approach | Effort | Coverage | Notes |
|----------|--------|----------|-------|
| `--force-renderer-accessibility` flag | Easy | All web content across tabs | Add to `/etc/chrome_dev.conf`, restart Chrome. Still no system UI. |
| Enable ChromeVox via Settings | Easy | Full desktop including system UI | Screen reader that speaks aloud — may have silent/API-only mode |
| Custom Chrome extension using `accessibilityPrivate` API | Medium | Full desktop tree | Same data ChromeVox sees; could expose over WebSocket/HTTP |
| Tast testing framework | Hard | Full Ash UI tree | Requires CrOS SDK; has `chrome.Accessibility` test helpers |
| Custom CrOS build with AT-SPI2 | Very hard | Standard Linux AT-SPI2 | Would need to add packages and recompile Chrome with ATK |

### Recommended: Custom Chrome Extension

The most practical approach for programmatic desktop tree access is a Chrome extension
using the `accessibilityPrivate` API. This would:

1. Access the same full Ash/desktop accessibility tree that ChromeVox uses
2. Include system UI elements (shelf, notifications, window list, dialogs)
3. Expose the tree over a local HTTP/WebSocket endpoint for external tools
4. Run silently without screen reader audio
5. Work on stock ChromeOS without custom builds

The extension would need to be loaded as an unpacked extension in developer mode, using
the `accessibilityPrivate` permission (which is restricted to allowlisted extension IDs
on non-dev-mode devices, but available in developer mode).

## Commands Used

```bash
# Check D-Bus tools
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/opt/bin
which dbus-send busctl dbus-monitor gdbus

# Search for AT-SPI2 files
find / -maxdepth 6 \( -name "*atspi*" -o -name "*at-spi*" -o -name "*a11y*" \) \
  -not -path "/proc/*" -not -path "/sys/*" 2>/dev/null

# Check AT-SPI2 on D-Bus
dbus-send --system --print-reply --dest=org.a11y.Bus /org/a11y/bus org.a11y.Bus.GetAddress

# List system bus names
dbus-send --system --print-reply --dest=org.freedesktop.DBus \
  /org/freedesktop/DBus org.freedesktop.DBus.ListNames

# Check Chrome process flags
cat /proc/$(pgrep -f "/opt/google/chrome/chrome" | head -1)/cmdline | tr '\0' '\n'

# Check Chrome environment
cat /proc/$(pgrep -f "/opt/google/chrome/chrome" | head -1)/environ | tr '\0' '\n'

# Check accessibility preferences
python3 -c "import json; p=json.load(open('/home/chronos/user/Preferences')); \
  print(json.dumps(p.get('accessibility',{}), indent=2))"
```

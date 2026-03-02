# Desktop Automation via chrome.automation

Investigation date: 2026-03-02
ChromeOS version: R144-16503.74.0, Chrome 144.0.7559.172

## Goal

Access the full ChromeOS desktop accessibility tree (shelf, system tray, window list,
dialogs — not just web content) programmatically via `chrome.automation.getDesktop()`.

## TL;DR

**Piggyback on ChromeOS built-in accessibility extensions via CDP.** Enable any
accessibility feature (Large Cursor is least intrusive), then `Runtime.evaluate` against
the `accessibility_common` service worker which has `chrome.automation` desktop access.

## What We Tried

### 1. Custom Chrome Extension (Failed)

Built an MV3 extension (`extension/`) with `"automation": {"desktop": true}` in its
manifest, deployed as an unpacked extension via `chrome://extensions`.

**Result:** `chrome.automation` is `undefined`. The API is gated by an allowlist in
Chromium's `extensions/common/api/_manifest_features.json`:

```json
"automation": {
  "channel": "stable",
  "extension_types": ["extension", "legacy_packaged_app", "platform_app"],
  "allowlist": [
    "2FCBCE08B34CCA17728A85F1EFBD9A34DD2558B2E",
    "05D1DBD6E8B9C4690FFA7D50E6F60C5290DC662A",
    ...
  ]
}
```

Only allowlisted extension IDs (hashed) can use the `automation` manifest key. Our
extension isn't on the list, and there's no way to add it at runtime.

### 2. --whitelisted-extension-id Flag (Failed)

Added `--whitelisted-extension-id=<our-id>` to `/etc/chrome_dev.conf`.

**Result:** `session_manager` filters out this flag. Only `--remote-debugging-port`
passes through to Chrome. The flag works in Chromium test harnesses but not on production
ChromeOS.

### 3. MV2 with automation key (Failed)

Tried MV2 manifest with `"automation": {"desktop": true}`.

**Result:** ChromeOS R144 rejects MV2 extensions entirely.

### 4. Chromium Test Key (Failed)

Used the test key from `chromium/src/chrome/test/data/extensions/api_test/automation/tests/service_worker/manifest.json`.

**Result:** Extension loads but `chrome.automation` still undefined. The test key only
works with `--whitelisted-extension-id` in the test harness environment.

### 5. AT-SPI2 / D-Bus (Failed)

See [accessibility-investigation.md](accessibility-investigation.md). AT-SPI2 is
completely absent from ChromeOS.

## What Works: Built-in Accessibility Extensions

ChromeOS ships component extensions at `/opt/google/chrome/resources/chromeos/accessibility/`
that are on the allowlist and have `"automation": {"desktop": true}`:

| Extension | ID | Loads When |
|-----------|---|------------|
| accessibility_common | `egfdjlfmgnehecnclamagfafdccgfndp` | Large Cursor, Dictation, Autoclick, Magnifier, FaceGaze |
| select_to_speak | `klbcgckkldhdhonijdbnhhaiedfkllef` | Select-to-speak |
| chromevox | `mndnfokpggljbaajbnioimlmbfngpief` | ChromeVox screen reader |

These are MV3 extensions with service workers. When an accessibility feature is enabled,
Chrome loads the corresponding extension and its service worker gets `chrome.automation`
access.

### How It Works

1. **Enable an accessibility feature** — Large Cursor is the least intrusive
   (Settings > Accessibility > Cursor and touchpad > Large mouse cursor)

2. **Find the service worker via CDP** — The service worker appears in
   `Target.getTargets` with type `service_worker` and the extension's URL

3. **Evaluate JS in the service worker** — Use CDP `Runtime.evaluate` to call
   `chrome.automation.getDesktop()` which returns the full desktop tree

### Important Details

- **Service worker context only** — `chrome.automation` is available in the service
  worker, NOT in offscreen pages (which also appear as CDP targets for the same extension)
- **Service workers go idle** — MV3 service workers can go dormant and disappear from
  `/json`. Use browser-level `Target.getTargets` to find them, then
  `Target.attachToTarget` to wake them
- **Component extensions are invisible** — They don't appear in `chrome://extensions` or
  `chrome.developerPrivate.getExtensionsInfo()`. Only visible via CDP `Target.getTargets`

### Example: Desktop Tree Output

```
[desktop] (horizontal)
  [window] "Built-in display"
    [window] "Settings" @500,0 1100x852
    [window] "Terminal" @0,0 1600x900
    [toolbar] "Shelf" @596,898 1075x3
    [dialog] "Select-to-speak menu" @656,351 384x82
```

The tree includes all system UI: windows, shelf, status tray, dialogs, buttons, tabs,
text fields, etc.

## Implementation

In `cdp.py`, `_find_automation_target()` searches for the accessibility_common or
select_to_speak service worker. The `desktop_tree()`, `desktop_find()`, and
`desktop_click()` functions evaluate JavaScript in this context.

No custom extension deployment is needed — we rely entirely on ChromeOS's built-in
extensions.

## Prerequisites

- At least one accessibility feature enabled in ChromeOS Settings
- CDP remote debugging enabled (`--remote-debugging-port=9222` in `/etc/chrome_dev.conf`)
- SSH root access to the device

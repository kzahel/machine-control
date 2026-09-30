# Machine Control Chrome extension

Topic: [`browser-control`](../../topics/browser-control.md)

This MV3 extension is the browser provider for a Machine Control resident on
the same computer. It connects to the resident only through Chrome native
messaging (`org.machine_control.browser`), and it acts only on requests the
resident forwards. The resident checks the person's `browser` grant before
forwarding; the extension badge shows `ON` while that grant is active and
detaches its debugger sessions when the grant ends.

Operations use `chrome.debugger` (CDP) on individual tabs:

| Resident operation | Effect |
| --- | --- |
| `browser.tabs` | List tabs |
| `browser.navigate` | Load an `http`, `https`, or `about:blank` URL in a tab or a new tab |
| `browser.snapshot` | Compact accessibility tree with generation-bound references |
| `browser.click` | Trusted mouse click at an element's center |
| `browser.type` | Focus an element and insert text |
| `browser.key` | Press Enter, Tab, Escape, Backspace, or an arrow key |
| `browser.capture` | Viewport PNG stored as a resident artifact |
| `browser.release` | Detach all debugger sessions |

References look like `TAB:GENERATION:NODE`. Taking a new snapshot or loading a
new page makes older references stale.

## Development install

The manifest carries a fixed public `key`, so the unpacked extension always
has the ID `ncbfifkjllmnkkjmomjohinigfgdocjc`. A Chrome Web Store release
would have a different ID and needs its own native-messaging registration.

1. Install Machine Control.app (`platforms/macos/resident/scripts/install-user.sh`).
2. Register the native host for the browser profile:
   `platforms/macos/resident/scripts/install-browser.sh`. Chrome reads
   user-level hosts from its user data directory, so a separate profile or
   Chrome for Testing needs `--browser-dir DIR`.
3. In `chrome://extensions`, enable Developer mode and choose
   **Load unpacked** with this directory.

Branded Chrome ignores `--load-extension`; Chrome for Testing accepts it,
which is how automated tests load the extension in disposable VMs.

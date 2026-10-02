# Machine Control Chrome extension

Topic: [`browser-control`](../../topics/browser-control.md)

This MV3 extension is the browser provider for a Machine Control resident on
the same computer. It connects to the resident only through Chrome native
messaging (`org.machine_control.browser`), and it acts only on requests the
resident forwards. The resident checks the person's `browser` grant before
forwarding; the extension badge shows `ON` while that grant is active (`DEV`
for the broader `devtools` grant) and
detaches its debugger sessions when the grant ends.

Operations use `chrome.debugger` (CDP) on individual tabs:

| Resident operation | Effect |
| --- | --- |
| `browser.tabs` | List tabs |
| `browser.wait` | Wait until a tab finishes loading and is not discarded |
| `browser.navigate` | Load an `http`, `https`, or `about:blank` URL in a tab or a new tab |
| `browser.snapshot` | Compact accessibility tree with generation-bound references |
| `browser.click` | Trusted mouse click at an element's center |
| `browser.type` | Focus an element and insert text |
| `browser.key` | Press Enter, Tab, Escape, Backspace, or an arrow key |
| `browser.capture` | Viewport PNG stored as a resident artifact |
| `browser.upload` | Attach local files to a file input, or to the chooser an upload button opens, without the OS file dialog |
| `browser.cdp` | Any DevTools protocol method with its parameters (`devtools` grant) |
| `browser.eval` | Evaluate JavaScript in a tab and return the value (`devtools` grant) |
| `browser.endpoint` | Report the local DevTools WebSocket endpoint template (`devtools` grant) |
| `browser.release` | Detach all debugger sessions |

Controlled tabs show an owned blue pointer over their site favicon. Newly
created agent tabs join a blue **Machine Control** group in their own window;
existing and pinned tabs keep their grouping. Listing tabs alone adds no marker.
`browser.tabs` reports `groupId` and `controlIndicator` (`none`, `active`, or
`unavailable`), so restricted-page omissions remain visible to callers.

Release, ended/replaced grants, native disconnect, and worker recovery restore
site icons and remove unchanged owned grouping. Site icon updates and user
renames, recolors, moves, shared groups, and added tabs are preserved. The icon
expires independently after ten seconds without a worker heartbeat. Indicators
use the authorized per-tab debugger in an isolated world; no page content
scripts or broad host permissions are added. They are visible status, not an
authorization boundary or a marker of completed work.

Run lifecycle checks with `node --test tests/browser/*.test.mjs`. The headed
[`indicators-live.py`](../../tests/browser/indicators-live.py) runner exercises
real Chrome for Testing and a native resident inside a claimed Mac appliance;
its caller owns target selection, claims, grant approval, and power cleanup.

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

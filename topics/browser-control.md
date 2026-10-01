# Browser Control

Topic: `browser-control`

Status: source-native developer preview accepted with Chrome for Testing in a
Tart guest and a per-tab CDP bridge exercised against real Chrome on the Mac.
Windows source-native and exact signed x64 Tauri browser tasks pass, including
local/outside effects and artifacts. Browser-open updater repair acceptance
remains open. The [provider dossier](../research/providers/chrome-extension.md)
owns platform evidence and omissions.
[Tactical 050](../docs/tactical/050-macos-host-control-mvp.md) owns the first
slice.

## Scope

Semantic control of the user's own running Chromium-family browser, with
existing profiles and sign-ins, through the same target selection, grants,
and result vocabulary as desktop control. This applies to physical hosts
([`host-control`](host-control.md)) and to browsers inside VM guests.

## Current

**Current:** [`platforms/chromeos/cdp.py`](../platforms/chromeos/cdp.py) is a
standard-library CDP client. It lists targets, reads a page's full
accessibility tree, finds nodes, and clicks. It depends on ChromeOS's
developer configuration enabling a fixed remote-debugging port. Its desktop
functions borrow ChromeOS accessibility extensions and do not apply
elsewhere; the page-level logic is reusable.

**Current (2026-09-30):** The [Machine Control extension](../providers/chrome-extension)
connects through native messaging to the resident on macOS. In a Tart guest,
Chrome for Testing loaded it unpacked; after a `browser` grant was approved,
typing and clicking produced the fixture page's own text change, a link
navigated, `file:` URLs were refused, and capture produced an artifact. A
same-user process claiming the provider role was refused by the resident's
code-identity check. Chrome for Testing showed no debugger info bar, so its
removal on revocation was not visually confirmed.

**Current (reported by the controller user):** Browser extensions coupled to a
particular assistant product did not work from agents running under
YepAnywhere.

## Decisions

**Decision:** The first route is a Machine Control Chrome extension, loaded
unpacked during development, with a possible Chrome Web Store release later.
Rejected or deferred alternatives:

- Remote-debugging ports: current Chrome refuses them on the default profile,
  and a separate profile lacks the user's sign-ins.
- Chrome's user-consented attach to a running browser: a candidate fallback,
  not yet evaluated.
- Desktop accessibility and input alone: always available, but coarse.

**Decision:** The extension reaches the resident only through Chrome native
messaging, not a localhost port. A small native host shipped in the
application bundle is registered for the extension's fixed ID; Chrome checks
the origin and starts the host, which relays to the resident socket. The
resident accepts the browser-provider role only from a peer whose code
identity matches that bundled host.

**Decision:** The extension uses `chrome.debugger` to attach CDP to individual
tabs, plus `chrome.tabs` for tab lifecycle. Chrome's own “being debugged” bar
is an intended visible indicator. A fixed manifest `key` keeps the unpacked
extension ID stable across checkouts.

**Decision:** Browser operations require the `browser` grant scope in the
resident's grant broker. The extension badge mirrors grant state but does not
enforce it.

**Decision:** For a live, efficient session an agent connects a raw CDP
WebSocket. Chrome refuses `--remote-debugging-port` on the signed-in profile,
so the Machine Control app hosts a loopback WebSocket server and relays frames
through the extension per tab. `browser.endpoint` (and a `devtools` grant
result) returns `ws://127.0.0.1:PORT/devtools/page/<tabId>?token=…`. The
server runs for the resident's lifetime; a per-grant token, cleared when the
grant ends, gates every connection, and the server also rejects any request
carrying an `Origin` header so a web page cannot reach it. Events stream back
over the socket. Tab-level clients and raw CDP libraries work directly;
browser-level attachment for Playwright and Puppeteer would need target
emulation and is not built. A separate agent Chrome profile started with
`--remote-debugging-port` remains the alternative for full native access
without the extension in the path.

**Decision:** Single-shot raw DevTools access is also available, because it is
the most capable and efficient browser route. `browser.cdp` passes any method and
parameters through `chrome.debugger`, and `browser.eval` evaluates JavaScript
and returns the value. Both require a separate `devtools` scope, because that
access can run scripts and read data on every signed-in site, and data read
that way can outlive the grant. The prompt says so, the badge shows `DEV`,
and recent activity records each method. Chrome still withholds a few domains
from extensions. For a live session with streamed events, an agent uses the
WebSocket endpoint above rather than these single-shot calls.

**Current (2026-09-30):** Verified on the host and in the guest that a raw CDP
WebSocket reads and drives the real signed-in Chrome, with events streaming.
`Runtime.evaluate` without an explicit context lands in the page's main world
and reads `document.title` correctly even alongside an isolated-world
extension. An empty read on a heavy single-page app traced to the tab being
discarded (reloaded on attach) and setting its title after load, not to a
bridge fault; `browser.tabs` now reports `discarded` so a caller can wait.

These observations precede the shared signed Tauri package. Its packaging
acceptance verified native-messaging startup/framing, not a full extension
task. The [desktop matrix](../docs/desktop-acceptance.md) separates those
package and environment boundaries.

## Open

- **Open:** Browser-level CDP attachment (target list plus per-tab attach) so
  Playwright and Puppeteer `connectOverCDP` work, not only tab-level clients.
- **Current:** Windows per-user registration, scoped browser operations, and
  single-shot raw CDP/evaluation are implemented. Signed installed acceptance
  is in [054](../docs/tactical/054-windows-browser-and-arm64.md). Windows upload
  and raw CDP WebSockets remain unavailable and are reported as omissions.
- **Open:** Linux registration and other Chromium browsers.
- **Open:** Web Store publication, which changes the extension ID and install
  flow.

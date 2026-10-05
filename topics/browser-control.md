# Browser Control

Topic: `browser-control`

Status: source-native developer preview accepted with Chrome for Testing in a
Tart guest and a per-tab CDP bridge exercised against real Chrome on the Mac.
Windows source-native and exact signed x64 Tauri browser tasks pass, including
local/outside effects and artifacts recorded on 0.4.7. Public 0.4.8 browser
tasks and production 0.4.7 to 0.4.8 replacement pass with Chrome open, reconnect
and revoked authority. Connected-browser uninstall also passes on 0.4.8. The
[provider dossier](../research/providers/chrome-extension.md)
owns platform evidence and omissions.
[Tactical 050](../docs/tactical/050-macos-host-control-mvp.md) owns the first
slice.

## Scope

Semantic control of the user's own running Chromium-family browser, with
existing profiles and sign-ins, through the same target selection, grants,
and result vocabulary as desktop control. This applies to physical hosts
([`host-control`](host-control.md)) and to browsers inside VM guests.

## Current

**Current (2026-10-02):** A source-independent YA Codex provider in the Mac
appliance consumes the signed installed Python CLI for a browser fixture:
tabs/snapshot, one semantic click, tab capture, artifact fetch and built-in
agent image consumption. An independent HTTP counter establishes the effect.
Chrome for Testing 145 passes the 23-check headed harness, including the
existing indicator/worker checks. This uses standing appliance authority;
workstation approval and other installed platforms remain separate. See
[Tactical 062](../docs/tactical/062-installed-agent-cli.md).

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

**Current (2026-10-02):** Controlled tabs carry an owned blue pointer favicon;
new agent tabs join a blue **Machine Control** group. Existing user groups and
pinned tabs stay in place. Release, grant replacement/revocation, disconnect,
and fresh-worker recovery restore owned state while preserving site-icon and
user-group edits. A page heartbeat expiry also clears an abandoned marker.
`browser.tabs` reports per-tab indicator availability separately from the global
grant. [Tactical 058](../docs/tactical/058-browser-tab-indicators.md) owns source and exact signed ARM64 VM
acceptance and desktop 0.4.10 publication. The
[Codex extension review](../research/providers/codex-browser-extension.md)
provided interaction inspiration; implementation and artwork are owned.

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
through the extension per tab. `browser.endpoint` returns the
`devtoolsEndpoint` template `ws://127.0.0.1:PORT/devtools/page/<tabId>?token=…`.
The server runs for the resident's lifetime and rejects every request carrying
an `Origin` header so a web page cannot reach it. The existing Mac bridge uses
a per-grant token and refuses reserved ownership. The Windows desktop bridge
binds its token to a retained live DevTools owner, grant and provider generation;
Pause, Stop or loss of that authority closes streams and invalidates the URL.
Single-shot ownership cannot produce a usable endpoint. Events stream back
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
and Windows audit history records payload-free operation/outcome metadata.
Chrome still withholds a few domains from extensions. For a live session with
streamed events, an agent uses the
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

- **Current, unreleased Windows x64 candidate:** `browser.upload` uses the
  shared extension's direct CDP input/chooser interception with native local-file
  validation, browser scope and live ownership. All 23 focused VM checks pass,
  including independent received bytes and Pause/Stop fences.
  [Tactical 098](../docs/tactical/098-windows-browser-upload.md) owns evidence
  and remaining signed/ARM64/physical qualification.
- **Open:** Browser-level CDP attachment (target list plus per-tab attach) so
  Playwright and Puppeteer `connectOverCDP` work, not only tab-level clients.
- **Current:** Windows per-user registration, scoped browser operations, and
  single-shot raw CDP/evaluation are implemented. Signed installed acceptance
  is in [054](../docs/tactical/054-windows-browser-and-arm64.md). The unreleased
  Windows candidate also provides retained-owner per-tab CDP WebSockets,
  streamed events and bounded, audited commands. [Tactical 099](../docs/tactical/099-windows-streaming-cdp.md)
  owns focused x64 acceptance and [the streaming guide](../desktop/WINDOWS-STREAMING-CDP.md)
  owns usage and target-loopback forwarding limits. Signed streaming packages,
  ARM64 live, physical and other-browser qualification remain separate.
- **Open:** Linux registration and other Chromium browsers.
- **Open:** Web Store publication, which changes the extension ID and install
  flow.

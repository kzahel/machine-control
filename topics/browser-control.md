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

**Current (2026-10-25), unreleased extension 0.8.1:** ordinary requests use
bounded per-tab scheduling and request-local authority. Discovery, dialog
handling, release and grant changes progress independently of stalled page
work. Deadlines and cancellation fence continuations; queued work refuses,
while dispatched timeouts report unknown delivery/effect. Confirmed debugger
detach frees abandoned command capacity even if Chrome never settles a callback.
Unconfirmed detaches block that route and can be retried by release. Optional
indicator cleanup has its own bounds. Typed `browser.dialog` requires a current
dialog ID for handling; `not_observed` is not proof that no dialog exists.
[Tactical 138](../docs/tactical/138-remote-arming-recovery.md) owns the repair
and signed Mac VM campaign plus the focused Windows/Linux source-native
release smoke; the provider dossier owns evidence limits. Windows typed dialog
handling now maps to the browser scope at the retained control-session gate.
The final signed development assembly passes that composed campaign with
native until-stopped approval, independent effects, faults and Stop. This is
the bundled unpacked provider in one VM; store and mixed-version rollout remain
separate.

**Current (2026-10-24), bundled in desktop 0.6.9:** ordinary worker requests bind
authority at message arrival and recheck it around awaited CDP work. Opaque
references carry an authority epoch so reconnect, worker restart and new grants
cannot revive old references through reused snapshot counters. Contract tests
prove held clicks and queued text cannot adopt fresh approval; packaged Mac
fault tests prove reconnect/restart refusal and fresh independent effects.
[Tactical 136](../docs/tactical/136-desktop-crash-hardening.md) owns execution;
the provider dossier owns platform and route limits. [Tactical 137](../docs/tactical/137-desktop-0.6.9-release.md)
adds exact published Mac ARM64 acceptance with the bundled unpacked provider;
Chrome Web Store delivery/connection has no new qualification here.

**Current (2026-10-14):** Extension 0.8.0 adds icons and a read-only side
panel (connection, access, controlled tabs, live payload-free activity) and was
submitted to the Chrome Web Store as an unlisted item with ID
`epejchbeajneooefnklikkfhbaeadkpc`. Source native hosts on all three desktop
platforms accept that ID beside the unpacked development ID. Public desktop
0.6.4 now packages those hosts and the side panel on all three platforms;
[Tactical 121](../docs/tactical/121-desktop-0.6.4-release.md) records package
authentication. [Tactical 117](../docs/tactical/117-chrome-web-store-extension.md)
owns store review, installed store-copy acceptance and the remaining sequence.

**Current (2026-10-11):** The unreleased signed ARM64 Mac candidate passes
21 Chrome for Testing 154 checks under native workstation approval with no
Settings WebView. Packaged CLI PNG retrieval, independent page/icon effects,
marker lifecycle and native-host reconnect after worker restart pass.
[Tactical 108](../docs/tactical/108-macos-runtime-presentation.md) owns the
bounded campaign. This adds ordinary workstation approval evidence; it does
not qualify browser-root streaming, a YA model probe, physical/Intel execution
or a public release.

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

**Decision:** The route is a Machine Control Chrome extension, loaded unpacked
during development and in Chrome for Testing, and distributed to people
through the Chrome Web Store. Native hosts accept both IDs.
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
over the socket. `browserEndpoint` adds a browser-root connection alongside
the tab template. Shared extension logic exposes supported default-profile
page targets, discovery, tab lifecycle, facade tab wrappers and flattened
native child sessions. Windows and macOS native bridges preserve session
routing; macOS browser-root changes build in the signed candidate but await
focused live qualification.
Playwright requires `noDefaults: true` because browser-wide download policy
is unavailable. Isolated contexts, browser shutdown and restricted operations
refuse explicitly. A separate agent Chrome profile started with
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

- **Current, shipped in desktop 0.6.8 (2026-10-17):** Settings includes a
  default-off **Allow approved browser access while locked** preference,
  independent of covered desktop unlock. Approve access while unlocked, then
  keep approved `browser` and separately approved `devtools` operations across
  a lock of that exact console. Mixed grants retain identity and expiry;
  desktop scopes are unavailable until unlock unless covered desktop control
  separately authorizes them. New or expanded approval still requires an
  unlocked console. Pause, Stop, expiry, disabling, session replacement and
  unknown session state remain effective. Browser-only owner connections do
  not activate the unlock helper. Grant status reports effective scopes and
  the lock restriction; status reports the preference. Only the local operator
  may change it. [Tactical 130](../docs/tactical/130-macos-browser-while-locked.md)
  owns Mac validation; [Tactical 131](../docs/tactical/131-windows-linux-browser-while-locked.md)
  owns Windows and GNOME Wayland Linux. Windows binds authority to the active
  console logon; Linux binds it to the active logind graphical session and
  GNOME screensaver owner. Unknown or replaced identities revoke access.
  Signed installed Settings acceptance, physical hardware and other Linux
  desktops remain separate qualification.

- **Current, unreleased Windows x64 candidate:** `browser.upload` uses the
  shared extension's direct CDP input/chooser interception with native local-file
  validation, browser scope and live ownership. All 23 focused VM checks pass,
  including independent received bytes and Pause/Stop fences.
  [Tactical 098](../docs/tactical/098-windows-browser-upload.md) owns evidence
  and remaining signed/ARM64/physical qualification.
- **Current, unreleased Windows candidate:** Browser-level attachment adds
  default-profile target discovery and flattened sessions for real Playwright
  and Puppeteer clients. [Tactical 100](../docs/tactical/100-browser-level-cdp.md)
  owns qualification and the supported subset. Shared extension behavior is
  reusable; macOS browser-root live qualification, Linux registration, isolated
  contexts and browser-wide operations remain separate gaps.
- **Current:** Windows per-user registration, scoped browser operations, and
  single-shot raw CDP/evaluation are implemented. Signed installed acceptance
  is in [054](../docs/tactical/054-windows-browser-and-arm64.md). The unreleased
  Windows candidate also provides retained-owner per-tab CDP WebSockets,
  streamed events and bounded, audited commands. [Tactical 099](../docs/tactical/099-windows-streaming-cdp.md)
  owns focused x64 acceptance and [the streaming guide](../desktop/WINDOWS-STREAMING-CDP.md)
  owns usage and target-loopback forwarding limits. Signed streaming packages,
  ARM64 live, physical and other-browser qualification remain separate.
- **Current, repaired in unreleased source:** the shipped serial-queue defect
  can block all requests behind one page dialog and misreport queued timeouts.
  The bounded replacement above separates recovery and cancels expired work.
  [Tactical 138](../docs/tactical/138-remote-arming-recovery.md) owns qualification;
  [the gap record](../gaps/2026-10-25-locked-use-self-revocation.md) explains the incident.
- **Open:** Linux installed store-copy qualification and other Chromium browsers.
- **Open:** Store review outcome and installed store-copy acceptance,
  a revoke-only Stop from the extension, and installer/policy installation
  ([117](../docs/tactical/117-chrome-web-store-extension.md)).

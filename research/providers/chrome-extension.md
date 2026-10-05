# Machine Control Chrome extension

## Identity and license

**Current:** The owned provider lives in
[`providers/chrome-extension`](../../providers/chrome-extension). Its declared
top-level license is the repository's [MIT license](../../LICENSE). The
Windows installer bundles the extension and native host, not Chrome. Browser
binaries and their dependencies retain their distributor's separate terms.

The upstream facilities are documented by Chrome: [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging),
[`chrome.debugger`](https://developer.chrome.com/docs/extensions/reference/api/debugger),
and [`chrome.tabs`](https://developer.chrome.com/docs/extensions/reference/api/tabs).
Native messaging uses length-prefixed JSON and a fixed allowed extension
origin. Windows registers a per-user host manifest in the registry; macOS uses
the browser's native-host manifest directory.

## Architecture and reach

**Current:** Chrome launches the bundled native host. The host relays to a
target-resident provider channel, separate from agent calls and operator
approval. The resident authenticates the provider process and owns browser
and DevTools authorization, reference generations, artifacts, and result
envelopes. The extension mirrors grant state and uses per-tab CDP plus native
tab lifecycle APIs. It is not the approval authority.

| Platform and route | Evidence | Boundary |
| --- | --- | --- |
| macOS source-native extension/native messaging | `conformance-tested` | Fixture effects, navigation, capture and provider refusal in a Tart guest; predates signed Tauri acceptance |
| macOS per-tab raw CDP WebSocket | `live-tested` | Reads/actions/events on physical and guest Chrome; browser-root native changes are source-only pending build/live qualification |
| macOS signed Tauri, installed Python CLI and YA local Codex | `conformance-tested` | Chrome for Testing 145 in a claimed appliance: independent HTTP counter effect, tab PNG consumed by the built-in agent image tool, plus 21 existing indicator/worker checks; standing policy, not workstation approval |
| Windows source-native extension/native messaging | `conformance-tested` | Dedicated x64 VM, browser/devtools enforcement, independent fixture effects and PNG/hash checks; exact installed evidence below |
| Windows signed Tauri extension/native messaging | `conformance-tested` | Public 0.4.8 x64 VM package: setup/approval, independent effects/capture, restart, production browser-open replacement and ordinary uninstall; local/outside parity and lock revocation recorded on 0.4.7 |
| Windows staged x64 file upload | `conformance-tested` | Unreleased real desktop UI, browser-only live SDK owner and CLI request parser; Chrome for Testing 154: direct/multiple inputs, intercepted chooser, independent HTTP byte/hash effects and 23 scope/path/reference/Pause/Stop checks |
| Windows staged x64 per-tab CDP WebSocket | `conformance-tested` | Unreleased real desktop UI and retained DevTools owner, fresh Chrome for Testing 154: commands/events, unresolved-promise concurrency, independent HTTP effects and 28 scope/token/Origin/owner/provider/Pause/Stop checks; signed/ARM64/physical acceptance separate |
| Windows staged x64 browser-level CDP | `conformance-tested` | Shared target facade and native session routing; Chrome for Testing 154, Playwright 1.63 and Puppeteer 25.12: independent clicks, captures, popup/iframe/worker, refusals and 51 real-UI/authority/provider checks; signed/ARM64/physical acceptance separate |
| Linux and other Chromium browsers | `upstream-claimed` facilities only | Owned registration and product acceptance absent |

[Tactical 050](../../docs/tactical/050-macos-host-control-mvp.md) and
[Tactical 054](../../docs/tactical/054-windows-browser-and-arm64.md) and
[055](../../docs/tactical/055-unified-desktop-publication.md) own execution.
The [desktop matrix](../../docs/desktop-acceptance.md) separates source-native
and exact installed product evidence.

## Fidelity, consequences, and gaps

**Current:** Snapshots expose tab accessibility nodes. References bind grant,
provider, and extension snapshot generations. Clicking and typing may activate
the browser tab; the OS cursor is expected to remain unchanged. Captures are
tab PNGs, not whole-desktop captures. CDP acknowledgement establishes delivery,
not independent application effect; the fixture's own marker supplies that
oracle.

**Current:** Ordinary browser operations and unrestricted script/CDP access
have separate scopes. Stop, expiry, session loss, and provider replacement
revoke or invalidate authority. Same-user shell access is not contained by this
boundary. Chrome may refuse privileged pages or CDP domains, and debugger
attachment can display Chrome's own indicator.

**Current:** Windows upload uses the shared `DOM.setFileInputFiles` and
`Page.fileChooserOpened` interception routes. The resident validates 1–20
readable local-drive regular files before forwarding any, refusing network/
device/stream paths, reparse links and hidden/private storage. This is browser
authority; no elevated service or desktop input is required. Chrome reopens
paths, so validation does not contain concurrent same-user replacement.
[Tactical 098](../../docs/tactical/098-windows-browser-upload.md) owns focused
x64 candidate evidence; signed/ARM64/physical qualification remains separate.

**Current, unreleased Windows candidate:** a target-loopback per-tab WebSocket
relays the shared worker's raw session protocol. DevTools scope and a retained
live owner are required; owner, grant and provider generations fence both
commands and forwarded data. The resident bounds transport, outstanding work
and output queues, records attachment/command metadata without payloads or
tokens, and closes uncertain streams without replay. Raw commands progress
concurrently so an awaited page promise does not hold up session cleanup.
[Tactical 099](../../docs/tactical/099-windows-streaming-cdp.md) owns focused
x64 per-tab evidence and remaining release/platform gates. Automatic outside
WebSocket tunnels remain unavailable.

**Current, unreleased candidate:** shared browser-level emulation combines
real extension page target IDs with facade browser/tab sessions, the current
default profile, tab lifecycle and connection-local child-session routing.
It preserves Chrome's restricted domains/pages rather than claiming complete
native browser CDP. Root attachment reports already-running targets;
before-first-script popup interception is unavailable. Playwright 1.63 uses
`noDefaults: true`; isolated contexts, downloads and shutdown refuse.
[Tactical 100](../../docs/tactical/100-browser-level-cdp.md) owns real-client
evidence. macOS native changes remain source-only, Linux registration absent.

**Open:** macOS browser-root build/live qualification; Linux registration; other Chromium browsers;
Web Store distribution; signed Mac workstation browser approval acceptance. No Windows ARM64
execution is inferred from the x64 browser evidence.

## Fit and next evidence

**Current:** The owned extension retains global `ON` / `DEV` toolbar badges and
adds blue pointer favicons on controlled tabs and a blue **Machine Control**
group for newly created agent tabs. Generation-fenced cleanup preserves site
icon updates and user group edits. Worker recovery restores recorded changes
without inferring authority. [058](../../docs/tactical/058-browser-tab-indicators.md)
owns the 20-check source and exact signed ARM64 Mac VM evidence, fresh native
visual capture, and desktop 0.4.10 release result. The signed run uses a standing
appliance policy; it does not add workstation browser approval evidence. The
[Codex extension review](codex-browser-extension.md) supplies source-reviewed
interaction patterns for those indicators; no third-party code was adopted.

The source-independent YA consumer additionally passes the bounded browser
fixture in [062](../../docs/tactical/062-installed-agent-cli.md): one semantic
click changes the independent HTTP counter once, and the model consumes its
new tab capture. The optional agent hook in the existing headed harness adds
two checks to its 21-check installed-client route. This is local signed
assembly evidence; publication and other platform/provider cells are separate.

**Decision:** Retain this target-native route behind the common facade. A
remote caller transports the same resident operations; it does not manipulate
a VM window. Signed Windows setup, grants, fixture tasks, reconnect and
local/outside artifact transfer and browser-open updater replacement pass.
The incoming installer
pauses only the owning native-host manifest during replacement, preventing
Chrome retries from locking its executable.

**Open:** In the headed fixture, a trusted CDP mouse dispatch to an inactive tab
acknowledged delivery without changing the page oracle. Selecting that tab
before dispatch produced the effect. Browser pointer activation/effect remains
a separate gap; marker visibility does not establish input effect.

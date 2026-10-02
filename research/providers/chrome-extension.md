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
| macOS per-tab raw CDP WebSocket | `live-tested` | Reads/actions/events on physical and guest Chrome; browser-level attachment absent |
| Windows source-native extension/native messaging | `conformance-tested` | Dedicated x64 VM, browser/devtools enforcement, independent fixture effects and PNG/hash checks; exact installed evidence below |
| Windows signed Tauri extension/native messaging | `conformance-tested` | Exact 0.4.6 x64 VM package; UI setup/approval, independent effects/capture, restart and local/outside browser parity; signed 0.4.4 to 0.4.6 browser-open replacement and lock revocation pass |
| Linux and other Chromium browsers | `upstream-claimed` facilities only | Owned registration and product acceptance absent |

[Tactical 050](../../docs/tactical/050-macos-host-control-mvp.md) and
[Tactical 054](../../docs/tactical/054-windows-browser-and-arm64.md) own execution.
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

**Open:** Windows file upload and streamed raw CDP WebSockets; browser-level
target emulation on all platforms; Linux registration; other Chromium browsers;
Web Store distribution; full signed Mac extension acceptance. No Windows ARM64
execution is inferred from the x64 browser evidence.

## Fit and next evidence

**Decision:** Retain this target-native route behind the common facade. A
remote caller transports the same resident operations; it does not manipulate
a VM window. Signed Windows setup, grants, fixture tasks, reconnect and
local/outside artifact transfer and browser-open updater replacement pass.
The incoming installer
pauses only the owning native-host manifest during replacement, preventing
Chrome retries from locking its executable.

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
Native messaging uses length-prefixed JSON and fixed allowed extension
origins. Windows registers a per-user host manifest in the registry; macOS uses
the browser's native-host manifest directory.

## Architecture and reach

**Current:** Public desktop 0.6.4 packages the 0.8.0 read-only side panel and
native hosts accepting both the unpacked and Chrome Web Store origins on
Mac, Windows and Linux. All six packages are authenticated in
[Tactical 121](../../docs/tactical/121-desktop-0.6.4-release.md); this is package
evidence, not installed store-copy connection evidence. Store review and that
native acceptance remain in [117](../../docs/tactical/117-chrome-web-store-extension.md).

**Current:** Chrome launches the bundled native host. The host relays to a
target-resident provider channel, separate from agent calls and operator
approval. The resident authenticates the provider process and owns browser
and DevTools authorization, reference generations, artifacts, and result
envelopes. The extension mirrors grant state and uses per-tab CDP plus native
tab lifecycle APIs. It is not the approval authority.

| Platform and route | Evidence | Boundary |
| --- | --- | --- |
| Extension 0.8.2 source/unpacked Mac ARM64 background route | `conformance-tested` | 17 claimed VM checks: independent HTTP click/text effects on an inactive tab, PNG, native foreground/key-window/cursor and selected-tab preservation, hidden visibility restoration and explicit foreground/reconnect; 20 ms sentinel sampling, standing appliance authority; other platforms and installed store-copy execution separate |
| Unreleased extension 0.8.1 in signed Mac ARM64 development assembly | `conformance-tested` | Claimed disposable macOS 26.6.2 VM, CfT 155: 81 composed browser/locked-use checks, native until-stopped approval, modal and deadline recovery, independent HTTP/native effects, restart and Stop; SIP disabled, one display; physical/store/mixed-version execution separate |
| Public desktop 0.6.9 Mac ARM64, bundled unpacked provider | `conformance-tested` | Exact signed/notarized app in a claimed Tart VM: fifty download/upload cycles, Settings, native-host loss, blocked-provider Stop, forced-exit recovery and stale-reference refusal; same archive publicly published; Chrome Web Store/Intel/physical execution separate |
| macOS source-native extension/native messaging | `conformance-tested` | Fixture effects, navigation, capture and provider refusal in a Tart guest; predates signed Tauri acceptance |
| macOS locked-console extension/native messaging | `live-tested` | macOS 26.6.2 Tart appliance, Chrome for Testing 155: tab enumeration, AX, independent click/text/navigation effects, PNG capture and reattachment with the OS still locked; standing authority, no covered unlock; workstation source has a separate opt-in |
| macOS source-native workstation locked-console extension | `live-tested` | 26 checks with native approval, retained mixed-grant ID/expiry, desktop/new-approval refusals, browser-owner admission, independent effects, capture, Pause/Resume and disable; ad-hoc VM identity, not signed installed Settings acceptance |
| macOS per-tab raw CDP WebSocket | `live-tested` | Reads/actions/events on physical and guest Chrome; browser-root native changes build in the signed candidate; focused live qualification remains open |
| macOS unreleased signed ARM64 runtime/presentation candidate | `conformance-tested` | Chrome for Testing 154, workstation native approval and no Settings WebView: 21 page/indicator/capture/worker checks through the packaged CLI; no YA agent probe or browser-root streaming qualification |
| macOS signed Tauri, installed Python CLI and YA local Codex | `conformance-tested` | Chrome for Testing 145 in a claimed appliance: independent HTTP counter effect, tab PNG consumed by the built-in agent image tool, plus 21 existing indicator/worker checks; standing policy, not workstation approval |
| Windows source-native extension/native messaging | `conformance-tested` | Dedicated x64 VM, browser/devtools enforcement, independent fixture effects and PNG/hash checks; exact installed evidence below |
| Windows ARM64 source-native locked-console extension | `live-tested` | 18 checks under real native approval with x64-emulated CfT 155 and software rendering: independent locked HTTP effects, capture, browser-owner admission, per-tab streamed DevTools, Pause/Resume and disable; signed installed Settings and native ARM browser acceptance separate |
| Windows signed Tauri extension/native messaging | `conformance-tested` | Public 0.4.8 x64 VM package: setup/approval, independent effects/capture, restart, production browser-open replacement and ordinary uninstall; local/outside parity and lock revocation recorded on 0.4.7 |
| Windows staged x64 file upload | `conformance-tested` | Unreleased real desktop UI, browser-only live SDK owner and CLI request parser; Chrome for Testing 154: direct/multiple inputs, intercepted chooser, independent HTTP byte/hash effects and 23 scope/path/reference/Pause/Stop checks |
| Windows staged x64 per-tab CDP WebSocket | `conformance-tested` | Unreleased real desktop UI and retained DevTools owner, fresh Chrome for Testing 154: commands/events, unresolved-promise concurrency, independent HTTP effects and 28 scope/token/Origin/owner/provider/Pause/Stop checks; signed/ARM64/physical acceptance separate |
| Windows staged x64 browser-level CDP | `conformance-tested` | Shared target facade and native session routing; Chrome for Testing 154, Playwright 1.63 and Puppeteer 25.12: independent clicks, captures, popup/iframe/worker, refusals and 51 real-UI/authority/provider checks; signed/ARM64/physical acceptance separate |
| Linux GNOME Wayland ARM64 source-native locked-console extension | `live-tested` | 37 checks with local operator arming, native CfT 156 in an empty unsandboxed test profile, independent OS lock and HTTP effects, capture, scope refusals, Pause/Resume and disable; signed installed UI and sandboxed browser acceptance remain separate |
| Linux packaged store-origin native host | `built` | Public 0.6.4 package authentication; installed store-copy connection remains open |
| Other Chromium browsers | `upstream-claimed` facilities only | Owned registration and product acceptance absent |

[Tactical 050](../../docs/tactical/050-macos-host-control-mvp.md) and
[Tactical 054](../../docs/tactical/054-windows-browser-and-arm64.md) and
[055](../../docs/tactical/055-unified-desktop-publication.md) own execution.
[Tactical 108](../../docs/tactical/108-macos-runtime-presentation.md) adds
signed unreleased workstation approval with Settings absent.
The [desktop matrix](../../docs/desktop-acceptance.md) separates source-native
and exact installed product evidence.

## Fidelity, consequences, and gaps

**Current (2026-10-27), extension 0.8.4 source:** the manifest declares
`file:///*` host access so Chrome can expose its separate user-controlled
file-access switch. Earlier store manifests omitted that declaration even
though upload errors directed users to the switch. Chrome documents the
[manual file-access grant](https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns#special-cases);
installed store-copy upload qualification remains separate.

**Current (2026-10-26), extension 0.8.2, source-reviewed and contract-tested:**
browser-root management has five-second deadlines, 64 retained requests,
eight unsettled mutation dispatches and eight independent discovery dispatches.
Discovery and tab close bypass the mutation chain. A management timeout fences
and closes its owning connection with an unknown-effect reason; physical slots
remain occupied until Chrome's calls settle. Tests hold `chrome.tabs.remove`
unresolved and prove discovery, replacement-connection progress and no replay.
This repairs a reproduced scheduling defect, not a proven historical modal cause.

**Current:** new tabs default to background creation in both ordinary and
browser-root operations. Known CDP activation requires explicit one-shot or
connection-local opt-in, rechecked for queued activation and reset on reconnect.
Input uses `Emulation.setFocusEmulationEnabled` before dispatch. This changes
page focus/visibility semantics without selecting the tab or raising its window.
Release explicitly clears the override before detach; uncertain reset appears in
release and tab metadata. Normal hidden visibility returns in the Mac fixture;
`document.hasFocus()` can remain true from injected input even after the override
ends. DOM focus is not a reliable oracle for OS focus or override cleanup.
The [extension guide](../../providers/chrome-extension/README.md#background-operation)
owns the command syntax. Arbitrary scripts, site popups and separately authorized
native control remain outside this cooperative foreground policy.

**Open:** Chrome UI confirmations such as saved-group deletion are not the
`Page.javascriptDialogOpening` dialogs tracked by `browser.dialog`. Their exact
extension close/ungroup trigger and recovery still need live qualification.
The bounded management repair does not automatically accept or dismiss them.

**Current (2026-10-25), unreleased 0.8.1, `source-reviewed` and
`contract-tested`:** ordinary per-tab scheduling bounds retained work and
physical slots, preserves request-local authority through awaits, and fences
canceled/expired continuations. Recovery has independent bounded execution.
Dispatched failure remains uncertain; queued input refuses. Attachment tokens,
raw-callback accounting and a separate Page-event readiness state prevent stale
callbacks from claiming a fresh route. A perpetually unsettled raw attach keeps
its tab and one of eight attachment slots fenced; a browser restart is the
recovery boundary. This is not an automatic restart or consent revocation.

**Current, bounded signed ARM64 VM `live-tested`:** with Chrome for Testing
155 on macOS 26.6.2, a beforeunload dialog survives debugger detach but a new
session's `Page.enable` stays pending and raw `Page.handleJavaScriptDialog`
returns no dialog to handle. This qualifies that specific route, not every
Chromium implementation. Explicit release therefore refuses promptly while an
observed, recoverable dialog is open. Typed handling retains the original
attachment; subsequent release invalidates old IDs. Tabs lists observed dialog
IDs/types, while `not_observed` and pending/failed observer states never assert
absence. Streams retain observed dialogs on closure; authority loss always
ends control. A dialog that appears after release can still require native UI.
[Tactical 138](../../docs/tactical/138-remote-arming-recovery.md) owns composed
signed development-assembly qualification; store and mixed-version rollout
remain separate.

**Current (2026-10-17):** bounded [macOS locked-console evidence](../platforms/macos.md#browser-control-with-the-console-locked)
shows browser operations need not unlock the OS console under standing
appliance authority. Unreleased workstation source provides a separate default-off
preference and scope enforcement; the existing covered desktop setting is a
different mechanism. New approval while locked remains unavailable.

**Current:** Snapshots expose tab accessibility nodes. References bind grant,
provider, and extension snapshot generations. Source 0.8.2 click/text input
uses virtual page focus; earlier revisions could require tab activation. The
OS cursor is expected to remain unchanged. Captures are
tab PNGs, not whole-desktop captures. CDP acknowledgement establishes delivery,
not independent application effect; the fixture's own marker supplies that
oracle.

**Current (2026-10-24), source-reviewed and contract-tested:** worker references
now also carry a random authority epoch. It changes on native disconnect,
release and grant replacement; a fresh worker starts with a new epoch. Numeric
snapshot counters alone previously allowed old references to become valid
again. Ordinary requests bind authority at message arrival and recheck it
around CDP awaits and before navigation effects. A held-geometry regression
proves that a revoked click cannot resume its mouse press under a new grant,
and queued old work refuses. This fence does not undo input already delivered
before revocation. [Tactical 136](../../docs/tactical/136-desktop-crash-hardening.md)
owns packaged recovery evidence.

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
evidence. macOS native changes build in the signed candidate, but browser-root
live qualification remains open; Linux browser-root qualification is separate.

**Open:** macOS browser-root live qualification; Linux installed store-copy qualification; other
Chromium browsers; Web Store review and installed store-copy connection
([117](../../docs/tactical/117-chrome-web-store-extension.md)); broader physical/Intel Mac
workstation browser acceptance. No Windows ARM64 execution is inferred from
the x64 browser evidence.

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

**Current, bounded Mac VM evidence:** the inactive-tab click without virtual
focus acknowledged delivery without a page effect; explicit focus emulation
produced the independent click and text effects while a separate native
sentinel retained foreground/key-window state, text and cursor position.
The source route integrates this preparation without an activation fallback.
[Tactical 140](../../docs/tactical/140-background-browser-control.md) records
final acceptance, cleanup and store rollout limits. Other platforms, website
behaviors, transient focus changes below the 20 ms sentinel sampling interval,
and installed store-copy execution need separate qualification.

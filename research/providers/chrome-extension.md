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

**Decision, implemented in unreleased desktop adapters:** the [unified permission model](../../topics/access-admission-and-pause.md#unified-permissions-and-handoff-contract)
treats Browser as one surface including supported CDP and page JavaScript,
independent of Desktop's mode. Existing browser/DevTools scope flags and the
acceptance matrix below describe current implementations. [Tactical 153](../../docs/tactical/153-unified-permissions-and-handoff.md)
owns Windows-first migration and removal of temporary legacy paths; no new
provider reach or live qualification is implied by this decision.


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
| Shared TypeScript core/adapter, Mac ARM64 scratch native-messaging route | `live-tested` | Eight headless two-process profile checks with the unchanged 0.8.4 worker: independent HTTP effects, exact approval/refusals, Stop, held reply and native relay reconnect; fixture identity/operator authority, browser sandbox disabled; same-process profiles, native authentication, installed packages and Linux execution separate ([151](../../docs/tactical/151-shared-core-real-browser.md)) |
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
| Windows ARM64 shared coordinator and named profiles | `conformance-tested` | Clean-source unsigned candidate: 39 checks with two regular profiles in one native ARM64 Chromium process, one registration, independent ordinary/page/root-CDP effects, Stop/expiry/reconnect/death and real Settings lifecycle; sandbox enabled, software rendering; signed/store/physical/x64 and Mac/Linux acceptance separate |
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

## Multiple-profile limit

**Historical (2026-11-02), source-reviewed before adoption:** the worker hello carried protocol,
extension version and user agent, with no persistent profile identity. The
macOS resident's `BrowserRelay.register` disconnects the current provider on
every trusted registration; Linux's `Browser.register` likewise disconnects
its singleton provider. The worker reconnects automatically and resets its
retry delay to one second on any resident message. Two accepted installations
can therefore repeatedly displace each other on those routes. The user reports
this symptom with two Chrome profiles; this investigation did not reproduce it
live or identify their exact installed versions.

At that reviewed revision, Windows also had a singleton provider, with
`BrowserRelay.RunAsync` serving one named-pipe connection at a time; the
macOS/Linux replacement-loop mechanism was not evidence of identical Windows
oscillation. The unreleased Windows source now replaces that path with
concurrent authenticated transports into the shared TypeScript coordinator.
The unreleased Mac source now uses concurrent authenticated transports and
exact profile selection as well. Linux source now does the same; its bounded
native/profile/package evidence and qualification limits are recorded below.

**Decision:** [named browser profiles](../../topics/browser-profiles.md) owns
the full registry/selection/authority direction; no interim singleton fix is
planned. [Tactical 149](../../docs/tactical/149-browser-profiles.md) scopes the
work. The shared-core scratch route below is bounded live evidence, not
qualification of installed multi-profile control or the existing singleton
residents.

**Current (2026-11-03), bounded Windows ARM64 `conformance-tested`:** the
extension has persistent origin-namespaced installation UUIDs, local names and
availability preferences. Windows requires profile protocol v1 before authority,
rejects copied live identities without replacement, and routes exact approved
IDs through one shared host. Native contracts and ARM64/x64 builds pass. A
clean-source unsigned ARM64 candidate passes 39 checks with two regular profiles
in one native Chromium process, independent ordinary/page/root-CDP effects,
owner/Stop/expiry/reconnect/child-death fencing and the real Settings lifecycle.
Sandboxed software-rendered fixture execution, exact source and verified cleanup
are recorded in [Tactical 152](../../docs/tactical/152-shared-runtime-windows-adoption.md).
An earlier fake-peer composition also passes five-minute owner continuity.
This does not establish signed installation, store delivery, physical/GPU/native
x64 or Mac/Linux multi-profile execution. Later Mac evidence is scoped below;
Linux evidence is scoped separately below.

**Current (2026-11-04), bounded Mac ARM64 `conformance-tested`:** the real
packaged Swift resident hosts the same pinned TypeScript authority. Twenty
ad-hoc appliance checks exercise native Settings/announcements, two Chrome for
Testing profiles, exact Work-only consent, independent Work effect with zero
Personal effects, independent pauses, Stop, an actual selected-profile CDP
stream, revocation of that open stream and the shipped Python SDK. Native app/policy/preferences and
owned processes are restored. This establishes neither physical input,
Intel execution, signed publication nor protected-helper composition.
[Tactical 154](../../docs/tactical/154-macos-shared-surface-adoption.md) owns
acceptance, cleanup and qualification limits.

**Current (2026-11-04), bounded Linux ARM64 `live-tested`:** the ordinary
Python resident hosts the same pinned authority and concurrent authenticated
native-host connections. Sixteen GNOME Wayland checks establish two enabled
profiles, independent Work-only HTTP effects with zero Personal effects,
unapproved-profile refusal, real owner-bound streamed CDP and stream revocation
on Stop while both profiles remain connected. A concurrent Desktop owner
cannot use physical input or GNOME Shell semantics to answer Browser approval;
its own session remains active. These are isolated Playwright Chromium profiles
with an explicit disabled fixture sandbox, not the user's installed browser.
Source `0435ccf` also passes 29 combined profile/locked/restart checks:
preapproved Work effects preserve the real GNOME lock, Desktop stays unavailable,
Pause/Resume and opt-in withdrawal work, and abrupt armed process loss restores
both connections with authority Off and no replayed page effects. The exact old
pinned Node child also dies with its native parent. Both unsigned packages pass
real Settings and shipped-SDK acceptance; original package/helper state and
Off are restored, owned processes/staging are removed and the claim is released.
Physical HID, signed release/store delivery and other compositor/hardware coverage remain separate.
[Tactical 155](../../docs/tactical/155-linux-shared-surface-adoption.md).

**Current (2026-11-02), bounded Mac ARM64 `live-tested`:** a Node-hosted adapter
consumes the unchanged worker protocol through real Chrome native messaging,
with identity assigned by private fixture endpoints. Two fresh persistent
profiles in separate headless Chrome for Testing processes exercise the same
TypeScript core as its deterministic suite. Trusted-click HTTP counters prove
profile-specific effects; extension panels observe Stop and controlled-tab
cleanup; a held callback cannot resolve a newer request, and native-host
transport loss leads to a fresh connection without disturbing the other
profile. This route uses fixture operator authority and a disabled browser
sandbox; it does not test production peer authentication, same-process Chrome
profiles, real account data, native consent, installed setup or store delivery.
[Tactical 151](../../docs/tactical/151-shared-core-real-browser.md) owns execution.

**Current (2026-11-02), bounded process-host follow-up:** the same fixture now
runs policy and its adapter in a separate child. Packaged Node and compiled
Bun both pass ten checks on Mac ARM64, adding scheduled grant expiry and hard
coordinator death/restart. Native-port loss clears both real panels; restart
has no consent or request replay, and old references refuse. Independent
trusted-click totals are six and four. These are synthetic fixture effects,
not installed native authentication or same-process-profile qualification.
[Tactical 152](../../docs/tactical/152-shared-runtime-windows-adoption.md) owns
the deployment decision and remaining Windows adoption gates.

## Fidelity, consequences, and gaps

**Current (2026-11-03), source repair with deterministic regression:** a real
Windows root-CDP run observed successful tab creation before `getTargets`
published its page target. `Target.createTarget` now waits for observation
inside the existing management deadline, creates exactly once, and fences late
observations on connection replacement. Delayed/missing-target and replacement
fixtures cover those cases. Bounded Windows qualification is recorded in
[Tactical 152](../../docs/tactical/152-shared-runtime-windows-adoption.md).

**Current (2026-11-02), bounded physical-macOS `live-tested` recovery:** the
connected native-host origin identified the development provider. Its legacy
references and hidden-input behavior differed from current source. Chrome
refused its first reload because of a generated `__pycache__`; moving only that
cache out and using the explicit retry loaded current operations. Static and
focus-sensitive background fixtures then produced one trusted pointer/click
sequence and HTTP effect each while independently locked, with text, PNG and
selected-tab preservation. Cleanup relocked and retained approval. The old
worker's exact revision and the individual effects of code reload versus state
reset remain unisolated. This does not qualify store delivery or other sites.
[Tactical 147](../../docs/tactical/147-physical-browser-provider-validation.md)
owns the before/after evidence.

**Current, unreleased diagnostics and development packaging:** granted
`browser.tabs` returns extension ID/version, protocol version and a digest of
the executing operation closure. It deliberately does not fetch current disk
contents or claim a whole-module/import fingerprint, authentication or effect
proof. A new clean unpacked-output mode preserves the development key and
excludes helper/cache files without mutating source or overwriting an existing
directory. Contract and polluted-source packaging tests cover those boundaries.

**Current (2026-11-02), owned source repair, bounded VM `conformance-tested`:**
the worker measured click geometry before preparing virtual focus. An owned
focus/visibility callback moves the target by 180 CSS pixels; four background
zoom cases missed while selected-tab controls passed. Preparing focus before
scroll/geometry repairs the deterministic regression and the 18-check live
background/sentinel suite. Eight repaired store-origin unpacked comparisons
also pass selected/background and zoom cells while IOKit independently reports
locked, with one HTTP click per case and preserved background tab selection.
This uses signed desktop 0.6.11, macOS 26.6.2 ARM64 and separately identified
Chrome for Testing 156.0.8078.80. Ordinary static cases also passed before the
repair, including earlier CfT 155 cells. Subsequent physical recovery is owned
by Tactical 147 above; it does not identify the original worker revision.
Store delivery, exact physical-browser patch
and other platform execution are not qualified. [Tactical 146](../../docs/tactical/146-background-browser-click-reproduction.md)
owns the recorded comparisons and cleanup.

**Open, usage-journal review (2026-11-01):** repeated terminal input reports
describe acknowledged `Input.insertText` without visible terminal text, while
explicit key events worked in one recovery. Frame targeting, application input
semantics and installed-provider differences remain unisolated. Qualify an
owned embedded-terminal fixture independently from ordinary HTML fields. The
[review](../../gaps/2026-11-01-usage-journal-review.md) records this gap separately
from background click delivery and the passing VM background-input cells.

**Current (2026-11-01), historical bounded physical-macOS `live-tested` gap:** the
connected extension reported 0.8.4, but a locked-console background click
acknowledged delivery without an independently observed fixture effect. Text,
inspection and capture worked. The exact installed artifact combination and
historical implementation remain unisolated; this does not supersede the separately qualified VM
route. The [gap record](../../gaps/2026-11-01-locked-background-browser-click.md)
owns observations, oracle limits and the required matched comparisons.

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

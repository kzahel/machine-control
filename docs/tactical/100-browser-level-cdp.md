# Browser-level CDP compatibility

Topics: [browser-control](../../topics/browser-control.md),
[windows-desktop](../../topics/windows-desktop.md).

Status: complete for the unreleased Windows x64 candidate; macOS source-only.

## Objective and completion conditions

The user requested browser-session attachment after Windows per-tab streaming
CDP: reuse shared extension behavior across platforms and commit the result.
Provide a browser-root endpoint for existing default-profile tabs, discovery,
new tabs/popups, flattened per-target sessions and related frame/worker routes.
Prove real Playwright and Puppeteer tasks in the claimed Windows test appliance
with independently observed effects, and preserve owner/grant/provider fences.

## Boundaries

The extension owns target semantics; native residents own authenticated
loopback transport and grant/owner policy. Windows retains its live DevTools
owner requirement. macOS retains its existing grant policy and receives source
bridge changes; neither macOS execution nor Linux registration is inferred
from Windows evidence. Restricted tabs/domains, isolated contexts, browser
shutdown and browser-wide download policy remain unavailable. Visual tab-group
editing is a separate browser API feature; contexts do not emulate groups.

## Ordered work

### 1 — expose the browser connection

Add `browserEndpoint` beside the existing `devtoolsEndpoint` template. Preserve
loopback/token/Origin gates, native generations, bounded commands and output,
payload-free audit, Pause/Stop and no replay. A browser connection owns the
extension's debugger attachment exclusively versus raw per-tab connections.

### 2 — implement shared discovery and sessions

Use real page target IDs from `chrome.debugger.getTargets`, native tab lifecycle
and extension debugger commands. Expose a logical default-profile context and
facade browser/tab wrappers for client compatibility. Map child session IDs
per connection; reject unknown/stale IDs and preserve routing on replies and
events. Report wrapper attachments as already running: browser-level attachment
cannot promise to pause a new renderer before its first script executes.

### 3 — prove browser clients and cleanup

Exercise pinned Playwright/Puppeteer packages using a separately identified
Chrome for Testing and the real desktop operator. Verify existing pages, new
tabs, clicks with independent HTTP effects, captures, popup/frame handling and
explicit unsupported operations. Exercise authority transitions through the
real UI, reap owned processes, restore browser registration, remove owned
staging, return the VM to its original power state and release its claim.

## Validation and final result

All 51 focused checks pass in the accepted Windows-hosted VirtualBox appliance
using the real Medium desktop operator, retained SDK DevTools owner and a fresh
Chrome for Testing 154.0.8037.92 profile. Playwright 1.63.0 with `noDefaults: true`
attaches an existing default-profile page, creates and clicks a tab, captures a
real PNG, discovers/controls a popup and routes cross-site iframe and dedicated
worker commands. Puppeteer 25.12.0 with `defaultViewport: null` attaches through
tab-wrapper/page sessions, creates/clicks/captures/closes a new page and
disconnects. Both clients' button clicks reach the independent HTTP oracle
exactly once. They refuse isolated contexts explicitly; shutdown and download
policy also refuse. No browser debug port is enabled.

The run repeats the existing raw-stream checks, then proves browser token and
Origin gates, exclusive root/per-tab attachment, forged session refusal,
Pause/Resume rotation, owner disconnection, native-host loss/reconnect and Stop.
The synthetic effect sequence contains only the three deliberate raw commands
and two browser-client clicks. No command is replayed automatically.

Shared fixtures prove target filtering, default-context boundaries, discovery,
native child-session translation, stale result/event suppression, cleanup and
Puppeteer wrapper attachment. Windows transport fixtures prove root routing,
reply/event session preservation, exclusivity, revocation and uncertain audit
completion on mismatched reply sessions. Desktop/unlock contracts, both format
checks, x64/ARM64 self-contained publishes, nine extension tests and 232 common
client tests pass (nine platform skips). Python/Node syntax and Git whitespace
checks pass. The legacy Windows smoke passes in WSL with local jq and its test
NVRAM fixture. macOS smoke/Swift tests cannot run on this host: native plutil
and Swift/Darwin tooling are unavailable. No Mac build or execution is claimed.

The live-tested runtime SHA-256 is
`4c9e5ecde6c92846ebd88d0cbad696ccebe9cbc62a3fa062e7491dfbf4198e75`;
the shared browser-facade module is
`0da2a5494654ace5c75ffa0cfbf714339bd29d8e00358a34ecb4739ed9f34fde`;
the worker is
`0de9637c03456b22b299524a1f959efa69e3d6c78463afb148f18768d5c77e03`.
Independent inspection confirms staged source hashes, zero owned processes and
no candidate registry/manifest references after actor cleanup. The owned staging
directory and scheduled task are removed; canonical credential verification
passes. The VM returns to its initial powered-off state in 37.945 seconds using
the existing declared bounded scheduling assist; no force-stop is used. Both
the ordinary test claim and the separate disruptive shutdown claim are released.
This does not establish unassisted VirtualBox shutdown. Cold boot initially
reports administration unavailable, then becomes reachable without outer input
or pause/resume recovery; stored-credential native login succeeds.

Final source review adds one shared cancellation guard after that exact live
candidate: native user cancellation/DevTools takeover closes the root session
instead of allowing indicator cleanup's tab update to auto-attach it again.
The regression emits Chrome's `canceled_by_user` event, proves closure and no
reattachment, and passes with all nine shared fixtures. Normal target closure
remains a per-target lifecycle event. This branch has not received a headed
Chrome Cancel test; the hashes above retain the exact VM-qualified candidate.

The [streaming guide](../../desktop/WINDOWS-STREAMING-CDP.md) owns usage and
limits. The repeatable Windows actor and real-client runner live under
[`tests/windows`](../../tests/windows/README.md); exact deployment locators,
profiles and evidence remain private. This is an unsigned development assembly,
not signed installed release qualification. macOS native build/live, Linux
registration, ARM64 live, physical targets, other browsers, isolated contexts,
browser-wide operations and automatic outside tunnels remain separate gates.

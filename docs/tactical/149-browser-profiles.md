# Implement named browser profiles

Owning topics: [browser profiles](../../topics/browser-profiles.md),
[browser control](../../topics/browser-control.md).

Status: **scope complete; implementation not started**.

Prerequisite: [Tactical 150](150-shared-resident-core.md) proves the shared
policy/reference-provider boundary. The native steps below are adoption work
around that core, not authorization to implement portable policy three times.

## Objective and completion conditions

The user requested scoping full named-profile support after two Chrome
profiles with the extension repeatedly displaced each other. They chose the
multi-profile direction and disabled their extra installation temporarily;
they did not request an interim singleton fix or implementation in this turn.

Implement the proposed contract in the owning topic: multiple stable provider
connections, local labels and availability, explicit agent selection, exact
profile approval and profile-bound ordinary/CDP operations. Complete the
feature only when two real profiles can coexist through normal operation and
fault recovery, without cross-profile page access or authority expansion, on
each claimed supported desktop platform. Source tests, live acceptance,
packaged acceptance and store delivery remain distinct gates.

## Boundaries

Keep the existing native messaging route and host authentication, Browser and
DevTools scopes, native approval, desktop admission and local/remote facade.
No interim single-provider release, automatic takeover/failover, global active
profile, new browser contexts, independent-owner concurrency, account-name
discovery, incognito support or new Chromium-brand qualification.

This record authorizes no deployment or publication. Future live work must
use claimed dedicated appliances, stored credentials and private usage and
provisioning journals as applicable. Use command-driven Chrome for Testing
fixtures, including two profiles in one browser instance. Do not test with a
temporary profile under the user's primary browser identity. Any later
physical-profile follow-up needs its own bounded scope; preserve the user's
disabled personal installation during scoping.

## Ordered work

### 1 — define profile discovery, selection and authority

Specify profile metadata, `browserProfileId`, availability revision,
per-connection generation, exact grant profile sets, refusal codes and protocol
negotiation in the common contracts. Keep label resolution on the resident;
labels are unique selectors only when unambiguous. Define metadata-only
discovery separately from granted tab discovery. Freeze the identity,
duplicate-ID, disable/re-enable, stale-reference and no-selector rules before
implementing transports.

Update `contracts/request-v0.schema.json`, the Windows typed request in
`src/MachineControl.Windows/Contract.cs`, and focused profile/discovery response
schemas and fixtures. Cover missing/unsupported profile fields so old clients
cannot have an explicit selector silently discarded. Return the resolved
profile ID and generation on browser results and session status.

### 2 — identify and configure extension installations

Add a small profile-state module beside
`providers/chrome-extension/service_worker.js`. Initialize local UUID, label
and availability before connection; extend the hello/accept handshake with
profile capability negotiation. Existing `storage` permission suffices.
Only the extension panel can change its local availability/label through typed
worker messages; an ordinary page or resident browser request cannot enable it.
Validate label bounds and render labels as text.

Update `panel.html`, `panel.js`, badge/setup states and store mocks. Show
disabled, connected/unapproved, approved and incompatible/conflicted states
without treating a successful native port as browser authority. Disabling must
fence dispatch immediately and trigger bounded debugger/indicator cleanup even
when the resident is unavailable. Preserve worker recovery and Stop behavior.
Old workers cannot receive authority from a profile-aware runtime without a
completed compatible handshake; new workers refuse old-runtime authority.

### 3 — implement registry and approval in the Windows vertical slice

Refactor `src/MachineControl.Windows/BrowserRelay.cs` into a bounded registry
and per-provider connection state. Replace the one-pipe-at-a-time accept loop;
keep native peer checks before untrusted frame reads. Separate pending
transport registration from profile admission. A newly identified profile or
duplicate identity must never displace another profile's provider state.

Extend `DesktopGrants.cs`, operator dispatch, native approval presentation and
grant/status projection with exact profile sets. All arming, request approval,
restoration and dispatch paths must use the same profile authorization check.
Keep request/response, grant fan-out, health, limits and cancellation isolated
by profile; retain an aggregate bound as well as per-profile bounds.

In `BrowserDevToolsBridge.cs`, bind tokens and sessions to the chosen provider
and generation, including per-tab ownership maps currently keyed only by tab
number. Browser-root discovery stays inside the selected profile. An unrelated
connection/restart must not cancel valid work on the other profile.
Verify the real scope of `chrome.debugger.getTargets` with two profiles in
one process; filter page targets against that installation's permitted tabs
and bind child frame/worker sessions to their already-authorized parent.
Do not assume that every Chrome discovery API has identical profile filtering.

### 4 — expose profile choice in the desktop and common clients

Replace the single connection presentation in `desktop/src/main.tsx` with a
profile list in Permissions, and profile selection beside Browser/DevTools
access controls. Extend `desktop/src/access-choices.ts` to remember exact
selected IDs as form choices without arming them. Approval names exact
requested profiles; adding an available profile never edits a live grant.

Extend `client/machine_control.py` browser discovery/help/request parsing with
`browser profiles` and `--browser-profile ID_OR_UNIQUE_LABEL`. Extend
`client/control_session.py` to carry a profile through control.open, the
single-shot admission handoff and retained requests, with one pinned profile
per browser-capable owner. A rejected ambiguous selection must remain
undispatched. Explicit selectors on unsupported runtimes fail clearly.
Update installed-client guides, raw JSON examples and consumer discovery
instructions; do not create a second profile registry in an agent integration.

### 5 — implement macOS and Linux parity

On macOS, refactor `BrowserRelay.swift` and `BrowserDevTools.swift` into
per-profile state, then update `Grants.swift`, `OperatorConsent.swift`,
`RuntimeOperator.swift`, native approval, admission and `Server.swift` routing.
Preserve console-bound saved consent while requiring fresh browser approval
for legacy consent lacking exact IDs. Update the minimized browser status
projection in `platforms/macos/host/machost.py` intentionally; do not leak
labels, native paths or identity details into public doctor evidence.

On Linux, refactor `desktop/native/linux/browser.py`, `grants.py`, approval,
coordinator and session dispatch for the same profile contract. Reuse native
host framing/authentication and existing GUI-session binding. Linux does not
currently expose the Windows/macOS streaming CDP bridge; implement named
profiles for its existing operations and continue reporting streaming as
unavailable. Building a new Linux WebSocket bridge is outside this slice.

Update each platform's operator/status bridges and audit operation allowlists
for metadata discovery and profile-specific outcomes. Preserve the existing
locked-browser preference and same-console restrictions.

### 6 — qualify lifecycle, effects and delivery

Add focused tests to existing worker, native relay/grant, Windows contract,
Linux, common-client and shared-UI suites. Extend a command-driven live runner
for two profiles with separately addressable fixture pages and independent HTTP
counters. Include both profiles in one Chrome for Testing browser instance,
plus separate test-browser processes for connection isolation.

Run the acceptance matrix below with truthful per-platform evidence. Build
matching bundled extension/native candidates; qualify exact packaged behavior
before any desktop release. Chrome Web Store installation and both update
orders require separate acceptance. Publication is a subsequent task under the
existing release workflows, not part of this scoping result.

## Acceptance matrix

| Area | Required evidence |
| --- | --- |
| Coexistence | Two profiles remain connected through repeated alternating operations for at least five minutes; no replacement/reconnect oscillation and no unexplained provider-generation change. |
| Independent effects | Work/Personal fixtures independently count navigation, click, text and upload effects; capture and tab discovery belong only to the selected profile; background tab/native foreground preservation retains existing checks. |
| Selection | Exact ID, unique label, duplicate labels, omitted selector with one/multiple authorized profiles, renamed and disconnected selected profile; no fallback to a connected unauthorized profile. |
| Authority | Disabled/newly enabled/unapproved profile cannot enumerate tabs or execute; pending approval cannot expand; new profile does not inherit existing Browser or DevTools approval; disable/re-enable requires reapproval. |
| References | Synthetic reused tab numbers and foreign references/dialog/session IDs refuse before dispatch across profiles and connection generations. |
| CDP where supported | Real browser-root and per-tab clients discover/act only in the bound profile; foreign tab IDs/tokens refuse; profile restart closes only its own streams; no endpoint retargeting. |
| Faults | Worker/native-host/browser/resident restart, duplicate installation IDs, stalled page, pending/late replies, handshake timeout, capacity, both update orders and unsupported client selectors; bounded cleanup and no replay. |
| Global controls | Pause, Stop, expiry, lock preference and console replacement fence all affected providers; profile loss/disable does not revoke unrelated profile authority. |
| Persistence | Rename/restart preserves identity; reinstall/reset does not inherit old approval; saved UI choices grant nothing; Mac consent never expands its recorded profile set. |
| Same interface | Local and outside callers select the same profile through existing target/claim transports; selectors survive adapters and single-shot/retained admission. |
| Privacy and cleanup | Discovery has no page/account data; no new identity permission, incognito reach or secret-bearing logs; owned browsers/servers reaped, target claims and staging released. |

Use `node --test tests/browser/*.test.mjs`, relevant common-client/native/UI
regressions and `python3 bin/check --portable`. Windows runtime changes require
`dotnet format --verify-no-changes`, contract tests and ARM64/x64 publishes
before a later commit. Use native Swift/Linux checks and exact candidate
acceptance for their changed surfaces. Do not infer live execution from a
cross-compile or store delivery from a successful bundled-provider run.

## Sizing and main risks

This is a cross-platform feature rather than an extension-only setting. The
six ordered steps are implementation/review units, not six independent small
patches or a calendar estimate. The largest work is exact-profile consent and
session propagation, the Windows concurrent accept loop, and CDP isolation.
The label field and discovery UI are comparatively small.

Prefer a complete Windows contract/extension/client/UI vertical slice followed
by Mac and Linux parity over a separate singleton hotfix. Do not advertise
multi-profile support on a platform before its own evidence passes. No
third-party provider research or new dependency is needed to begin.

## Validation and final result

Scoping only: reviewed the current extension handshake/retry and side panel,
all three resident singleton relays, Mac/Windows CDP bridges, grant models,
common CLI/admission handoff, saved choices and setup UI. The owning topic
records the proposed behavior and this tactical records implementation order
and acceptance gates. No runtime, installed extension, user profile, package
or release has been changed. Multi-profile execution remains unqualified.

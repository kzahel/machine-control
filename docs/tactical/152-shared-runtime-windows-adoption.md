# Shared runtime decision and Windows browser adoption

Owning topics: [shared-resident-core](../../topics/shared-resident-core.md),
[browser-profiles](../../topics/browser-profiles.md).

Status: **complete for the bounded Windows browser cutover; Mac/Linux adoption
and signed publication remain separate**.

## Motivation and objective

Two browser profiles exposed duplicated resident policy across Swift, C# and
Python. The deterministic and real-browser slices established a reusable
TypeScript policy implementation, but did not settle its installed language,
process placement or native integration. The user requested a larger
autonomous milestone with a decision and a migrated product path, rather than
an indefinite sequence of harness improvements.

Choose the shared runtime language and deployment model, then migrate the
complete Windows browser path through it. Preserve ordinary browser and CDP
behavior, and remove the policy it replaces. A passing development fixture
alone does not complete this milestone.

## Completion conditions

- A durable language/deployment decision with measured packaging and execution
  evidence, rejected alternatives, limitations and maintenance obligations.
- Reproducible build smoke for the six desktop targets. Distinguish a built
  artifact from actual execution and installed acceptance on each target.
- Production extension identity and exact profile selection through one native
  host registration, including two profiles belonging to one browser instance.
- One owner for browser approval, expiry, routing, request lifetime and cleanup;
  authenticated native transport and OS safety remain native responsibilities.
- A packaged Windows candidate on a dedicated claimed appliance passes
  independent ordinary/CDP effects, Stop, expiry, reconnect/restart and stale
  reference checks, with settings absent and reopened.
- Commits, explicit accounting of removed native policy, and a concrete Mac
  and Linux adoption plan based on the proven boundary.

## Boundaries

Use the owning topic's [shared resident core, reference target and Windows
adapter terminology](../../topics/shared-resident-core.md#terms-and-current-scope).
Develop those together. Keep the Python CLI/client implementation; a client
rewrite, new TypeScript session SDK and client-language cutover are outside
this tactical. Compatible profile-selection interface changes remain in scope.

No publication, personal installation replacement, all-platform migration,
arbitrary privileged execution, or replacement of protected native services.
Preserve unrelated worktree changes. Use existing dedicated appliances with
claims and cleanup; fresh provisioning also requires its private journal.

## Ordered work

### 1 — settle executable deployment

Qualify pinned Node and Bun executable deployment against the existing core
and real browser. Measure the edit/check loop, startup and basic resource use.
Exercise EOF and process death while requests are unsettled, with no replay or
authority restoration on restart. Keep the policy source independent of the
selected host. Do not build a full Rust competitor unless a concrete blocker
requires a small reproducer and comparison. Settle the choice explicitly.

### 2 — define and enforce the native boundary

Map existing Windows authority before migrating it. Native code authenticates
operator and provider peers, observes console/session safety, retains caller
admission and performs OS effects. Shared policy owns exact browser profile
approval, finite lifetime, routing, dispatch deadlines, fencing and cleanup.
Native OS unavailability is an input that revokes or blocks authority; it must
not become a second independently renewable browser grant. Specify how browser
authority composes with the existing desktop owner and raw-CDP lifetime.

### 3 — implement named browser sessions

Add persistent installation identity, manual labels and exact profile sets.
Use one registration and concurrent authenticated native transports. Bind
ordinary references, endpoint tokens, CDP sessions and per-tab reservations to
the selected profile and generations. Old consent and incompatible protocol
versions must not silently gain browser authority. Delete/delegate replaced
Windows grant and singleton routing logic.

### 4 — qualify the Windows candidate

Run strict portable checks, Windows contract checks, formatting and ARM64/x64
publishes. Use a dedicated appliance and separately identified test browser,
retain private minimized evidence, test independent effects and failure
cleanup, then release claims and restore the appliance's initial power state.
Report exact coverage and any unfulfilled gate honestly.

### 5 — close the decision and adoption plan

Update current topic truth and component ownership. Record the measured
language decision, implementation result, policy removed and remaining Mac/
Linux migration work. Commit reviewable changes with the owning topic
trailers. No release or push is implicit.

## Execution and source result

**Decision:** TypeScript policy in a privately bundled, hash-pinned Node LTS
child, owned by the native resident independently of Settings. The
[owning topic](../../topics/shared-resident-core.md#language-and-deployment-decision)
records measurements, the working Bun alternative, rejected rewrite and
maintenance obligations. Node 24.22.2 payloads build for all six desktop
targets. Earlier comparison payloads also exercised Bun 1.4.4; those are
qualification artifacts, not another adopted implementation.

**Current source:** the production inlet covers every ordinary browser
operation, exact named profile sets, separate DevTools scope, timed/until-Stop
consent, original-consent checkpoints, native safety ceilings and bounded
CDP endpoint/stream lifetime. The reference provider models stateful browser
effects behind that same policy. It contains no grant/routing engine.

Windows `BrowserDevToolsBridge.cs` is deleted. Its endpoint/token, stream,
reservation and CDP correlation policy now belongs to the shared host.
`BrowserRelay` retains concurrent authenticated pipes, native owner/safety
checks, payload-free journal persistence and validated file/artifact effects;
it no longer owns singleton selection or a competing browser request engine.
`DesktopGrants` delegates browser authority and restoration to the shared
projection. Generic desktop grants, admission and protected services remain
native. The Python CLI/client remains Python, with compatible `browser profiles`
and explicit `--profile` capability negotiation.

The extension stores a local installation UUID, name and enabled preference,
without account discovery or synchronized storage. Windows requires profile
protocol v1. Incompatible/colliding copies remain connected but unarmed with
repair guidance. Existing Mac/Linux residents retain their legacy protocol
behavior until adoption; they cannot honor explicit profile selection.

Desktop/native approval selects exact enabled IDs and remembers form choices
separately from authority. A profile can withdraw only its own availability;
re-enabling it cannot restore consent. The core's opaque checkpoint preserves
original expiry and withdrawal revisions across temporary native grants.
Global Stop and process death invalidate saved consent. Wire IDs and grant
fences include a fresh child boot namespace to reject old worker callbacks.

Packaging includes the pinned Node runtime, owned source, `ws` and notices.
Windows Node bytes remain unchanged through signing: the product catalog
binds the payload manifest and full-byte verification checks its exact file
set. Source-clean companion staging binds the same source revision as the
Tauri app and bundled Python client. Unsigned staged development acceptance
is distinct from signed installer/publication qualification.

### Verification performed

- Strict TypeScript checks and 48 shared runtime regressions pass, covering
  controlled clocks, stateful reference effects, profile isolation, authority
  replacement/restoration, IPC, EOF/death and strict CDP transport cases.
- The complete portable runner passes, including Python client, release
  packaging and 15 extension worker/facade tests. Desktop strict build
  and both real-built-frontend saved-choice tests pass.
- Portable .NET contract tests, format verification and Windows ARM64/x64
  self-contained publishes pass. The complete contract runner also passes on
  the real Windows ARM64 appliance; this is distinct from cross-publishing
  and browser effects. The suite includes the native fixes and deterministic
  regressions for unpumped UI contexts and response bytes visible before
  task completion, private journal ACL preservation and closed stream
  diagnostics.
  A stalled-reader regression fails against the old private transport and
  passes with dedicated I/O, finite child termination and bounded disposal.
- Earlier Windows native composition acceptance passed with two fake browser
  peers, including five-minute retained-owner continuity. This exercises
  actual peer authentication, private child IPC and native admission without
  substituting another policy engine or requiring a browser.
- Node payloads built for all six targets during qualification; their policy
  source is unchanged in the final candidate. The packaged Mac ARM64 child passes five
  process checks and ten real-browser checks. Earlier Node/Bun Windows ARM64
  native and x64-emulated comparison suites pass; the final ARM64 Node payload
  also passes all five process checks natively.
  The final x64-emulated process run timed out and its exact scratch children
  were reaped; x64 publication is a build result, not current live acceptance.
- Actual Windows supervisor tests pass, including delayed startup versus the
  ordinary-call deadline and owned-job cleanup after a blocked write. Startup
  has a finite 30-second budget; ordinary operator calls retain five seconds.

### Appliance qualification and final result

**Current (2026-11-03), bounded `conformance-tested`:** a clean-source unsigned
Windows ARM64 candidate at `b80aa7cbf4c3282e16148323ff3aa5f2b50811d1`
passes all 39 real-browser and Tauri Settings checks in one run. Native runtime,
shared policy, extension, bundled Python client, actor and app identities are
bound to that source and verified bytes. The actual Windows native contract
runner also passes from that frozen source. The app embeds production assets;
a private generated version input does not constitute a version bump or release.

The dedicated appliance runs a separately identified native ARM64 Chromium
snapshot, with its sandbox enabled and software rendering. Two regular profiles
belong to one browser process and use one temporary native-host registration.
Independent HTTP/file effects verify trusted input, upload, capture and raw
operations. Page streams and profile-isolated browser-root creation, flattened
sessions, detach and close complete through the resident. Root and page
attachments are tested in separate phases because each profile reserves its
active attachment route.

The same run proves no implicit selector with two approvals, no cross-profile
references or offline failover, owner-disconnect closure, global Stop, real
60-second expiry without Settings, reconnect fencing, policy-child death and
fresh Off restart. Through real UI Automation, Settings grants exact profiles,
can be destroyed while browser effects continue, reopens to Stop the existing
authority, and restarts with remembered choices but no restored consent. Fresh
approval retains both exact profile choices.

The actor's finally cleanup passes. The outside controller separately verifies
restored native-host registration, reaped owned processes, removed tasks,
private scratch and sandbox-compatible test-browser staging, original Off
power state and released target claim. Canonical credential files remain ready,
nonempty and mode `0600`; their contents were not exposed or changed. Private
reports and usage notes retain exact target/evidence locators outside Git.

### Integration repairs and verification limits

Windows child startup retains the OS-owned `SystemRoot` needed by crypto while
clearing arbitrary inherited Node options. Native operator continuations do
not depend on an STA message pump. Admission releases provider occupancy before
response bytes are visible, while response tasks retain bounded tracking.
Native contract regressions cover those handoff boundaries.

Journal writes verify an already-correct protected DACL instead of repeatedly
propagating it across the state tree; an actual NTFS change-time regression
proves preservation and repair. Private pipe qualification then identified
async-over-sync write cancellation escaping the safety monitor. Dedicated
blocking read/write/stderr workers, one serialized outbound frame, the existing
three-second watchdog and exact-child termination repair that boundary.
Terminal policy-host loss leaves native monitoring available. The final
candidate
uses the original .NET 8.0.25 build baseline; a newer-runtime diagnostic was not
used as a substitute for the transport repair.

Chrome can finish creating a tab before its debugger target appears. The
extension creates once and waits for observation within the existing management
deadline, fencing connection replacement. Deterministic delayed/missing-target
and replacement cases pass; an earlier patched diagnostic also passed 20 root
lifecycle cycles. That diagnostic is distinct from the clean 39-check result.

Fixture corrections preserve the real oracle: modal opening is observed
without replaying an uncertain click; command waits follow the advertised
45-second deadline, while revocation separately requires actual closure within
five seconds. Silent open sockets fail that check. Headed profile selection is
needed for two regular profiles in one process. Browser binaries have sandbox
read/execute access while profiles and evidence remain private. The operator
uses isolated WebView storage and the production Tauri protocol feature.
Optional timed C-level Python stack walking reproduced a separate access
violation and is excluded from this actor; the normal Python client is unchanged.
See the [Windows harness guide](../../tests/windows/README.md).

This establishes the browser coordination cutover, not every Windows desktop
policy or every load/OS transition. Earlier owner-timeout observations did not
establish one universal cause. No signed installer, store delivery, publication,
physical/native x64, GPU or Mac/Linux adoption is inferred. The final x64-emulated
Node process timeout remains a limitation; x64 publication is a build result.

The [owning topic's adoption plan](../../topics/shared-resident-core.md#windows-cutover-and-next-adoption)
retains native Swift/Python platform effects and authentication, adapts this
same inlet, then deletes each platform's replaced browser policy after its own
native and packaged acceptance. macOS is next; a client rewrite is not required.

# Shared runtime decision and Windows browser adoption

Owning topics: [shared-resident-core](../../topics/shared-resident-core.md),
[browser-profiles](../../topics/browser-profiles.md).

Status: **Windows migration implemented; packaged candidate acceptance active**.

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
  packaging and nine extension indicator/worker tests. Desktop strict build
  and both real-built-frontend saved-choice tests pass.
- Portable .NET contract tests, format verification and Windows ARM64/x64
  self-contained publishes pass. The complete contract runner also passes on the real Windows ARM64
  appliance; this is distinct from cross-publishing and browser effects.
- All six final Node payloads build. The packaged Mac ARM64 child passes five
  process checks and ten real-browser checks. Earlier Node/Bun Windows ARM64
  native and x64-emulated comparison suites pass; final Windows candidate
  execution remains its own gate.

### Appliance qualification

**Current:** acceptance is active on an existing exclusively claimed Windows
ARM64 appliance. It uses a separately identified test Chromium, temporary
native-host registration and finally-style claim/process/power cleanup. The
actor exercises the production native peer authentication, inherited operator,
retained Python owner, two regular Chrome profiles in one process, independent
ordinary/page/root-CDP effects, Stop/expiry/reconnect/death and disposable real
Tauri Settings. No personal browser or installed product is replaced.

Integration work fixed the child environment: Windows cryptographic startup
requires the OS-owned `SystemRoot`, while arbitrary inherited Node options and
module paths remain cleared. Windows retained console channels now start both
pipe directions independently. Native safety facts are published only when
they change, preserving the child policy's idle Off state. Portable tests use
the same shared child rather than retaining the deleted C# bridge as a test
surrogate.

The initial headless browser singleton did not open a second regular-profile
window; the simultaneous-profile actor therefore runs headed. A marked
ordinary fixture tab identifies the requested Chrome profile before navigating
to its extension setup UI. The runner's browser-startup budget is separate
from the product's action deadlines. Private usage notes and reports retain
concrete friction and target locators.

**Unfulfilled:** passing the final real two-profile ordinary/CDP and Tauri
Settings lifecycle run and verified appliance cleanup. No signed installer, publication, physical/native x64 or
Mac/Linux adoption is inferred. The source implementation is committed while
these execution gates remain active.

The [owning topic's adoption plan](../../topics/shared-resident-core.md#windows-cutover-and-next-adoption)
retains native Swift/Python platform effects and authentication, adapts this
same inlet, then deletes each platform's replaced browser policy only after
its own native and packaged acceptance. A client rewrite is not required.

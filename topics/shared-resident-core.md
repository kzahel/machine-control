# Shared resident policy and fast reference verification

Topic: `shared-resident-core`

Status: **Windows adapter implemented; packaged candidate qualification active**.

## Motivation

**Current:** two Chrome profiles with the extension can contend for the
resident's singleton browser connection. The [provider dossier](../research/providers/chrome-extension.md#multiple-profile-limit)
owns the source findings and their live-evidence limits. Multi-profile work
exposes a wider maintenance problem: grants, provider routing, deadlines,
revocation and generation fencing are separately implemented in the Swift Mac,
C# Windows and Python Linux residents. Mac/Windows owner admission and CDP
bridges also have separate implementations; Linux does not have identical
feature coverage. These are overlapping policy implementations, not three
equivalent translations of one enforced model.

The product already shares its Python client, TypeScript settings UI,
JavaScript Chrome extension, common result vocabulary and some conformance
runners. Native peer authentication, accessibility, capture, input, console
observation and protected operations need platform implementations. Portable
policy is currently intertwined with those native responsibilities.

The user requested using browser profiles to refactor this middle layer,
with lightweight, fast verification rather than repeatedly assembling a
desktop package or bringing up three OS appliances. The original language
question compared iteration-friendly TS/Python with Rust's native deployment.
The first deliverable makes that architecture concrete without claiming
an all-platform migration or production browser-profile support.

## Terms and current scope

**Decision:** use these names for this workstream:

- **Shared resident core:** the reusable target-side policy implementation for
  approval, profile selection, routing, deadlines, revocation and request/session
  lifetime. Native authentication, OS observations and platform effects remain
  behind its adapter boundary.
- **Reference target:** the test-only composition of that same core with
  stateful **reference providers**, controlled time and independent effect
  checks. Its current implementation is a small deterministic fixture, expanded
  capability by capability alongside Windows adoption.
- **Windows adapter:** the native integration supplying authenticated ingress,
  OS safety observations and real provider effects to the shared core.

**Decision:** focus implementation on the shared resident core, Windows adapter
and reference target together, beginning with the complete browser-control
vertical slice. The reference providers simulate effects and observations;
both targets execute the same policy implementation.

Keep the existing Python CLI and client implementation. A client rewrite,
TypeScript session SDK and client-language cutover are outside this workstream.
Preserve the public client experience, making only compatible interface changes
required for browser profiles. Client consolidation remains a separate possible
future concern, not a prerequisite for resident adoption.

## Direction and ownership

**Decision:** build one reusable resident policy implementation with typed
provider boundaries, exercised against a stateful reference provider. The
reference provider substitutes platform effects; it must not contain another
grant/routing/revocation engine. Keep the shared core independent of Tauri,
the WebView, agent-written code, native OS APIs and browser automation tools.
Windows remains the first native adoption vertical slice. Preserve existing
providers, signed identities and protected watchdogs during migration.

**Current:** strict, erasable TypeScript under `runtime/` implements the
shared browser coordinator. Pure policy has no runtime dependencies; the
production Node transport uses pinned `ws`. Strict checking remains a separate
build gate. The language/deployment decision below supersedes the original
prototype-only placement. The Python client remains unchanged in language.

## Language and deployment decision

**Decision:** retain TypeScript for shared policy and deploy it as a private
child with a bundled, pinned Node LTS runtime. No system Node, npm, interpreter
discovery or agent-side runtime installation is required. The native resident
owns the child independently of Settings. Keep the policy free of Node/Bun
APIs; the inherited process host is a replaceable adapter around that source.
The current runtime pin is Node 24.22.2, with exact upstream archive hashes
and upstream notices retained in the payload. This settles the implementation
direction; installed identity and full Windows adoption remain acceptance
gates, not facts implied by the choice.

**Current:** both pinned Node and Bun 1.4.4 payloads build for all six desktop
targets. Header inspection verifies OS/architecture, not executable correctness.
On Mac ARM64, both packaged children pass four process checks and ten real
browser checks, including EOF, hard kill, expiry, stale references, native-port
cleanup and fresh Off restart. The unchanged extension produces independently
observed trusted-click effects through either process host.

**Current, bounded Windows process evidence:** Node and Bun payloads pass the
four-check process suite on an exclusively claimed Windows ARM64 appliance:
ARM64 natively and x64 under emulation. This qualifies inherited pipe framing,
EOF/kill cleanup, scheduled expiry and fresh Off state, not native x64
hardware, production browser-peer authentication or an installed desktop app.
Scratch staging/processes are removed, Off restored and claims released.

**Current, local eight-sample measurements:** median empty-host startup is
about 62 ms for Node and 12 ms for Bun. Self-reported idle RSS is approximately
91 MB and 8 MB respectively; these are runtime reports, not an independent OS
memory census or a workload benchmark. Both idle Off without periodic wakeups.
The uncompressed Node payload is 82 MB on Windows ARM64 and 94 MB on x64,
versus Bun's 100 MB and 115 MB; Mac/Linux Node payloads are 123–127 MB versus
Bun's 89–109 MB. Artifact size and RAM are separate costs.

**Decision:** accept Node's measured footprint for a known LTS maintenance
boundary and unchanged, hash-pinned upstream runtime distribution. Bun is a
working alternative with better startup/RSS in this fixture, not a failed
experiment. It introduces another runtime compatibility and redistribution
qualification obligation; its [license record](https://github.com/oven-sh/bun/blob/bun-v1.4.4/LICENSE.md)
includes MIT for Bun itself and narrower terms for linked dependencies,
including LGPL JavaScriptCore. This is not a claim that Bun cannot be shipped.
The [Node release policy](https://nodejs.org/en/about/previous-releases) provides
the chosen patch/support lifecycle. Pin upgrades must rerun process, browser,
native and package acceptance; runtime maintenance is now a product duty.

**Decision:** do not write a competing Rust core. There is no demonstrated
deployment blocker requiring it; native-library embedding does not outweigh
reimplementing the already exercised policy. Rust remains appropriate for the
existing Tauri/native boundary. Python remains the agent-facing client and
platform tooling; no Python policy prototype was built, so there is no measured
Python performance claim. The decision can be revisited for a concrete failure,
not through parallel policy engines or another open-ended language comparison.

## Native adoption boundary

**Decision for adoption:** one shared authority owns browser policy. The
following split is implemented in Windows source; native/package execution
is qualified separately. Mac and Linux have not adopted it.

| Responsibility | Owner after adoption |
| --- | --- |
| Native operator and browser-peer authentication | Existing native resident |
| OS console/session observations, protected provider and emergency transport shutdown | Native adapters/watchdogs |
| Exact profile approval, scope, lifetime, withdrawal and generation | Shared core |
| Profile selection, request admission to browser routes, deadline, terminal result and late-reply fencing | Shared core |
| Browser endpoint tokens, profile-bound stream ownership/reservations and revocation | Shared policy, over bounded transport adapters |
| Native caller identity and existing desktop control-owner admission | Native ingress, passed as a fenced capability input |
| Settings, extension panel and native notices | Projections and trusted operator decisions; never replacement authorities |

Native ingress can deny an unsafe operation or close a route independently;
it cannot mint, renew or restore browser approval. Remove the browser grant
checks being replaced from native `DesktopGrants`/relay policy rather than
renewing the same browser permission separately in two processes. Existing
desktop grants and protected watchdogs remain native until their own migration.
Mixed desktop/browser approval needs explicit composition and rollback; do
not silently interpret an old consent record as an exact profile set.

The [private host inlet](../runtime/PROTOCOL.md) now includes profile-aware
identity, the complete ordinary operation vocabulary, DevTools endpoints and
streams, indefinite operator consent and native safety/owner checks. Reference
providers exercise those policies with independent stateful effects. Dead
transport retirement releases correlation capacity without changing unknown
application effects. Windows source integrates this boundary and removes its replaced policy;
packaged candidate acceptance is recorded in Tactical 152. Mac and Linux adopt this proven
boundary after the complete Windows candidate, without porting another policy
engine into Swift or Python.

The module is the Windows browser policy implementation and the reference
target uses the same owner. This is not an all-platform cutover. Authority
methods are internal trusted-host calls, not agent operations or a public
JSON protocol. A future host must authenticate provider peers and operator
decisions before creating handles. Public profile names and generations are
selectors/diagnostics, never authority. This adds no security boundary against
a same-user agent with unrestricted shell access.

## First acceptance slice

**Decision:** model two provider connections, exact-profile finite approval,
one typed `browser.click`, request deadlines, Stop, connection replacement and
late completion. Use runtime-local object handles for connections, approval
and dispatch correlation so copied public IDs cannot supply authority. Freeze
input snapshots crossing the boundary. Keep queued work separate from work
that has crossed the provider dispatch boundary.

Stop removes approval before emitting cleanup. Queued work terminates as
refused before dispatch; already-dispatched work has unknown delivery/effect.
Cancellation does not establish that an application effect was undone. Late
replies cannot produce a second terminal result or restore approval. A new
connection never replaces another profile, and a disconnected selected
profile is never substituted with another connected one. Reapproval and
reconnect cannot make old connection/reference/dispatch handles current.

The reference provider owns a small independent counter model and held
completions. It can perform an effect before withholding its response; tests
inspect that model separately from the core result. The clock is explicit and
monotonic, with no sleeps, desktop, display server, browser or network needed.
Bound connected providers and retained requests; the host consumes returned
effects rather than allowing a growing internal event log.

Do not include full owner admission, approval UI, persistent consent,
snapshot/reference discovery, script evaluation, CDP, screenshots, synthetic
desktop rendering or real browser attachment in this first deliverable.
The test target string is provider-owned fixture state, not a newly promised
cross-platform element-reference format. The existing result vocabulary still
separates delivery and independently observed effect.

## Verification progression

**Decision:** use three complementary levels:

1. Deterministic core scenarios and provider-contract tests on the developer's
   OS, with a controlled clock and adversarial event ordering.
2. The same core with real extension/native-messaging/browser integration,
   initially a separately identified headless Chromium or Chrome for Testing.
   Add a virtual display only for behavior that needs it. A browser fixture
   does not require the GNOME-specific production desktop provider.
3. Native Windows, Mac and Linux acceptance for their real transport identity,
   OS permissions, accessibility, focus, session transitions and packages.

Survey existing implementations to extract intended invariants and explicitly
different capabilities. Do not turn every historical behavior into a common
requirement, emulate entire OSes or infer native correctness from the fake.
Any future simulated screen is a narrow provider fixture, not a fourth policy
implementation or a replacement OS.

## Windows cutover and next adoption

**Current implementation:** `BrowserRelay` is an authenticated concurrent
pipe and native-effect adapter. The old singleton routing, native wire request
correlation and generation/reference rewriting are replaced by the shared
host. `BrowserDevToolsBridge.cs` is deleted: native HTTP/WebSocket endpoint
ownership, tokens, per-tab reservations, CDP command correlation and stream
revocation are no longer a competing Windows policy implementation.
`DesktopGrants` delegates Browser/DevTools scope checks and consent to the
shared projection; temporary browser consent uses the opaque checkpoint below.
It retains generic desktop grants, caller admission and OS safety observations.
`SharedBrowserHost` owns one pinned Node child and fails closed on child loss.
Native code retains payload-free audit persistence and validated artifact/file
operations. Settings is a disposable operator projection.

The reference target models the ordinary browser vocabulary, stateful tabs,
input, upload, capture and raw-operation observations behind this same policy.
Its effects are independent of the policy's reported delivery. It does not
simulate an entire desktop or qualify native authentication, OS permissions,
foreground behavior or protected control.

**Decision:** migrate macOS next with this exact private inlet. Retain Swift
peer authentication, AX/capture/input and protected/session facilities. Replace
its singleton browser relay and CDP policy with per-connection transport into
one shared host. Translate trusted operator decisions and console/owner facts;
do not port the registry or expiry engine into Swift. Preserve exact-profile
consent and remaining lifetime across its existing same-console restoration,
requiring fresh consent for old records lacking IDs. Qualify two regular
profiles, independent ordinary/root/page CDP effects, owner/Stop/session loss,
Settings recreation and exact packaged ARM64/x64 identity on Mac before deleting
its replaced path or advertising support there.

**Decision:** adopt Linux after the Mac boundary is proven. Retain Python for
AT-SPI, compositor/capture/input, native peer credentials and target lifecycle;
replace browser coordination with the same child adapter. Linux currently lacks
the complete Mac/Windows streaming surface: capability omissions remain honest
until qualified. Prove production Unix peer/owner authentication, GNOME Wayland
session/lock transitions, exact profile consent, browser effects and packaged
cleanup on its own target. Neither platform needs a CLI rewrite or another
shared-policy implementation.

[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md) owns
Windows execution, evidence limits and final status. The
[browser-profiles topic](browser-profiles.md) owns the product contract and
remaining cross-platform rollout. Pinned runtime updates must repeat portable,
real-browser, native and package acceptance; no publication or installation
replacement is implicit in this workstream.

## Original consent during temporary grants

**Decision, implemented in the shared core:** when Windows temporarily replaces
person-enabled access, native code retains an opaque checkpoint rather than
reconstructing browser consent from its own scopes and a new duration. The core
keeps the original expiry, profile selection, DevTools scope and profile
withdrawal revisions. Restoration issues fresh fences, consumes the checkpoint
once, excludes profiles withdrawn since capture, and cannot extend the original
lifetime. Re-enabling a profile cannot undo its withdrawal. Global Stop and
process death invalidate all saved consent. A temporary grant with no browser
scope suspends browser access without turning it into a fresh approval.

Native code still decides when its generic temporary grant ends and retains
native console/session safety as a denial ceiling. Browser authority and the
restoration decision's browser-specific rules remain in one shared owner.

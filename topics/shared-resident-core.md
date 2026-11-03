# Shared resident policy and fast reference verification

Topic: `shared-resident-core`

Status: **language/deployment chosen; Windows adoption active; no installed integration**.

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

**Initial slice:** use strict, erasable TypeScript under
`runtime/`, runnable with Node 24+ without a build or runtime dependencies.
Its pinned compiler is a development dependency only. This evaluates the
coordinator policy and development loop; it does not commit installed
packages to Node/Bun, claim packaging qualification or require replacing the
Python agent interface. Native-library embedding remains a Rust advantage;
runtime deployment and library/process placement need their own evidence.

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
following is the required ownership split, not the installed state today.

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

The [private host inlet](../runtime/PROTOCOL.md) is implemented for three typed
operations and finite fixture approvals. Production adoption still needs
profile-aware identity, all ordinary operations and DevTools streams,
indefinite operator lifetimes, native admission fences and a bounded
quiescence/reclamation policy for lost dispatched work. The installed Windows
grant/relay code has not yet been replaced. Mac and Linux adopt this proven
boundary after the complete Windows candidate, without porting another policy
engine into Swift or Python.

The module is intended to become the shared policy implementation, not a
throwaway mock of one. It currently has no installed consumers. Authority
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

## Next evidence

**Decision:** the next milestone migrates a complete Windows browser path
through the chosen TypeScript/Node boundary, with packaged acceptance.
[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md) owns its
gates. The executable comparison above settles language and placement;
no Rust comparison is warranted by current evidence.
The milestone must account for deleted native policy, retain ordinary/CDP
behavior, and prove settings independence and failure cleanup. Another fixture
alone does not complete it. Publication and personal installation replacement
are outside its scope.

**Current, bounded Mac ARM64 live evidence:** the same core now handles typed
tab discovery, snapshots and clicks through the unchanged extension and real
native messaging. Two independent headless test-browser profiles now pass ten
checks in approximately five seconds, with independent trusted-click HTTP
effects, Stop in both extension panels, a held old reply and genuine native
relay loss/reconnect, scheduled expiry and policy-process death/restart.
Fixture endpoints assign identity and fixture operator
calls approve exact profiles; production native authentication, same-process
Chrome profiles, browser sandbox and installed acceptance are not qualified.
[Tactical 151](../docs/tactical/151-shared-core-real-browser.md) owns execution
and [the provider dossier](../research/providers/chrome-extension.md#multiple-profile-limit)
owns route evidence. This consumes the existing worker protocol without a
new extension release or change to the installed residents.

**Current:** the TypeScript core, stateful provider, explicit-clock scenario
and 28 focused regressions pass locally with strict TypeScript checking.
The deterministic 24-test subset reports roughly 0.1 seconds; process checks
add approximately 1.3 seconds on the development Mac. These are local
observations, not cross-platform benchmarks. CI is wired
to run the same core tests and type check on all three desktop host families;
remote CI execution and native/package acceptance are not inferred. A separate
Linux CI job is wired for real-browser acceptance using the packaged child.
Coordinator CI builds all six Node payloads on Linux and executes native
payloads on all three host families. Remote execution is not inferred from
this configuration or local Mac evidence.

[Tactical 150](../docs/tactical/150-shared-resident-core.md) owns the reference
slice and [Tactical 151](../docs/tactical/151-shared-core-real-browser.md) owns
the real-browser follow-up. Both hosts now use one dispatch helper, preserving
the same fresh-authority check, remaining budget and submission ordering.

**Decision:** next remove fixture-assigned identity: add persistent extension
installation identity and prove two profiles in one Chrome process through a
single native-host registration. Then qualify production native peer/operator
authentication and packaged deployment through this same core. Remove policy
being replaced from each native resident, one qualified vertical slice at a
time. Shipping a new layer while retaining competing native policy engines
does not complete the refactor.

[Browser profiles](browser-profiles.md) owns the proposed product contract;
its full implementation plan depends on this workstream and must not proceed
by independently rewriting all three native policy engines.

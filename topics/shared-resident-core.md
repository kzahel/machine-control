# Shared resident policy and fast reference verification

Topic: `shared-resident-core`

Status: **first deterministic slice complete; no installed integration**.

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
desktop package or bringing up three OS appliances. Language preference is
still open between iteration-friendly TS/Python and Rust's native deployment.
The first deliverable must make that architecture concrete without claiming
an all-platform migration or production browser-profile support.

## Direction and ownership

**Decision:** build one reusable resident policy implementation with typed
provider boundaries, exercised against a stateful reference provider. The
reference provider substitutes platform effects; it must not contain another
grant/routing/revocation engine. Keep the shared core independent of Tauri,
the WebView, agent-written code, native OS APIs and browser automation tools.
Windows remains the first native adoption vertical slice. Preserve existing
providers, signed identities and protected watchdogs during migration.

**Decision for the first slice:** use strict, erasable TypeScript under
`runtime/`, runnable with Node 24+ without a build or runtime dependencies.
Its pinned compiler is a development dependency only. This evaluates the
coordinator policy and development loop; it does not commit installed
packages to Node/Bun, claim packaging qualification or require replacing the
Python agent interface. Native-library embedding remains a Rust advantage;
runtime deployment and library/process placement need their own evidence.

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

**Current:** the TypeScript core, stateful provider, explicit-clock scenario
and 17 focused regressions pass locally under Node 24 and Node 26, with strict
TypeScript checking. The suite reports roughly 0.1 seconds on the development
Mac; this is a local observation, not a cross-platform benchmark. CI is wired
to run the same core tests and type check on all three desktop host families;
remote CI execution and native/package/browser acceptance are not inferred.

[Tactical 150](../docs/tactical/150-shared-resident-core.md) owns this first
slice, its executable scenario, verification and result. Before native rollout,
prove real native messaging, extension debugger behavior, two-profile effects,
process loss and packaging through this same core. Then remove the policy
being replaced from each native resident, one qualified vertical slice at a
time. Shipping a new layer while retaining competing native policy engines
does not complete the refactor.

[Browser profiles](browser-profiles.md) owns the proposed product contract;
its full implementation plan depends on this workstream and must not proceed
by independently rewriting all three native policy engines.

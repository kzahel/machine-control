# Prove shared resident policy with a reference provider

Owning topics: [shared resident core](../../topics/shared-resident-core.md),
[browser profiles](../../topics/browser-profiles.md).

Status: **first deterministic slice complete; native/browser integration pending**.

## Objective and completion conditions

The user requested recording the workstream's motivation durably, then
implementing the first lightweight deliverable, committing it and recommending
the next step. Prove two provider connections, exact approval, an action,
Stop and a late result using the actual proposed shared core and a stateful
reference provider. Produce a fast executable scenario and focused regressions
without a desktop VM, framebuffer, browser or installed-app change.

Complete when the core owns routing/authority, the reference provider owns
only fixture effects, the independent model demonstrates no cross-profile
dispatch, and queued/dispatched revocation plus late completion are truthful.
Wire verification into repository checks and record actual qualification.

## Boundaries

TypeScript is the first-slice implementation choice, not a settled six-target
deployment decision. No native resident replacement, public operator/agent
approval API, new privileged surface, real extension attachment, release or
VM provisioning. No full synthetic desktop or general provider dispatch.
Use only typed browser clicks and bounded state. Preserve other working-tree
changes outside this workstream.

## Ordered work

### 1 — record the reason and shared boundary

Write the owning topic before runtime implementation. Record the browser
singleton trigger, duplicated policy versus legitimate OS differences,
language/process uncertainty, fast-reference approach and migration limits.
Link the topic from architecture, system ownership and browser-profile plans.

### 2 — implement the reusable coordinator

Add strict, erasable TypeScript with no runtime dependencies. Define typed
provider connection, approval, request, dispatch and completion boundaries.
Use exact handles, an injected monotonic clock, bounded state, explicit
dispatch acceptance and terminal-result effects. Stop/replacement/expiry and
disconnect must fence queued and dispatched work before handling late results.

### 3 — prove independent fixture effects

Add a counter-backed provider with explicit held replies and a manual clock.
Run the motivating scenario and adversarial variants through the same core.
Inspect provider counters/received commands separately from accepted results.
Verify that public-ID copies, stale handles and foreign-provider replies
cannot retarget work or complete someone else's pending request.

### 4 — validate and commit

Run strict type checking, deterministic tests, the executable scenario and
repository portable checks. Integrate Node 24 execution/type checking into
cross-platform CI. Review staged changes for private deployment data and
unrelated edits. Commit the source, workstream/scoping documents and checks;
report the next bounded real-browser integration step and remaining limits.

## Validation and final result

The motivation and ownership topic was written before implementation. The
first module is strict TypeScript with no runtime dependencies; it runs under
Node without a compiler/build step, Tauri, native UI or browser. Its only
development dependency is the pinned compiler already used by the desktop.

The executable scenario connects fictional Work and Personal providers,
approves Work only, independently observes one Work counter increment before
holding the reply, then Stops. Cancellation leaves that effect intact and the
terminal result reports unknown delivery/effect. Personal reconnects and gets
fresh approval; the old Work reply cannot complete its new request, even with
the same public request label, or restore Work's authority. A fresh Personal
reply confirms delivery while the core continues to report effect as
unverifiable; the independent fixture counter proves the effect separately.

All 17 focused tests pass with strict TypeScript 5.9.3 checking. They cover
independent providers, queued versus dispatched Stop, immutable snapshots,
copied/foreign/runtime-old handles, cross-profile references, duplicate live
identity, no failover, disconnect/reconnect, reapproval, exact expiry/deadlines,
bounded capacity, provider failures and malformed/invalid-clock input.
Unsettled dispatches retain physical-call capacity across Stop and reapproval
until the exact completion arrives; cancellation alone cannot recycle slots.

Tests and the scenario pass under Node 26.7.0 and a temporary official Node
24.22.2 ARM64 binary verified against its published archive checksum. The
temporary binary is removed. The local suite reports approximately 0.1 seconds;
it contains no sleeps or OS/provider I/O. CI installs Node 24 and the pinned
compiler on Mac, Windows and Linux; the common portable runner invokes the
reference suite. Remote CI execution is not claimed.

Repository portable checks pass, including the shared reference suite and
existing browser lifecycle checks; that full local run took 252 seconds.
Strict checking, frozen dependency installation, whitespace, new JSON and
319 local documentation links also pass. The scoped source review preserves
the two unrelated pre-existing documentation edits outside this workstream.
No existing native runtime, installed extension, target,
credential, package or release was operated or replaced. The next bounded
step is a real native-messaging/extension adapter consuming this same core,
with independent two-profile browser effects and transport-loss checks.

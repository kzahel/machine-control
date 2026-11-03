# Shared runtime decision and Windows browser adoption

Owning topics: [shared-resident-core](../../topics/shared-resident-core.md),
[browser-profiles](../../topics/browser-profiles.md).

Status: **language/deployment decision complete; Windows migration pending**.

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

## Execution

**Current:** prior slices are committed in `bcef146` and `8fe60b9`. The core
has no installed consumer. Windows source review confirms native grant,
provider generation and singleton relay ownership are currently intertwined.
The language/deployment decision is TypeScript with a privately bundled Node
LTS child; the owning topic records reasons and rejected alternatives. Both
Node 24.22.2 and Bun 1.4.4 build for all six targets, with binary-header
verification and source/file manifests. Mac ARM64 packaged execution passes
four process tests and ten real-browser checks under both hosts. Linux
execution and native x64 execution are not inferred from cross-built payloads.

The executable uses inherited framed pipes, fresh process epochs, bounded
correlation and exact reference fences. A native parent must close browser
transports after child death; the fixture now proves that obligation against
real ports and panels. Deadline-driven scheduling eliminates periodic wakes
while Off. The former in-process fixture composition is replaced, rather than
retained as another policy host. Portable checks and strict checking pass.

Windows process qualification uses an existing exclusively claimed appliance,
authenticated administration, scratch payloads and finally-style shutdown and
claim release. A locked desktop initially made generic readiness fail even
though administration was ready; process-only qualification correctly needs
the latter. An emulated x64 expiry test exposed an unrealistic 120 ms IPC
assumption, safely refusing before dispatch. The integration budget was repaired;
deterministic tests retain exact-boundary coverage. No password was changed,
no desktop/browser installation was replaced, and no outer UI route was used.

**Current:** all four Windows payloads, Node and Bun on both architectures,
pass the four-check process suite: ARM64 natively and x64 under emulation on
the same ARM64 appliance. Minimized private reports retain the distinction.
A Bun Windows test also exposed an invalid
same-read assumption between terminal results and grant projections; the test
now independently waits for framed revocation and drains streams through close.
This does not change the core's ordering or grant semantics.

## Validation and checkpoint result

Strict TypeScript checking, 28 focused checks, the complete portable check
runner, workflow YAML parsing, local documentation links and whitespace checks
pass. Both packaged Mac ARM64 hosts pass the ten real-browser checks and the
process suite. All twelve payload source manifests match the current owned
policy source. Windows reports confirm four passing payloads and successful
staging/process/power/claim cleanup. CI configuration adds six-target builds
and native packaged execution on the three desktop host families; remote CI
has not been run in this task.

**Result:** language and deployment checkpoint complete: TypeScript and a
privately bundled Node LTS child. The complete Windows browser migration is
still active and unfulfilled as listed above. No release, push or personal
installation change occurred.

**Unfulfilled:** production profile identity, full ordinary/DevTools operation
coverage, native browser-policy replacement, signed/installed Windows candidate
and Settings lifecycle acceptance. No installed Windows policy has been deleted
yet. Those remain completion gates for this tactical; executable qualification
does not mark the complete milestone done.

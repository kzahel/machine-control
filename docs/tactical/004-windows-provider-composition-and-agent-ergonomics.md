# Tactical 004: Windows Provider Composition and Agent Ergonomics

Status: complete; started and completed 2026-08-09.

Topics: `windows-resident-control`, `architecture`,
`capabilities-and-results`, and `provider-landscape`.

Parent tactical:
[`002-windows-full-target-native-control.md`](002-windows-full-target-native-control.md).

## Objective

Turn the proven Windows resident-control mechanisms into a coherent tool an
agent can use for a complete application-testing workflow. Connect the pinned,
unmodified Cua ordinary-desktop provider behind the owned facade, retain the
deep native Windows provider for system-shell, protected, lifecycle, and
measured gap operations, and select a provider per operation with truthful
route and effect reporting.

Prove that an authorized outside agent and an agent running inside Windows can
use the same conceptual operations to prepare, launch, navigate, verify, and
clean up a realistic application test without viewing, focusing, or sending
input through a VM console, hypervisor window, remote-desktop viewport, or
hardware KVM.

## Completion conditions

- The owned facade remains the stable contract. Callers do not import a Cua,
  WinApp, or native-provider-specific vocabulary to complete the workflow.
- The exact Cua revision already evaluated in `machine-control-spike` is
  connected as a replaceable ordinary-session adapter without forking it or
  copying its implementation into this repository.
- The native Windows adapter remains authoritative for operations where live
  evidence shows greater reach or fidelity, including system-shell and
  protected-session surfaces. It is not demoted merely to make one library
  appear universal.
- WinApp is exercised as a differential provider on selected fixture and
  system-shell cases. It is adopted behind the facade only for an operation
  where measured evidence shows a useful advantage over both Cua and the owned
  native route.
- The arbiter selects a provider per operation from current capabilities and
  target/session state. Every result reports provider attempts, actual route,
  fidelity, delivery, independently observed effect, uncertainty, and known
  focus/cursor consequences.
- A deterministic fixture workflow and at least one representative real
  Windows workflow pass through the same facade. Together they cover semantic
  observation/action, exact capture, keyboard/pointer fallback, window state,
  transient UI, a system surface, and an elevated or protected transition.
- The representative workflow succeeds from both an authenticated outside
  carrier and a target-local Medium process. Differences are limited to target
  selection, transport, latency, and explicitly disclosed capabilities.
- No ordinary passing case focuses or manipulates an outer VM/KVM or
  remote-view window. Outer observation may be used only as a separately
  authorized independent oracle and must not deliver test input.
- Bounded observations report serialized bytes, estimated tokens, provider
  latency, end-to-end latency, agent round trips, retries, and stale-reference
  events. The result is compared with the existing ChromeOS ergonomic
  reference without requiring identical platform internals.
- Provider absence, crash, timeout, stale identity, unsupported operation,
  ambiguous delivery, and disagreement produce structured results. A fallback
  occurs only when the contract authorizes it and the result discloses it.
- Deterministic fixture or OS effects remain the correctness oracle. Agreement
  among Cua, native UIA/Win32, and WinApp is differential evidence, not proof.
- Windows x64 and ARM64 builds pass. The adopted composition is reproducibly
  installable on a clean test appliance without embedding private inventory,
  credentials, or machine-specific configuration.
- The evidence either closes Tactical 002's live provider-composition gap or
  records a precise remaining condition. A Cua fork or broader owned rewrite
  is proposed only if repeated evidence meets the architecture's replacement
  gate.

## Architecture under test

```text
target-local caller ---------------- local pipe --------+
                                                        |
outside caller ---------------- authenticated carrier --+-- owned facade
                                                               |
                                                      operation arbiter
                                                        /      |       \
                                                       /       |        \
                                             Cua ordinary   Windows    WinApp
                                               adapter       native   differential
                                                            adapter     adapter
                                                               |
                                                ordinary + protected
                                                  session boundary
                                                               |
                                                     fixture / Windows
                                                     effect oracle
```

Cua, native Windows APIs, and WinApp are replaceable providers. The facade,
session/protected boundary, capability/result vocabulary, routing policy, and
conformance corpus are project-owned.

## Boundaries

- Do not repeat the completed broad Cua survey. Reuse its pinned source and
  existing evidence, then investigate only integration facts or newly exposed
  gaps needed by this tactical.
- Do not fork Cua, start an all-platform rewrite, or require one provider to
  handle every Windows operation for architectural neatness.
- Do not adopt WinApp merely because the provisional architecture mentioned
  it. Differential value must be demonstrated for a concrete operation.
- Do not change the already proven UAC, secure-desktop, PIN/password, lockout,
  or sign-in policy to simplify provider integration.
- Do not place secrets in the ordinary contract or rerun credential cases
  unless a change actually crosses their guarded path and the human explicitly
  supervises the one-submission test.
- Do not count a provider acknowledgement, input delivery, matching provider
  output, or changed screenshot alone as an application effect.
- Do not silently turn a semantic failure into coordinate input. Refresh
  observation, require the operation's authorized fallback, and report the
  resulting fidelity and interference consequences.
- Do not make MCP, SSH, a local pipe, or a CLI syntax the contract or security
  boundary. This tactical may improve those facades, but the normalized
  operation/result model remains transport-independent.
- Do not expand implementation to macOS or Linux in this tactical. Preserve
  cross-platform adapter seams only where the Windows evidence exercises them.
- Do not absorb testbed lifecycle/bootstrap/recovery or YepAnywhere session
  coordination into this repository.

## Implementation steps

### 1 — freeze workflows and native baseline

Choose one deterministic fixture workflow and one representative real Windows
workflow before changing routing. Record required operations, expected OS or
fixture effects, allowed fallbacks, compact observation bounds, and current
native-provider measurements. Link the existing Cua spike evidence instead of
copying its logs.

### 2 — make provider capabilities executable

Replace descriptive provider inventory with machine-readable availability,
operation, session, desktop, privilege, semantic-fidelity, capture, and input
capabilities. Distinguish unavailable, unsupported, temporarily unhealthy,
policy-refused, and not-yet-integrated states.

### 3 — connect pinned Cua as an adapter

Package and supervise the evaluated Cua revision in the ordinary interactive
session. Translate owned window/element identities and normalized operations
at the adapter boundary. Preserve upstream route/effect information while
preventing provider-specific objects from leaking into the public contract.

### 4 — define evidence-driven routing

Encode an explicit initial routing table from the completed Windows shell and
Cua evidence. Prefer Cua for operations where it meets the contract and the
native adapter for measured shell, capture, lifecycle, elevated, or protected
gaps. Specify whether each failure is terminal, retryable on the same provider,
or eligible for a named fallback.

### 5 — run the WinApp differential lane

Exercise WinApp against selected deterministic fixture, taskbar, Settings,
packaged-window, and exact-capture cases. Record its payload, latency, semantic
reach, identity stability, and effect observability. Add an adapter only for a
demonstrated useful route; otherwise retain it as conformance evidence.

### 6 — complete the agent-facing workflow

Drive preparation through the authorized administration carrier and all UI
work through the resident facade. From outside Windows, install or stage the
test subject, launch it, navigate semantic and transient surfaces, exercise a
system interaction, cross one protected boundary, verify application/OS
effects, and clean up. Repeat representative operations from a target-local
Medium caller without changing their meaning.

### 7 — measure semantic and transport ergonomics

Capture bounded per-operation and end-to-end measurements: returned elements,
serialized bytes, estimated tokens, provider and transport latency, agent
round trips, retries, fallbacks, reference refreshes, and foreground/cursor
impact. Compare the workflow shape with ChromeOS and identify avoidable agent
friction rather than forcing numerical parity.

### 8 — prove failure and recovery behavior

Withhold or stop each optional provider, invalidate references, force bounded
timeouts, and exercise an unsupported route. Verify deterministic refusal or
authorized fallback, helper/provider restart, generation changes, and honest
unknown-effect handling. Never use outer input to turn a failure into a pass.

### 9 — package, document, and decide

Publish Windows x64 and ARM64, install the chosen composition through the
authoritative testbed, rerun representative ordinary and protected regression
cases, and remove temporary provider state. Update the provider dossiers,
Windows platform report, architecture/results topics, this tactical, and
Tactical 002 with measured adoption or rejection decisions and remaining
gaps.

## Validation plan

Use deterministic fixture state and authoritative Windows state as independent
oracles. Retain raw provider traces and machine-specific output only in the
target-local evidence location or the research spike; commit minimized,
redacted measurements here.

At minimum, record a matrix with:

- operation and expected effect;
- selected and attempted providers;
- local versus remote placement;
- semantic, visual, input, and protected route;
- delivery and independently observed effect;
- payload bytes, estimated tokens, latency, and round trips;
- fallback or retry behavior; and
- final cleanup state.

## Validation record

Execution started on 2026-08-09.

### Frozen workflows and baseline

**Decision:** The deterministic workflow uses the checked-in Medium fixture:
launch it without an outer UI route, identify its exact HWND, take a bounded
semantic snapshot, invoke its increment control through a snapshot-scoped
reference, independently observe `counter=0` becoming `counter=1`, capture the
exact window, exercise minimize/maximize/restore, reject a stale reference,
close the fixture, and prove its process/window effect disappeared. Semantic
snapshot and invocation prefer Cua; exact capture may fall back to the native
provider when Cua cannot register the HWND; native Win32 owns window state.

**Decision:** The representative Windows workflow is the existing shell
conformance path: Start/Search, Quick Settings, notification overflow,
Settings, File Explorer, desktop transient menu, fixture lifecycle, exact
capture, application switching, revocation, and helper recreation. It adds one
UAC approve/cancel transition through the already proven protected broker.
The protected regression is reused and is not a reason to rerun credential
submission. All ordinary Default-desktop operations must remain in the Medium
interactive helper, including `scope=system` shell operations.

**Pre-integration baseline:** The owned native provider supplied the complete
passing route. It reported bounded element count, visited nodes, serialized
bytes, estimated tokens, end-to-end latency, generation, route, delivery,
effect, focus, cursor, and exact-capture artifact metadata. Cua was pinned at
0.17.0 and source review revision
`d21e3447f9b08c761c090946648d5aca5e6c9cf1`, but was not connected. WinApp
was the adopted testbed comparison route. Exact prior Cua and shell
measurements remain linked from the research corpus rather than copied here.

**Current implementation:** Provider inventory and routing are now executable
machine-readable capability records. Availability, placement, privilege,
desktop requirements, per-operation fidelity, delivery, effect observation,
host interference, omissions, source pin, and failure policy are distinct.
The service no longer treats `scope=system` as authority to use LocalSystem on
the ordinary Default desktop; protected routing follows the observed input
desktop or lock state instead.

This first slice passed source builds for Windows x64 and ARM64. Its live
composition result is recorded below.

### Cua composition and placement result

**Current — live ARM64 VM:** The runtime now packages the exact evaluated Cua
0.17.0 release asset behind a digest check and supervises it as an unmodified
child of the Medium helper on a private per-generation named pipe. Telemetry
and update checks are disabled. The helper independently requires Medium RID
8192; Cua never starts in the LocalSystem protected process. Capability output
separately reports the evaluated release digest, pinned source-review revision,
and the unresolved fact that the release binary does not attest its source
SHA.

The deterministic fixture workflow passed from both placements through the
same facade. An authenticated remote caller used 18 round trips including the
failure lane; a target-local Medium caller used 12 and deliberately omitted
service revocation because successful revocation terminates that caller's
helper process tree. Both used these ordinary passing routes:

| Operation | Remote latency | Local latency | Route | Oracle |
| --- | ---: | ---: | --- | --- |
| bounded semantic snapshot | 181 ms | 181 ms | `cua/get_window_state` | exact HWND and normalized elements |
| background increment | 63 ms | 51 ms | `cua/accessibility` | fixture-owned counter marker, not Cua agreement |
| exact content capture | 202 ms | 232 ms | `cua/get_window_state_capture` | PNG extent, size, and SHA-256 |

The first projected snapshot response was 1,210 bytes remotely and 1,211
bytes locally, approximately 302 and 303 tokens. The action response was
1,031/1,032 bytes, approximately 258 tokens. The cursor remained at the same
coordinates across each workflow. Foreground changed because the workflow
intentionally launched and changed state on its own fixture; the semantic Cua
action remained background-delivered.

**Current — failure conformance:** A one-millisecond read-only deadline caused
a structured Cua timeout and a separately disclosed native UIA observation.
Killing the supervised daemon invalidated the prior owned reference before
dispatch, consumed its single automatic restart, and recovered a fresh Cua
snapshot. A second crash exhausted the bounded restart and produced an
explicit native observation fallback with both provider attempts. Service
revocation rejected the earlier runtime generation and recreated its helper.
The reversible absence test withheld only the installed Cua executable,
reported the provider `unavailable`, used a disclosed native observation
fallback, restored the exact package, and revoked the temporary generation.

**Current — environment correction:** The first application marker exposed
that `CreateProcessAsUser` had inherited the LocalSystem service environment.
The launcher now creates the correct token-specific environment block before
starting either session helper. The rerun placed `%LOCALAPPDATA%` state in the
interactive user's profile and let the independent marker prove the action.

### WinApp differential result

**Current — live ARM64 VM:** WinApp 0.5.0 ran through the authoritative
testbed's interactive-session relay against the same fixture and representative
shell surfaces. These measurements are end-to-end CLI/relay results, while the
owned facade reports provider-local latency; they therefore establish useful
operational differences rather than a universal provider benchmark.

| Case | WinApp observation | Owned composed route | Result |
| --- | --- | --- | --- |
| fixture inspect/action | 529-byte inspect with 6 actionable elements in 5,767 ms; 47-byte InvokePattern result in 5,666 ms | Cua snapshot/action in 181/51–63 ms | both reached the application-owned counter oracle |
| taskbar Start | 2,022 bytes and 20 controls in 5,846 ms | 289-byte native projection in 137 ms | equivalent required semantic value |
| Settings | 4,660-byte outer-HWND inspect with 39 controls in 6,677 ms | 598-byte native query in 140 ms | both reached the requested Settings surface |
| exact taskbar capture | 1,399×48, 21,664 bytes in 6,752 ms | 1,399×48, 22,141 bytes in 57 ms | no WinApp fidelity advantage in this cell |
| maximize | title-bar InvokePattern in 6,435 ms | native `window.state` with effect readback | both effects confirmed independently |

WinApp also selected Accessibility in Settings; the owned native route then
independently observed the resulting Visual effects surface. This is useful
differential evidence, but no tested operation showed greater reach, fidelity,
effect observability, or ergonomics than the resident Cua/native composition.

**Decision:** Do not add WinApp to the installed runtime for Tactical 004.
Preserve it in `winvm-testbed` as an external differential and diagnostic
route. The platform-depth adapter is the owned native UIA/Win32 provider until
a future measured gap demonstrates that WinApp or another provider is better
for a specific operation.

### Composed shell and protected result

**Current — live ARM64 VM:** The representative shell suite passed through the
composed runtime for Start/Search, taskbar flyouts, Settings, Explorer, desktop
context menu, window lifecycle, exact capture, application switching,
revocation, and helper recreation. Ordinary operations, including
`scope=system`, remained in the Medium helper. Compact examples included Start
at 289 bytes/about 72 tokens/167 ms, Settings at 5,577 bytes/about 1,394
tokens/305 ms, and Explorer at 526 bytes/about 131 tokens/596 ms.

The UAC suite retained the real enabled-consent policy and proved both cancel
and approve on the genuine `Winlogon` input desktop. The protected worker used
input-desktop GDI capture, exposed four semantic elements in the cancel case
and two in the approve case, controlled the resulting High-integrity fixture,
and confirmed its increment through the fixture-owned marker. Cleanup
independently observed zero remaining fixtures.

This run exposed one routing distinction worth preserving. A Medium route can
see an elevated control yet be unable to invoke it, and a Win32 state message
can be delivered across integrity boundaries without effect. The arbiter now
performs one disclosed protected retry only for a system-scoped semantic
refusal before dispatch, or an exact idempotent state action independently
observed to have no effect. It never retries provider references or an action
with unknown completion.

### Physical x64 and placement result

**Current — live physical Windows x64:** The final x64 package installed as the
same automatic resident service and passed without a VM-host, KVM, reboot,
sign-in, or credential route. The target initially reported the
`Screen-saver` input desktop; a target-native protected Escape returned the
already authenticated session to `Default`, after which ordinary work used
the Medium helper.

The deterministic workflow passed remotely in 15 facade round trips and from
a target-local Medium process in 12. Both selected Cua for bounded snapshot,
semantic action, and exact capture; native Win32 owned window state. The
application marker confirmed the action, the one-millisecond observation
deadline produced a disclosed native UIA fallback, remote revocation rejected
the stale generation and recreated the helper, and the cursor remained
unchanged.

| Operation | Remote | Local | Typical serialized size |
| --- | ---: | ---: | ---: |
| bounded snapshot | 83 ms | 95 ms | 1,208 bytes/about 302 tokens |
| semantic increment | 1,102 ms | 44 ms | 1,032–1,038 bytes/about 258–260 tokens |
| exact capture | 187 ms | 114 ms | 1,126 bytes/about 282 tokens |

The physical shell regression also passed. Representative compact results
included Start at 288 bytes/about 72 tokens/82 ms and Settings at 7,412
bytes/about 1,853 tokens/157 ms. Search, Quick Settings, and Notification
Center honestly disclosed their authorized target-local input or pixel
fallbacks where the physical shell exposed fewer semantics. Exact fixture
capture selected Cua. Genuine secure-desktop UAC cancel and approve passed
again, including High-integrity semantics and the independent elevated marker.
Credential login was not rerun because this change did not cross its guarded
secret path.

### Packaging, cleanup, and final decision

**Current:** Self-contained Windows ARM64 and x64 packages build from the same
source and include the upstream MIT license plus a digest-verified Cua 0.17.0
provider. The evaluated provider executable SHA-256 values are
`fef346fc57fb57f5721ee77cf479c607cd5015580447cdca71a71ef43175afaa`
for ARM64 and
`635efe92eb0c3f9737db7e8aca0198f12ccf97e3269a9a75d28388690113db27`
for x64. The package truthfully keeps the evaluated release artifact separate
from the source-review SHA because upstream does not attest that binary's
source provenance.

The physical target deliberately retains the installed final runtime for
continued appliance testing. Tactical staging, raw JSON, screenshots,
application markers, and fixtures were removed. The ARM64 appliance retains
the final runtime, has the original UAC policy, contains none of that temporary
evidence, and was returned to its prior stopped lifecycle.

**Final result:** All completion conditions passed. The owned facade composes
pinned Cua with the deeper native Windows provider per operation, presents the
same contract to local and authenticated outside callers, survives bounded
provider failures without silent fallback, and covers ordinary shell plus
full protected UAC operation without an outer route. The WinApp differential
did not justify another installed adapter. This closes Tactical 002's live
provider-composition condition without a Cua fork or broader rewrite.

Remaining program work—production endpoint authorization, more Windows/session
variants, binary provenance improvements, additional fixtures, and eventual
golden-image automation—is continuing product work rather than an incomplete
Tactical 004 condition.

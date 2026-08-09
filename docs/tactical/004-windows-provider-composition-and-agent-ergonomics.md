# Tactical 004: Windows Provider Composition and Agent Ergonomics

Status: active; started 2026-08-09.

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

Execution has not started. The current owned native provider is the baseline;
Cua is declared but not connected, and WinApp is an external comparison route
rather than an adopted runtime adapter. Tactical 002 remains active on this
provider-composition condition.

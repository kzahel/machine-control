# Tactical 013: Unified Desktop Entry and Conformance

Status: active.

Topics: `target-lifecycle-and-readiness`, `unified-desktop-client`, and
`capabilities-and-results`.

## Objective

Implement one target-selecting client that provides a normalized readiness,
lifecycle, resident-control, artifact, and explicit escape-hatch experience
across the accepted Windows, macOS, and Linux testbeds without moving their
authoritative lifecycle or recovery logic.

## Completion conditions

- A versioned local target registry selects logical targets and testbed
  adapters without committing private paths, machine names, identifiers,
  addresses, or credentials. Portable sibling defaults work for the three
  current desktop testbeds.
- `target status`, `up`, `suspend`, `shutdown`, `force-stop`, `capabilities`,
  and read-only `doctor --json` have normalized output and typed failures.
- Each testbed owns and emits a minimized `machine-control-doctor/v0` readiness
  document with independent power, administration, desktop, resident,
  semantic, capture, input, and outer states.
- `desktop call` reaches every outside resident through its authoritative
  testbed adapter. `desktop call-local` proves the same resident where a local
  placement route exists. Windows receives first-class testbed wrapper entry
  points rather than requiring callers to construct PowerShell manually.
- Friendly commands cover status, capabilities, application/window inventory,
  snapshots, actions, capture, input, and application lifecycle while
  translating only explicitly documented historical operation differences.
- Artifact retrieval accepts only a bounded resident-created handle and
  reports the selected adapter and output path.
- `testbed --` and `os --` preserve machine-specific capabilities explicitly.
  Ordinary desktop calls never silently invoke outer VM-window capture/input.
- Automated adapter tests cover selection, JSON validation, translation,
  failure/refusal behavior, argument preservation, and private-data
  minimization.
- One common deterministic workflow runs against each available accepted
  desktop without outer UI and records local/remote generation parity,
  independent effects, capture/artifact behavior, latency, bytes, and cleanup.
- Documentation describes the accepted surface, deviations, and remaining
  platform-specific gaps. All mutated candidates stop normally.

## Boundaries

- The common client is initially a small dependency-free host CLI and adapter
  contract, not a network service, SDK matrix, MCP server, or YepAnywhere
  integration.
- Testbeds retain target identity, mutation guards, VM lifecycle, bootstrap,
  guest administration, recovery, image factories, and protected-operation
  policy.
- The portable lifecycle subset does not absorb Windows image/seal commands,
  Tart-specific operations, Linux clone/disposable commands, or device
  lifecycle concepts not yet exercised.
- Normalized state does not erase raw adapter state or platform extensions.
- Live validation uses only already authorized candidates. It does not weaken
  TCC, UAC, Polkit, login, secure-desktop, or outer-UI safeguards.

## Implementation steps

### 1 — define target and readiness contracts

Add the target registry and doctor schemas, logical sibling defaults, result
normalization rules, and fixtures for malformed, unavailable, off, degraded,
and ready adapters.

### 2 — expose authoritative testbed adapters

Add machine-readable doctor output and the minimum resident/artifact entry
points to each testbed. Preserve their native human diagnostics and platform
commands. Commit each independently useful testbed slice in its owning
repository.

### 3 — implement the common client

Add target selection, lifecycle dispatch, desktop friendly commands, raw
resident calls, bounded artifacts, result validation, and named `testbed`/`os`
escape hatches. Keep stdout machine-readable when requested and diagnostics on
stderr.

### 4 — prove the common workflow

Run one shared scenario across Windows, macOS, and Linux using deterministic
fixtures and independent effects. Prohibit outer UI, compare local/outside
generations, record efficiency, and clean up each target before normal
shutdown.

### 5 — publish the accepted entry surface

Update the contract, root synthesis, system map, owning topics, testbed
runbooks, and this tactical with exact supported commands, translations,
evidence, deviations, and next work.

## Validation record

Pending implementation and live conformance.

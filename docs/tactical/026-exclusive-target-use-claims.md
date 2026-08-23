# Tactical 026: Exclusive Target-Use Claims

Status: complete

Topics: [`target-use-claims`](../../topics/target-use-claims.md),
[`vm-workspaces-and-storage-policy`](../../topics/vm-workspaces-and-storage-policy.md),
[`target-lifecycle-and-readiness`](../../topics/target-lifecycle-and-readiness.md)

## Objective

Add coordinator-neutral, expiring, exclusive target-use claims to the common
Machine Control experience and enforce them across the accepted Windows,
macOS, and Linux VM paths.

## Completion conditions

- The common CLI exposes claim capabilities, status, acquire, renew, and
  release with bounded caller-supplied attribution and a required reason.
- Claims bind to exact private provider identities and serialize concurrent
  acquisition in adapter-owned private state.
- Accepted VM targets refuse meaningful use without a matching live claim
  while leaving coordination-safe diagnostics available.
- Workspace acquisition returns an atomically acquired usage claim and
  workspace release requires and relinquishes that claim.
- Expiry, reacquisition fencing, conflict projection, renewal, idempotent
  release, and pre-dispatch refusal have dependency-free conformance coverage.
- Agent-facing docs and command help make acquisition and cleanup discoverable
  without naming or depending on a particular coordinator.

## Boundaries

- Do not add code or documentation to YepAnywhere or another coordinator.
- Do not treat self-asserted claimant metadata as authenticated identity.
- Do not make a claim identifier a credential or authorization grant.
- Do not automatically stop, delete, revert, or release a workspace merely
  because its usage claim expired.
- Do not claim protection from another process holding the same unrestricted
  shell or direct provider access.
- Do not extend initial enforcement to physical-device adapters without a
  target-specific contention and lifecycle decision.

## Work

### 1 — publish the claim contract

Define claim vocabulary, identity assurance, timing, fencing, exceptions,
workspace interaction, ownership, and validation requirements. Register the
topic and tactical and update affected architecture documents.

### 2 — implement the private claim authority

Add a dependency-free provider-neutral claim store with private records,
atomic per-resource operations, exact identity checks, expiry, renewal,
release, public minimization, and deterministic tests.

### 3 — expose the common client experience

Add `claim` operations, a global claim selector, schema validation, target
claim-policy discovery, actionable typed refusals, bounded claimant metadata,
and client conformance fixtures.

### 4 — enforce accepted VM use

Connect the Windows/Linux UTM and macOS Tart adapters to the shared authority.
Require claims for effectful lifecycle, administration, desktop, maintenance,
artifact, outer-recovery, and native escape-hatch commands. Preserve doctor,
status, capabilities, claim inspection, and dry-run inventory as safe paths.

### 5 — compose claims with workspaces

Acquire a target-use claim before returning a persistent or derived workspace,
return its descriptor, reject competing persistent acquisition, and require
the matching claim during safe retained/discarded release.

### 6 — validate contention and handoff

Run dependency-free common and provider tests, platform static/smoke suites,
portable repository checks, and a bounded live two-caller exercise where the
configured targets are available. Record honestly any live route that cannot
be exercised.

## Result

Completed on 2026-08-23.

- Published the coordinator-neutral claim contract, vocabulary, ownership,
  exact-identity and workspace rules, schemas, topic, and agent guidance in
  commit `9d5c570`.
- Added the private atomic claim authority, fencing generations, duration and
  metadata bounds, public minimization, permissions, and contention tests in
  commit `5d52de4`.
- Added common claim operations, policy discovery, strict validation,
  pre-dispatch checks, and workspace attribution in commit `adcf5e6`.
- Enforced claims in the Windows/Linux UTM and macOS Tart adapters and composed
  claim acquisition/release with persistent, isolated, and candidate
  workspaces in commit `289bdc1`.
- Added public workflows, subcommand help, platform/operator guidance, live
  conformance cleanup, and this completed record in the final documentation
  commit.

Portable validation passed the common coordinator, claim, workspace, Android,
ChromeOS, iOS, Quest, and Steam Deck suites plus tracked JSON, Bash syntax, and
whitespace checks. The macOS native static suite also passed. The configured
Windows, macOS, and Linux adapter identities each passed live acquire/check/
release and a bounded two-caller contention exercise: one holder won, the
other received `target_claimed`, and the winning claim was released. These
live checks exercised claim arbitration only; they did not boot or control a
VM.

No YepAnywhere or other coordinator files were changed. Physical-device
claims remain a future target-specific decision, as scoped. The current
same-user boundary coordinates cooperating callers and does not prevent direct
hypervisor use or another process with equivalent filesystem authority.

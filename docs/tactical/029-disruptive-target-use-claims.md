# Disruptive Target-Use Claims

Status: complete

Owning topics:

- [`target-use-claims`](../../topics/target-use-claims.md)
- [`inner-first-routing`](../../topics/inner-first-routing.md)

## Objective

Implement the smallest enforceable distinction between ordinary target use and
host-disruptive outer VM recovery. Keep ordinary claims as the default, require
an explicit `claim acquire --disruptive` request for host-visible capture and
host-injected input, and enforce that distinction before an authoritative VM
adapter dispatches the outer provider.

## Completion conditions

- Claim capabilities report the supported `ordinary` and `disruptive` use
  classes and the default class.
- Acquisition accepts `--disruptive`; acquire, status, conflict, and renewal
  results disclose the selected use class without changing exclusive mode.
- Existing active claim records that predate the field load safely as
  `ordinary` rather than becoming disruptive or unreadable.
- A class-aware claim check returns `disruptive_claim_required` when a live
  ordinary claim is presented for a disruptive operation.
- The common client returns that typed refusal before dispatching known outer
  VM capture or input commands.
- The Windows, Linux, and macOS VM wrappers independently recheck the use class
  so direct adapter entry and the common `testbed --` escape cannot bypass the
  gate.
- Platform-owner outer-UI prohibitions remain stronger than a disruptive
  claim, while lifecycle, administration, and target-native desktop control
  continue to accept ordinary claims.
- Dependency-free tests prove defaulting, propagation, refusal, acceptance,
  adapter enforcement, and unchanged workspace composition.

## Boundaries

- Keep this first slice UI-less. Do not add approval dialogs, notifications,
  persistent indicators, or controller GUI dependencies.
- Do not present the cooperative same-user claim store as hostile-process
  authorization or prevent direct hypervisor use outside the governed
  interface.
- Do not overload `mode: exclusive`; represent disruption as a separate use
  class on the same exact-resource lease.
- Do not grant disruptive access to workspace-acquired claims implicitly.
- Do not weaken an adapter's absolute `FORBID_OUTER_UI` policy or target,
  geometry, role, and lifecycle guards.
- Do not require live outer capture or input to validate a refusal that occurs
  deterministically before provider dispatch.

## Work

### 1 — extend the claim contract and private authority

Add use-class capability and descriptor fields, ordinary-by-default
acquisition, an explicit disruptive acquisition flag, class-aware validation,
and safe loading of legacy active records. Cover the store and JSON contracts
with deterministic tests.

### 2 — expose the common client experience

Accept and forward `claim acquire --disruptive`, validate the expanded
capability and result shapes, keep workspace claims ordinary, and request a
disruptive check for known outer VM commands before dispatch.

### 3 — enforce authoritative adapter boundaries

Add one shared class-aware shell guard and apply it to host-visible screenshot,
pointer, keyboard, scan-code, and drag operations in the Windows, Linux, and
macOS VM wrappers. Preserve the provider-owned absolute prohibition after the
claim gate.

### 4 — prove compatibility and publish current truth

Run claim, client, workspace, platform smoke, contract, portable, and native
checks. Update the owning topics, provider documentation, command help, and
this tactical with the implemented behavior and validation result.

## Validation

- `python3 -m unittest discover -s providers/claims/tests -v`
- `python3 -m unittest discover -s tests/client -v`
- `python3 -m unittest discover -s providers/workspaces/tests -v`
- `bash platforms/windows/tests/smoke.sh`
- `bash platforms/linux/tests/static.sh`
- `bash platforms/macos/tests/smoke.sh --static`
- `python3 bin/check --portable`
- `python3 bin/check --native`

## Result

Completed on 2026-08-25.

The shared claim contract and private authority now expose `useClasses` policy
and a per-claim `useClass`. Acquisition defaults to `ordinary` and accepts the
explicit `--disruptive` flag. A class-aware check returns
`disruptive_claim_required` with the current minimized holder descriptor when
an ordinary claim is presented. Legacy active records without the field load
as ordinary and are upgraded in private state on their next write.

The common client validates and projects the expanded contract, forwards
explicit disruptive acquisition, keeps workspace-composed claims ordinary,
and performs a typed preflight for known host-side VM commands. The Windows,
Linux, and macOS public wrappers independently repeat the exact-resource
disruptive check for every host-visible screenshot, pointer, keyboard, drag,
and scan-code command before provider dispatch. Existing provider target,
geometry, role, and absolute outer-UI prohibitions remain unchanged and are
still evaluated after a disruptive claim passes.

Implementation landed in the following commits:

- `e83d716` added the claim-store and JSON-contract use classes, class-aware
  validation, compatibility default, and store tests;
- `07efedf` added the common client flag, validation, typed preflight, and
  client fixtures;
- `d1dc413` added authoritative wrapper enforcement and full command-set
  adapter tests; and
- `8bd6c49` published current topic, contract, platform, and agent guidance.

The claim, client, and workspace suites passed. Windows smoke, Linux native
static, macOS native static, `python3 bin/check --portable`, and
`python3 bin/check --native` passed, including tracked JSON, Bash syntax, and
whitespace checks. The Linux and macOS full smoke runners require a configured
accepted guest, while the behavior in this slice is deterministically refused
before provider dispatch; their fixture/static variants were used instead.
No live outer capture or input was invoked, and no claim policy was bypassed
for target operation.

Notifications, approval, a persistent active indicator, and immediate
controller revocation remain the explicitly deferred controller-affordance
layer.

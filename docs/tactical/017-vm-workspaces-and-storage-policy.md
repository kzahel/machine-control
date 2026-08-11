# Tactical 017: VM Workspaces and Storage Policy

Status: active.

Topics: `vm-workspaces-and-storage-policy` and
`target-lifecycle-and-readiness`.

## Objective

Add an adapter-neutral VM workspace surface that keeps persistent development
machines as the ordinary default, supports disposable or thin isolated work
when a provider can do so safely, and retains explicit candidates without
creating a large VM per feature. Preserve UTM, Tart, and future libvirt/KVM as
replaceable lifecycle mechanisms behind authoritative platform adapters.

## Completion conditions

- The public contract separates persistent, isolated, and candidate intent
  from actual derivation mechanisms and storage cost.
- The common coordinator exposes additive workspace capability, acquisition,
  inventory, release, and garbage-collection dry-run commands.
- Private inventory may select a default intent without publishing concrete
  VM identities or provider state.
- Adapter results validate against public schemas and redact concrete provider
  identifiers, commands, paths, endpoints, and receipts.
- Windows UTM maps isolated work to provider disposable mode and keeps
  persistent development and ready-base roles distinct.
- Tart maps isolated work to a temporary APFS copy-on-write clone and retains
  explicit candidates.
- Temporary cleanup is bound to mode-`0600` creation receipts and fresh exact
  provider identity; source and last-ready-base protection fail closed.
- Full or unknown-cost derivation obeys explicit capacity and policy gates.
- Fake adapters exercise the contract natively on macOS, Linux, and Windows.
- Minimal live UTM and Tart rehearsals prove mechanism outcomes when authorized
  controller-ready bases are available; unavailable live readiness is
  recorded honestly without using outer UI.

## Boundaries

- Do not change the behavior of `target up` or make workspace acquisition an
  ordinary desktop-control prerequisite.
- Do not create one persistent clone per feature or silently convert every
  task into a disposable run.
- Do not create, rebuild, delete, or generalize a real Windows appliance merely
  to complete the portable contract.
- Do not implement libvirt without an authorized host. Define its adapter
  boundary and conformance expectations now.
- Do not expose private target names, UUIDs, paths, endpoints, receipts, or
  storage topology in the public repository or normalized output.
- Do not treat a workspace handle as authority or garbage collect resources
  that lack an exact adapter-owned receipt.

## Ordered work

### 1 — establish the workspace vocabulary

Create the owning topic, register its commit series, and describe intent,
mechanism, placement, storage, ownership, and policy boundaries. Update the
target-lifecycle topic and system map only where the new boundary changes their
current truth.

### 2 — add contracts and fake-provider conformance

Add capability and operation-result schemas, sanitized examples, validators,
and a dependency-free fake adapter. Cover all three intents, mechanism
disclosure, unsupported intent, redaction, opaque handles, and non-mutating
inventory/garbage-collection dry-run behavior.

### 3 — expose the common workspace client

Add coordinator commands without changing ordinary target lifecycle. Forward
only normalized intent and opaque handles. Validate every adapter response and
return typed refusals when an adapter lacks the workspace interface.

### 4 — implement UTM workspace policy

Compose the existing UTM disposable and clone primitives behind workspace
commands. Keep persistent development and stopped ready-base identities in
private configuration. Use disposable mode for isolated work, classify
ordinary clone cost conservatively, serialize source use, and bind release to
exact provider state.

### 5 — implement Tart workspace policy

Use local APFS copy-on-write clone semantics for isolated and candidate work.
Enforce one temporary workspace by default, source mutation guards, storage
headroom, receipt ownership, and exact-name release. Keep long-lived
development reuse as the default.

### 6 — wire private preferences

Extend the private inventory projection with sanitized default intent while
keeping real role relationships and provider identities in its private
configuration. Test controller-specific registry output on macOS, Linux, and
Windows.

### 7 — validate and record evidence

Run portable/native checks and platform smoke tests. Perform only the small
live disposable and copy-on-write rehearsals allowed by current target
readiness, clean temporary mutations, update current topics and this result,
then push the complete commit series.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- `python3 -m unittest tests/client/test_machine_control.py`
- platform shell syntax and smoke tests for every changed provider;
- dotfiles private-inventory tests on the current controller and hosted matrix;
- read-only inventory before live mutation, exact identity guards before
  acquire/release, and no outer input during ordinary validation.

## Result

Active. Record implemented mechanisms, validation evidence, deviations, and
remaining live-appliance work here before completion.

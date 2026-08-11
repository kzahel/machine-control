# Tactical 017: VM Workspaces and Storage Policy

Status: complete (August 11, 2026).

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

Completed. The common client now exposes validated workspace capabilities,
acquisition, opaque-handle selection, receipt-minimized inventory, guarded
release, and dry-run garbage collection. Public schemas distinguish caller
intent from `existing_instance`, provider-disposable, filesystem COW,
full-copy, and future QCOW backing mechanisms. Private inventory chooses only
the default intent and concrete provider policy; normalized results reject
private names, identifiers, endpoints, commands, paths, and receipt contents.

Windows and Linux UTM adapters reuse an explicitly proven development VM for
`persistent`, use UTM disposable mode for `isolated`, and prohibit ordinary
full-copy candidates unless private policy grants a bounded one-time fallback.
The Tart adapter reuses a proven development VM or creates APFS copy-on-write
derivatives. Default limits permit one temporary and two retained workspaces,
reserve provider-storage headroom, and never auto-delete a source or ready
base. Mode-`0600` private receipts and fresh exact identity checks bind every
temporary release. Direct macOS and Linux lifecycle mutations also now fail
closed when only public example selection is present.

Portable checks passed 38 common-client tests, eight receipt/UTM mechanism
tests, the other dependency-free platform corpora, tracked JSON and shell
validation, and whitespace checks. Native macOS validation passed the Swift,
plist, shell, and fail-closed provider checks; the existing Swift deprecation
warnings remain informational. Dotfiles passed its ten private-inventory
tests.

One live Tart rehearsal acquired an isolated APFS COW clone, addressed it only
through its opaque handle, and passed the common doctor with administration,
desktop, resident, semantic, capture, and input all ready. Release stopped and
deleted only that derivative, removed its receipt, and left the protected
source stopped. The first attempt had correctly retained a cleanup-pending
receipt when a Tart guest-agent transport was unavailable; guarded release
cleaned it, and the adapter was corrected to rediscover a derivative's own
endpoint for the configured guest transport before the passing repetition.

No current UTM guest qualified as an authorized ready base for a minimal live
disposable rehearsal. The Linux appliance started but its QEMU guest-agent and
resident readiness did not recover within the bounded check, so it was shut
down cleanly without outer UI. The Windows selection is a generalized seal,
not an authorized controller-ready derivation base. UTM outcome and cleanup
semantics therefore remain deterministic fake-provider evidence until either
platform has a freshly proven base; no new large VM was created to satisfy
this tactical.

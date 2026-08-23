# VM Workspaces and Storage Policy

Topic: `vm-workspaces-and-storage-policy`

Status: implemented contract and current provider policy.

## Scope

This topic owns the portable intent, capability, storage, ownership, and
cleanup vocabulary for derived virtual-machine workspaces. It covers the
choice between reusing a stateful development VM, running clean work without
retaining its changes, and retaining an explicit appliance-development
candidate.

It does not make the common coordinator a hypervisor driver. The authoritative
platform adapter still resolves private base and development identities,
checks provider-native identity and roles, chooses an implementation
mechanism, and performs cleanup. Ordinary `target up` retains its existing
meaning and behavior.

## Intent is distinct from mechanism

**Decision:** callers request one of three workspace intents:

- `persistent` reuses and retains the configured stateful development target;
- `isolated` starts from a known-ready base and discards all changes on
  release; and
- `candidate` starts from an authorized base and retains changes for explicit
  appliance development, acceptance, or promotion.

The adapter reports the actual mechanism. Portable mechanism values are:

```text
existing_instance
provider_disposable_overlay
filesystem_cow_clone
qcow_backing_overlay
full_copy
fresh_provision
```

An isolated UTM/QEMU target may use provider disposable mode. Tart may use an
APFS copy-on-write clone. A future libvirt/QEMU provider may use a transient
domain with a QCOW2 backing overlay. These are equivalent only in the promised
workspace outcome; their concurrency, base dependency, capacity, and recovery
properties remain explicit.

A derived Tart target never inherits the development VM's fixed SSH endpoint.
Its configured guest transport rediscovers the derivative's own address.

## Placement and ownership

**Decision:** the coordinator, adapter execution endpoint, hypervisor host,
and guest target are independent placements. A route selected on a Linux
controller may call local libvirt; another route may reach an authenticated
provider endpoint on a separate Linux VM host. The common client launches the
selected authoritative adapter and never assumes that the hypervisor is local.

The public contract contains logical aliases, normalized capabilities, and
opaque workspace handles. Concrete VM names, UUIDs, storage paths, endpoints,
and provider receipts remain in private inventory or mode-`0600` adapter state.
A handle is a selector, not bearer authority.

A workspace receipt is also not a usage reservation. Exclusive caller access
is governed by the separate target-use claim contract in
[`target-use-claims.md`](target-use-claims.md). Workspace acquisition composes
the two atomically, while cleanup ownership and current usage remain distinct.

Only an adapter that created a temporary resource may release or garbage
collect it. Creation writes a receipt bound to the exact provider identity,
source identity, requested intent, actual mechanism, and cleanup disposition.
Deletion requires the receipt and a fresh provider-native identity match; a
name, prefix, age, or glob is never sufficient.

## Policy layers

**Decision:** portable preferences and provider safety remain separate.

Preferences may select the default intent, limit temporary and retained
workspaces, reserve free storage, and refuse expensive copy fallback. Private
inventory may choose a default intent for a logical target. A command may make
an explicit allowed override.

Provider safety remains authoritative and cannot be weakened by the common
client. Every adapter must:

- protect source and ready-base roles from ordinary mutation;
- refuse deletion of the last known controller-ready base;
- require a stopped source when its mechanism needs one;
- serialize mechanisms that cannot share a source concurrently;
- fail closed when derivation cost or cleanup ownership is uncertain; and
- keep an unsuccessful temporary workspace for diagnosis unless an exact,
  adapter-owned cleanup receipt makes automatic release safe.

Default policy favors one persistent development VM and one stopped ready
base. It creates no per-feature clone implicitly. At most one temporary
workspace may exist by default, even when its initial storage is cheap.

## Storage vocabulary

**Decision:** logical disk size is not physical cost. Providers report a cost
class and the strongest measurements they can support:

```text
cost_class       = overlay | copy_on_write | full_copy | unknown
measurement      = exact | estimate | unavailable
virtual_bytes    = guest-addressable capacity when known
allocated_bytes  = provider object allocation when meaningful
exclusive_bytes  = uniquely owned allocation when measurable
free_bytes       = provider storage-volume capacity when measurable
```

Copy-on-write is an initial-cost property, not a permanent size promise. A
policy must reserve divergence headroom for operating-system updates, SDKs,
caches, and build output. Shared APFS extents may make per-directory totals
double-count storage, so adapters must not present their sum as exclusive
allocation.

## Portable surface

**Decision:** workspace management is additive beside target lifecycle:

```text
machine-control --target <alias> workspace capabilities
machine-control --target <alias> workspace acquire --intent <intent>
machine-control --target <alias> workspace inventory
machine-control --target <alias> workspace release <opaque-handle>
machine-control --target <alias> workspace gc --dry-run
machine-control --target <alias> --workspace <opaque-handle> target doctor
machine-control --target <alias> --workspace <opaque-handle> desktop status
```

`capabilities` and `inventory` are read-only. `acquire` and `release` are
explicitly mutating. Garbage collection begins as dry-run only; automatic or
confirmed cleanup must never broaden its selection beyond adapter-owned
receipts.

The returned handle explicitly selects later target, desktop, testbed, or OS
calls. The coordinator forwards it as an adapter selector. The adapter still
requires its private receipt and a fresh exact provider-identity match; the
handle grants no authority by itself. Workspace-management operations reject
an already selected handle to avoid ambiguous nested acquisition or release.

The normalized acquire result reports requested intent, actual mechanism,
retention, whether cleanup is automatic, and storage preflight confidence. It
also reports the acquired target-use claim. It does not publish the concrete
source or derived VM identity. Workspace release requires that matching live
claim and relinquishes it only after safe retain-or-discard handling completes.

## Provider direction

**Current:** Windows and Linux lifecycle use UTM/QEMU on macOS; macOS uses
Tart. UTM already exposes non-persistent start and registered clone operations.
Tart exposes APFS copy-on-write local clones. Existing provider-specific
commands remain compatibility escape hatches while the workspace surface is
adopted.

**Decision:** a future [libvirt QEMU/KVM provider](https://libvirt.org/drvqemu.html)
implements the same platform adapter contract. The Windows guest driver,
resident facade, and readiness contract remain unchanged when lifecycle moves
from UTM/macOS to libvirt/Linux. Virt-manager may be a human-facing libvirt UI
but is not part of the portable contract. The provider should use libvirt as
its owned automation surface over QEMU/KVM, use QEMU guest-agent or guest
networking only through typed adapter operations, and prove QCOW2
backing-overlay cleanup rather than assuming that a snapshot or overlay
satisfies `isolated` intent.

**Decision:** [Hyper-V](https://learn.microsoft.com/windows-server/virtualization/hyper-v/overview)
is the first Windows-host provider candidate for Windows and Linux guests. Its
PowerShell management surface should own exact VM identity, lifecycle,
storage, and checkpoint or differencing-disk mechanisms.
[PowerShell Direct](https://learn.microsoft.com/windows-server/virtualization/hyper-v/powershell-direct)
is useful for Windows bootstrap and recovery but is not a cross-guest
transport; Linux and ordinary post-bootstrap control continue through explicit
guest administration and the target-resident facade. Hyper-V Manager and
VMConnect are human and outer-recovery surfaces, not the ordinary adapter
contract. Evaluate [QEMU with WHPX](https://www.qemu.org/docs/master/system/whpx.html)
only if live evidence finds a required host-edition, workspace, capture, input,
or recovery gap that the Hyper-V provider cannot meet. VMware and VirtualBox
remain unselected candidates rather than implicit fallbacks.

**Decision:** neither the Linux nor Windows host plan attempts to virtualize a
macOS guest. Callers on those platforms reach a physical Mac, its resident
controller, or an Apple-hosted Tart adapter through an authenticated remote
route. Remote adapter execution is a normal placement of the same contract,
not evidence of a local Linux or Windows macOS hypervisor.

## Current implementation and validation

Dependency-free fake-provider tests run on macOS, Linux, and Windows and cover
capability validation, intent forwarding, redaction, unsupported intent,
receipt-bound release, capacity refusal, last-ready-base protection, and
dry-run inventory. UTM-specific fake-provider tests additionally prove
persistent
reuse, disposable stop without source deletion, and the full-copy policy gate.

**Current:** one live Tart copy-on-write clone reached full common-doctor
readiness and was released without mutating its stopped source. A failed first
start also proved cleanup-pending receipt retention and guarded operator
release; derived targets now rediscover their own endpoint instead of
inheriting the development VM's fixed SSH endpoint.

**Current:** the retained Windows and Linux candidates each passed a fresh
running-ready observation, clean shutdown, and exact stopped identity
assertion. Private inventory lets each single stateful VM serve as both its
development target and stopped ready base, permits one temporary workspace,
reserves provider storage headroom, and prohibits implicit full-copy fallback.

Each UTM base also passed one minimal disposable-outcome rehearsal. A marker
created in provider disposable mode was absent after release and persistent
restart; both receipt inventories ended empty and both bases ended stopped.
This validates discard-on-release without making a disposable VM the default
for ordinary stateful work. A future provider repeats the outcome with its own
declared overlay mechanism.

## Open work

- Determine whether storage divergence can be measured usefully enough to
  warn on a long-lived copy-on-write workspace without claiming false
  per-workspace precision.
- Decide when an isolated failure should be retained automatically versus
  stopped with only its receipt retained for operator-directed recovery.
- Add a libvirt/Linux host provider only when an authorized host is available
  for real capability and cleanup validation.
- After the Linux provider proves the adapter boundary, add and live-validate
  a Hyper-V/Windows host provider, beginning with a Windows guest and then a
  Linux guest. Keep its supported host editions and CPU architectures explicit
  rather than projecting one successful machine onto all Windows hosts.

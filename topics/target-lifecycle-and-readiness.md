# Target Lifecycle and Readiness

Topic: `target-lifecycle-and-readiness`

Status: current common outer entry surface for accepted desktop adapters and
normalized Android, iOS, and Quest device adapters.

## Scope

This topic owns the agent-facing vocabulary for selecting a target, inspecting
its readiness, and requesting ordinary lifecycle transitions. It does not own
hypervisor, physical-device, bootstrap, recovery, or private-inventory logic.
Platform-specific logic remains in the authoritative platform/testbed adapter:
in the external repository before consolidation cutover and in its platform
directory here afterward. Private inventory remains outside this public
repository.

The common surface should make the frequent workflow consistent:

```text
machine-control --target <logical-target> target status
machine-control --target <logical-target> target up
machine-control --target <logical-target> target doctor
machine-control --target <logical-target> target ensure-ready
machine-control --target <logical-target> target shutdown
```

VM workspace acquisition is an additive surface beside this lifecycle, not a
replacement for `target up`. See
[`vm-workspaces-and-storage-policy.md`](vm-workspaces-and-storage-policy.md)
for persistent, isolated, and retained-candidate intent.

A logical target is a local inventory selector, not bearer authority and not
necessarily a VM. Target aliases and adapter paths may live in ignored local
configuration. Tracked examples must use non-authoritative placeholders and
must not disclose real infrastructure.

## Ownership boundary

**Decision:** The common client dispatches lifecycle and readiness requests to
the authoritative platform/testbed adapter. Repository placement does not
change this adapter boundary. The common client does not invoke Tart, UTM,
SSH, QEMU, CoreDevice, ADB, or a device directly.

The platform/testbed adapter retains:

- exact target identity, UUID/serial pinning, role and mutation guards;
- start, resume, suspend, shutdown, stop, clone, disposable, and delete policy;
- bootstrap, guest command transport, outer recovery, and safe cleanup; and
- platform-specific readiness checks and remediation guidance.

The common client owns target selection, stable command names, normalized
results, exit behavior, and preservation of typed adapter extensions.

## Lifecycle vocabulary

**Current:** The portable subset is `status`, `up`, `suspend`, `shutdown`,
`force-stop`, `doctor`, and `capabilities`. An adapter reports unsupported
operations instead of silently substituting a materially different transition.

`up` means reach the testbed's ordinary running state. It may start or resume.
`shutdown` requests a clean guest shutdown and waits for the authoritative
provider's terminal state. `suspend` preserves state only when the testbed
declares it safe. `force-stop` remains explicit and is never an automatic
fallback. Testbed-specific commands such as Windows `down`, image sealing,
disposable launch, or Linux reboot remain escape hatches.

Normalize observations to the applicable state dimensions without discarding
the raw adapter value. Desktop targets use:

```text
power_state       = off | starting | running | suspended | unknown
admin_state       = ready | degraded | unavailable | unknown
desktop_state     = unlocked | locked | protected | no_session | unknown
resident_state    = ready | degraded | unavailable | unknown
semantic_state    = ready | degraded | unavailable | unknown
capture_state     = ready | degraded | unavailable | unknown
input_state       = ready | degraded | unavailable | unknown
outer_state       = ready | observation_only | prohibited | unavailable | unknown
```

Device targets instead add these dimensions and do not claim a desktop or
resident process:

```text
connection_state  = ready | degraded | unavailable | unknown
boot_state        = ready | degraded | unavailable | unknown
interaction_state = unlocked | locked | protected | no_session | unknown
runner_state      = ready | degraded | unavailable | unknown
```

Both target kinds retain power, administration, semantic, capture, input, and
outer/device-host route state. A device can be connected while protected, or
have a cached runner whose post-boot authorization remains unverified.

## Doctor contract

**Decision:** `doctor` is read-only. It must never boot, resume, log in, grant
consent, deploy software, or fall back to outer input. A distinct requested
operation may perform those mutations.

`doctor --json` returns one `machine-control-doctor/v0` document containing:

- the logical target and platform profile;
- overall readiness and the independent state dimensions above;
- a stable list of named checks with `pass`, `warn`, `fail`, or `skip` status;
- resident contract version and generation when reachable;
- available lifecycle operations and the adapter actually used;
- outer-control availability and host-interference policy; and
- an `extensions` object for platform/testbed facts that cannot be normalized.

The portable result must not expose a real hostname, IP address, user name,
VM/device identifier, credential, or private route. Human-oriented native
testbed output may remain more diagnostic locally; the common JSON projection
is deliberately minimized for agent use and durable evidence.

## Explicit readiness and candidate handoff

**Current:** `target ensure-ready` is the explicitly mutating counterpart to
`doctor`. It first preserves the complete normalized doctor observation. When
the target is off, suspended, or still starting and the adapter declares
`up`, it requests that one ordinary start transition and runs doctor again.
The result records the initial and final states, its bounded action list,
completion, and uncertainty. A running unhealthy target returns
`readiness_repair_required`; the client never guesses a bootstrap, login,
consent, credential, outer-input, or force-stop action.
If an adapter reports start failure, the client still performs the final
read-only doctor and keeps reported delivery separate from the independently
observed ready or unready effect.

**Current:** `target validate-candidate` requires an exact adapter-side
candidate-role and identity assertion with no workspace receipt ownership,
then obtains a fresh running-ready doctor observation. It is evidence, not
promotion authority. `target prepare-promotion` performs the same observation,
requests a clean shutdown, and requires a second exact assertion in the off
state. Only that stopped result is eligible for a subsequent private-inventory
role update. A `--workspace` handle is rejected for promotion preparation.

## Current implementation

[`bin/machine-control`](../bin/machine-control) selects a logical target from
portable in-repository platform defaults, an ignored
[`machine-control-targets/v0`](../contracts/targets-v0.schema.json) registry,
or an optional private inventory provider. The provider may carry concrete
commands and environment internally; `targets` omits both from its output.
It delegates every lifecycle operation to the selected authoritative testbed,
returns a `machine-control-target/v0` projection with both normalized and raw
adapter state, and validates each testbed's
[`machine-control-doctor/v0`](../contracts/doctor-v0.schema.json) document.

The three common desktop adapters independently inspect power, administration,
logged-in desktop, resident, semantic, capture, input, and outer-route policy. Powered
off is a valid minimized doctor result with `ready: false`; doctor does not
start or repair the target. Live acceptance proved common clean shutdown and
subsequent `powerState: off` on all three profiles. See the
[three-desktop evidence](../docs/evidence/desktop-common-entry.md).

The desktop VM adapters also expose the additive workspace protocol. Public
macOS and Linux examples now require an exact ignored/private
candidate-or-disposable binding before any lifecycle mutation; a plausible
example name alone cannot start, suspend, shut down, or stop a local VM.

Android, iOS, and Quest retain `native` platform interfaces below the common
layer but now emit the same minimized doctor envelope. The common client
therefore exposes `target status|doctor|capabilities` for all three and only
dispatches a mutating lifecycle verb when that exact adapter declares it. iOS
and Android currently declare full reboot; Quest deliberately does not. iOS
full reboot is live-accepted for the passcode-free profile and preserves a
typed manual-first-unlock state for passcode-protected devices.

iOS additionally has an explicit common `ios` operation family beside target
lifecycle. This does not add application or semantic verbs to the portable
lifecycle set and does not make Android or Quest inherit XCTest semantics.
ChromeOS and Steam Deck remain behind the explicit `testbed --` escape until
their own normalized projections exist.

## Failure behavior

- Missing inventory, target, adapter, or command returns a typed refusal.
- A powered-off target is a valid observation, not an adapter crash.
- `doctor` can be successful as an observation while reporting `ready: false`;
  the CLI exit code remains nonzero so automation fails closed.
- Platform extensions never override a failed portable readiness dimension.
- Outer recovery is reported, not invoked, by ordinary readiness checks.

## Open work

- Add narrowly named, idempotent inner repair operations only where live
  evidence establishes an honest precondition and effect contract. Start-only
  readiness remains the portable default.
- Add authorization and discovery above the current local registry without
  turning a logical alias into bearer authority.
- Extend the device projection to ChromeOS and Steam Deck where it adds honest
  value without fabricating lifecycle parity.
- Integrate authorized target discovery with YepAnywhere without moving
  private inventory into this public repository.

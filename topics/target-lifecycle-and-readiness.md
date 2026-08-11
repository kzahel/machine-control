# Target Lifecycle and Readiness

Topic: `target-lifecycle-and-readiness`

Status: proposed common entry surface over authoritative testbed adapters.

## Scope

This topic owns the agent-facing vocabulary for selecting a target, inspecting
its readiness, and requesting ordinary lifecycle transitions. It does not own
hypervisor, physical-device, bootstrap, recovery, or private-inventory logic.
Those remain in the authoritative testbed.

The common surface should make the frequent workflow consistent:

```text
machine-control --target <logical-target> target status
machine-control --target <logical-target> target up
machine-control --target <logical-target> target doctor
machine-control --target <logical-target> target shutdown
```

A logical target is a local inventory selector, not bearer authority and not
necessarily a VM. Target aliases and adapter paths may live in ignored local
configuration. Tracked examples must use non-authoritative placeholders and
must not disclose real infrastructure.

## Ownership boundary

**Decision:** The common client dispatches lifecycle and readiness requests to
the authoritative testbed adapter. It does not invoke Tart, UTM, SSH, QEMU,
CoreDevice, ADB, or a device directly.

The testbed retains:

- exact target identity, UUID/serial pinning, role and mutation guards;
- start, resume, suspend, shutdown, stop, clone, disposable, and delete policy;
- bootstrap, guest command transport, outer recovery, and safe cleanup; and
- platform-specific readiness checks and remediation guidance.

The common client owns target selection, stable command names, normalized
results, exit behavior, and preservation of typed adapter extensions.

## Lifecycle vocabulary

**Proposal:** The portable subset is `status`, `up`, `suspend`, `shutdown`,
`force-stop`, `doctor`, and `capabilities`. An adapter reports unsupported
operations instead of silently substituting a materially different transition.

`up` means reach the testbed's ordinary running state. It may start or resume.
`shutdown` requests a clean guest shutdown and waits for the authoritative
provider's terminal state. `suspend` preserves state only when the testbed
declares it safe. `force-stop` remains explicit and is never an automatic
fallback. Testbed-specific commands such as Windows `down`, image sealing,
disposable launch, or Linux reboot remain escape hatches.

Normalize observations to these state dimensions without discarding the raw
adapter value:

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

## Failure behavior

- Missing inventory, target, adapter, or command returns a typed refusal.
- A powered-off target is a valid observation, not an adapter crash.
- `doctor` can be successful as an observation while reporting `ready: false`;
  the CLI exit code remains nonzero so automation fails closed.
- Platform extensions never override a failed portable readiness dimension.
- Outer recovery is reported, not invoked, by ordinary readiness checks.

## Open work

- Determine when `ensure-ready` is useful as an explicitly mutating compound
  operation after the individual lifecycle and doctor paths are proven.
- Add physical/device lifecycle profiles without making desktop VM fields
  mandatory.
- Integrate authorized target discovery with YepAnywhere without moving
  private inventory into this public repository.

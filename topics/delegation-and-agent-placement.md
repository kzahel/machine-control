# Delegation and Agent Placement

Topic: `delegation-and-agent-placement`

Status: active coordination and placement contract.

## Decision

YepAnywhere cross-host delegation is the initial orchestration mechanism. A
controller session creates and supervises separate native worker sessions on
authorized YA peers. It does not move the controller transcript and does not
proxy every target operation through the controller.

Delegation is not the machine-control transport. An authorized outside agent
can address a target-resident controller directly. A delegated worker is an
optional execution placement for local development context or agent-coupled
tools, and it calls the same resident control surface locally.

## Three selections, not one

Before starting work, coordination resolves three independent choices:

1. **Worker peer:** where the agent provider will execute.
2. **Project:** which target-local checkout or workspace the worker will use.
3. **System under test:** which local machine, VM, attached device, browser, or
   remote target the worker will control.

For a Windows VM these may all point at the Windows guest. For physical iOS,
the worker and project live on a Mac while the SUT is the attached phone. For a
hardware KVM, the worker may run on the KVM controller while the SUT has no
software agent at all.

## Preferred desktop flows

```text
controller                authoritative testbed        resident controller
    |                              |                            |
    |-- readiness/start ---------->|                            |
    |<---------- target reachable -|                            |
    |---------------- authenticated direct control ----------->|
    |                        semantic/capture/input/admin        |
    |<----------------------- results and evidence -------------|
    |-- outer recovery only ------>|                            |

controller                         target YA          resident controller
    |                                 |                         |
    |-- optional delegation -------->|                         |
    |                         local build/debug                 |
    |                                 |-- local control ------->|
    |<------------- progress/attention/result -----------------|
```

The outer testbed may prepare a stopped guest before direct control or
delegation. Once the resident controller is healthy, it should leave ordinary
desktop work to that controller. Spawning a worker should not be required just
to make semantic UI or guest-local input remotely reachable.

## Supervision states

The delegation record and machine state should remain distinct. Useful worker
states include:

- `starting`
- `active`
- `waiting_for_input`
- `waiting_for_recovery`
- `complete`
- `failed`
- `unavailable`

Useful machine dimensions include power, guest administration, desktop
session, semantic provider, and outer-provider readiness. A worker can be
`active` while a visual provider is degraded, or `unavailable` while the VM is
still running.

## Attention and recovery

A worker should request controller attention when:

- a required capability is absent or degraded;
- a human credential/consent gate is reached;
- an inner provider cannot determine whether an action occurred;
- the interactive session is locked, logged out, or on a protected desktop;
- guest IPC is failing and an independent route is needed; or
- continuing would require a route outside the worker's grant.

The controller may answer, delegate a diagnostic task elsewhere, invoke the
outer testbed, or ask the user. It should not automatically widen the worker's
tools after an attention event.

## Local and remote use share semantics

The same coordination application service should support:

- starting a worker on the current YA peer;
- starting a worker on an authorized remote peer; and
- supervising both through the same operations.

Peer authentication, grants, project resolution, and remote failure handling
are additional layers for remote work. They should not cause a separate worker
state model or a second orchestration product.

## Artifacts and results

The worker returns a bounded result plus references to target-owned artifacts.
The controller does not need the entire worker transcript in its context. A
result should identify:

- worker peer/session and SUT;
- project/commit facts relevant to the run;
- capabilities and actual routes used;
- assertions and evidence;
- degraded, unverifiable, or skipped coverage;
- recovery or human actions that occurred; and
- final cleanup/lifecycle recommendation.

## Open coordination question

**Open:** Decide whether a worker session ever moves between YA peers or
whether delegation to a new target-owned session remains the long-term model.
Do not make worker migration a prerequisite for the machine-control contract.

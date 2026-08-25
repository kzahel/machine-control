# Inner-First Routing

Topic: `inner-first-routing`

Status: accepted routing and authorization policy.

## Problem

The desktop testbeds document semantic control before coordinate control, but
an agent can still discover and invoke the outer VM controls. On macOS-hosted
VMs those controls may focus UTM or Tart, move the host pointer, type through
the controller desktop, or otherwise interrupt the user's main work.

A preference in a skill is insufficient. Tool availability and authorization
should make the safe route the natural route.

## Decision

Ordinary worker sessions use only:

- `guest.admin` for files, processes, builds, deployment, logs, and OS state;
- `guest.user` for application launch, semantic snapshots/actions, and
  guest-local screenshots/input; and
- a specifically authorized `guest.broker` capability when a task genuinely
  requires a protected route.

`host.hypervisor` and external KVM/HID routes are not ordinary worker tools.
They belong to the controller/testbed recovery path.

## When outer control is appropriate

Outer observation or input is justified for:

1. Initial VM creation or startup before the guest agent is reachable.
2. Bootstrapping the guest administration channel or semantic helper.
3. Diagnosing a suspected guest hang, missing interactive session, lock screen,
   or broken guest IPC.
4. Recovering after the inner provider reports a structured unavailable or
   unhealthy state.
5. Providing an independent visual oracle for a bounded conformance test,
   preferably without input or host focus changes.
6. Operating a target that inherently has no guest agent, such as an attached
   phone or a hardware-KVM-only machine.

Outer control is not justified merely because:

- a semantic selector was inconvenient;
- a screenshot looked easier than inspecting the native tree;
- the worker did not read the target's operating guide;
- one accessibility node was missing while other guest-local fallbacks remain;
- the provider could retry by foregrounding the VM host window; or
- coordinate input happened to work in a previous run.

## Enforcement model

### Separate tool grants by agent role

The controller session may receive testbed lifecycle and recovery operations.
A delegated worker normally receives guest-local tools only. The worker cannot
request a broader route by supplying a target ID, route string, environment
variable, or public session label.

### Structured recovery request

When an inner route fails, the worker reports:

```json
{
  "kind": "recovery_request",
  "target": "opaque-testbed-target",
  "inner_state": "semantic_unavailable",
  "observed": "interactive desktop session is absent",
  "requested_capability": "host.hypervisor.screenshot",
  "input_requested": false,
  "host_interference": "none",
  "suggested_next_step": "determine whether the guest is at the login screen"
}
```

The controller or a trusted orchestration policy decides whether to invoke the
outer provider. A request does not itself grant the route.

### Observation before outer input

Outer input requires a fresh outer observation, an exact target, a declared
coordinate space, and a reason. It must fail closed when target identity or
geometry is ambiguous.

### No silent route escalation

An inner action may recommend a foreground, protected, or outer route, but it
does not take that route automatically. This applies even when the higher route
would probably make the action succeed.

### Report host interference

Capabilities and results should classify host impact:

- `none`: no controller-desktop interaction;
- `capture_only`: reads a host-visible surface without focusing it;
- `focus`: foregrounds a VM or remote-console window;
- `pointer`: moves or captures the controller pointer;
- `keyboard`: injects through the controller's active desktop;
- `exclusive`: temporarily captures input or prevents ordinary host use.

The controller can deny disruptive routes while the user is active.

## Expected testbed evolution

This document does not require rewriting the existing CLIs. Candidate
incremental safeguards are:

- expose a machine-readable `capabilities --json` with plane, route, and host
  interference;
- distinguish guest-local UI commands from outer recovery commands in tool
  adapters even if the underlying CLI remains compatible;
- require an explicit recovery context or lease for outer mutating commands;
- keep read-only `status`, `probe`, and non-focusing screenshots separately
  grantable;
- record actual route and reason in artifacts; and
- add conformance tests proving a worker cannot access outer input under its
  normal grant.

The first implementation should enforce this at the YA/testbed tool boundary.
Prompt instructions remain useful guidance, but they are not the authorization
mechanism.

### UI-less disruptive claims

**Decision:** Machine Control distinguishes an ordinary
target-use claim from an explicitly disruptive claim. Ordinary remains the
default. Host-visible VM screenshot, focus, pointer, keyboard, and exclusive
input operations require a live disruptive claim in addition to any
platform-owner prohibition. Acquisition uses an explicit `--disruptive` flag,
the existing required reason and claimant attribution, and the normal bounded
claim lifetime; it does not prompt again for every outer operation. The
authoritative adapter enforces the distinction so the common `testbed --`
escape cannot bypass it.

**Current:** The shared claim authority records and validates the use class.
The common client performs a typed disruptive preflight for known outer VM
commands, and the Windows, Linux, and macOS wrappers recheck it before provider
dispatch. An ordinary claim receives `disruptive_claim_required`; a disruptive
claim continues to the existing provider target, geometry, role, and
outer-UI-policy checks.

This is a cooperative safety interlock against accidental route selection, not
strong authorization against a same-user process with an unrestricted shell.
The claim result and status should disclose the disruptive class, reason,
holder, and expiry. Keep the existing claim `mode` as `exclusive`; represent
ordinary versus disruptive as a separate use class rather than overloading
exclusivity.

**Open — controller affordance:** A future supervising controller may notify
the user when disruptive access is requested or activated, require approval,
show a persistent active indicator, and offer immediate revocation. Machine
Control should expose enough structured state for that affordance, while the
coordination/controller UI owns presentation. The implemented interlock
remains UI-less and does not add a Rust GUI/notification dependency or
platform-native approval dialog to each testbed adapter.

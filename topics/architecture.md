# Architecture

## Decision

Machine control is a set of cooperating control planes with independent trust
and failure boundaries. It is not one privileged daemon and not one API that
forwards arbitrary commands to every host.

```text
                                  system under test
                                       |
controller user                       |
      |                               |
      v                               v
controller YA session       worker YA session / local agent
      |                         |                 |
      |                         |                 +-- desktop plane
      |                         +-------------------- administration plane
      |
      +-- coordination plane
      |     target discovery, delegate, observe, wait, steer, interrupt
      |
      +-- authoritative testbed on controller host
            |
            +-- outer plane: lifecycle, bootstrap, framebuffer/HID, recovery
            +-- protected plane: optional narrow broker, when justified
```

The controller session, worker session, execution host, SUT, and testbed may
coincide, but the contract must not assume they do.

## Why the worker belongs inside

A guest-local worker can inspect the actual checkout, build outputs, process
tree, logs, application files, OS permissions, native accessibility APIs, and
desktop-session state without proxying all of that through the hypervisor. It
also receives platform-specific tools and instructions naturally.

This is most valuable on Windows, macOS, and Linux desktops. A worker outside
the guest tends to see only a remote shell plus pixels and must reconstruct
state that the guest already knows.

Some targets cannot host a worker. Stock iOS is the clearest case: a Mac worker
controls the phone through CoreDevice and a signed XCTest runner. Agent
placement therefore must remain separate from target identity.

## Failure independence

The inner and outer routes are both necessary precisely because neither is a
complete replacement for the other.

| Route | Strength | Fails when | Normal role |
| --- | --- | --- | --- |
| Guest administration | Rich system state and deterministic non-UI work | Guest agent/SSH/service or OS is unavailable | Build, install, files, processes, logs |
| Guest semantic desktop | Rich UI structure and targeted actions | No interactive session, permissions missing, accessibility broken, guest hung | Ordinary application testing |
| Guest protected broker | Can cross a narrowly defined privilege/session boundary | Broker absent, unarmed, incompatible, or policy refuses | Exceptional protected capability |
| Host hypervisor/device | Survives many guest failures | Host provider unavailable or physical transport absent | Startup, bootstrap, recovery, independent oracle |
| Hardware KVM | Independent of target OS and software | No capturable output/HID path or hardware unavailable | Physical bootstrap/recovery and pixels/HID oracle |
| Human | Can resolve credentials, consent, and physical ambiguity | User unavailable | Explicit gate, never a silent automated fallback |

Outer independence is valuable, but its ordinary use is costly: it may focus
the VM application, move the host pointer, inject global keys, capture the
controller's input, and disturb unrelated work. The architecture therefore
restricts outer access rather than merely ranking it last in documentation.

## Trust boundaries

### YepAnywhere coordination

YA authorizes which peer may create a worker, which project/provider/permission
ceiling is allowed, and which supervision operations are available. It does not
grant arbitrary target filesystem paths or generic access to a peer's local
REST surface.

### Guest worker

The worker receives only tools suitable for its task and placement. On a
desktop guest this normally includes the administration and semantic desktop
planes. It does not receive hypervisor/KVM tools by default.

### Authoritative testbed

The testbed owns exact device/VM selection, lifecycle transitions, bootstrap,
leases, recovery, and target-specific safety. The coordination layer invokes a
bounded testbed adapter; it does not reimplement those policies.

### Protected broker

A protected broker is optional, separately installed, and narrowly typed. It
can report or perform capabilities such as input-desktop state or approved
secure-desktop capture/input. It must not expose arbitrary command execution,
service management, registry access, or the entire user-session tool registry.

## Common contract boundary

The useful common surface covers:

- capability and state discovery;
- scoped semantic and visual observation;
- application/window/element actions;
- declared coordinate spaces;
- route, delivery, effect, evidence, and uncertainty;
- explicit recovery requests;
- cancellation, revocation, and cleanup.

It should not absorb:

- YA peer pairing or worker transcripts;
- arbitrary shell and filesystem protocols;
- hypervisor-specific lifecycle policy;
- product-specific pass/fail assertions;
- credentials or generic protected authorization.

The first goal is common terminology and conformance, not a new network daemon.

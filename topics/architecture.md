# Architecture

Topic: `architecture`

Status: active architecture contract.

## Decision

Machine control is a set of cooperating control planes with independent trust
and failure boundaries. It is not one privileged daemon and not one API that
forwards arbitrary commands to every host.

```text
authorized outside agent -------- authenticated transport -------+
                                                                  |
target-local agent -------------------- local IPC ----------------+-->
                                                                      target controller
                                                                        - administration adapters
                                                                        - user-session companion
                                                                        - optional protected broker

controller YA session ----- optional delegation -----> target-local YA worker
        |
        +----- authoritative testbed ----------------> outer lifecycle/recovery
```

The controller session, worker session, execution host, SUT, target controller,
and testbed may coincide, but the contract must not assume they do. In
particular, control implementation placement and agent placement are separate:
an outside agent must be able to call the target controller without spawning a
target-local worker first.

## Why control belongs with the target

A target-local controller can inspect the real process tree, applications, OS
permissions, native accessibility APIs, displays, and interactive-session
state. It can capture and inject within the target rather than focusing a VM
window on the controller host. Those properties hold whether its caller is a
local worker or an authorized agent elsewhere.

A target-local worker adds value when a task needs the checkout, build outputs,
debugger, platform-specific instructions, or an agent-coupled provider such as
Computer Use. It should call the same controller through local IPC. It is not a
prerequisite for ordinary remote control and must not be the only way an
outside session obtains semantic UI, screenshots, or input.

Some targets cannot host a worker. Stock iOS is the clearest case: a Mac worker
controls the phone through CoreDevice and a signed XCTest runner. Agent
placement therefore must remain separate from target identity.

ChromeOS demonstrates the desired desktop shape today: the caller is normally
outside, SSH carries requests, and `chrome.automation`, CDP, capture, and input
all execute on the Chromebook. Windows, macOS, and Linux should preserve that
shape with their own native facilities.

## Resident component shape

**Proposal:** The Windows vertical slice should validate a small set of
components rather than one omnipotent daemon:

1. A stable installed target service owns identity, authenticated local/remote
   sessions, capabilities, cancellation, revocation, and routing.
2. A normal-user companion in the interactive session owns UI Automation,
   screen/window capture, guest-local input, clipboard, and session-scoped app
   operations.
3. A narrow privileged broker exists only for explicitly authorized operations
   that cannot safely run in the companion. Its methods are typed capabilities,
   not arbitrary command execution or a privileged mirror of the whole API.
4. Administration adapters use the strongest existing OS mechanisms for shell,
   files, packages, processes, services, deployment, and logs.

The exact process boundary is platform-specific. macOS may need a stable signed
helper so Accessibility, Screen Recording, Input Monitoring, and TCC approvals
attach to a durable identity. Linux must bind to the correct desktop and D-Bus
session. ChromeOS already distributes the equivalent functions across SSH and
target-local helpers. The common contract should describe the capabilities,
not insist that every platform use the same number of processes.

## One contract, multiple facades and transports

**Decision:** The project owns one versioned ergonomic contract, independent of
how calls arrive. A local socket or named pipe, SSH, vsock, an authenticated
network tunnel, a CLI, SDK, or MCP facade may all expose it. None of those
transports or facades is itself the authorization boundary.

Local and remote sessions must negotiate the same capability vocabulary and
receive the same result semantics. Remote transport may add latency, streaming,
or artifact handles; it must not reduce the outside caller to pixels when the
resident provider has semantic control. Public target names and YA session IDs
must not double as private bearer authority.

Do not freeze the wire protocol before the Windows slice exercises it. Do
preserve the separation now so a proprietary agent protocol, a convenient MCP
server, or an initial SSH command format cannot become the architecture by
accident. Large screenshots and other binary artifacts should be streamable or
addressable by bounded handles rather than requiring base64 inside every tool
result.

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

The same-user boundary is not a strong security boundary when the worker also
has a shell: it can generally reach whatever that user can reach. Per-tool
policy is still useful for ergonomics and accidental misuse, but stronger
containment requires a different OS identity, sandbox, isolated test appliance,
or authorization component outside the worker's authority.

### Authoritative testbed

The testbed owns exact device/VM selection, lifecycle transitions, bootstrap,
leases, recovery, and target-specific safety. The coordination layer invokes a
bounded testbed adapter; it does not reimplement those policies.

### Protected broker

A protected broker is optional, separately installed, and narrowly typed. It
can report or perform capabilities such as input-desktop state or approved
secure-desktop capture/input. It must not expose arbitrary command execution,
service management, registry access, or the entire user-session tool registry.

## Deployment safety profiles

The North Star is full practical control, but the correct authorization posture
depends on what kind of machine is being controlled.

### Dedicated test appliance

A disposable VM or dedicated physical test machine may intentionally arm a
strong resident controller, including narrowly defined protected operations.
Isolation and rebuildability are major parts of its safety boundary. The
unrestricted profile is selected by trusted installation or launch policy; an
agent must not be able to widen a personal-machine profile with request fields,
environment variables, or command-line arguments.

### Personal or shared workstation

Ordinary control runs with the interactive user's authority. Protected or
disruptive capabilities require a visible, bounded grant that identifies the
target, capability, scope, expiry, and current target generation and can be
revoked independently. A trusted authorization host or equivalent OS boundary
may issue such a lease; the ordinary shell-capable agent cannot approve its own
elevation. Lock state, credentials, consent, and secure-desktop operations
remain separate capabilities rather than consequences of a generic “admin”
flag.

Both profiles use the same control vocabulary and report their real privilege
and restrictions. Personal-machine safety must not redefine the project into a
weak controller, and test-appliance power must not silently leak into personal
deployments.

## Common contract boundary

The useful common surface covers:

- version/session lifecycle, health, cancellation, leases, and revocation;
- capability and state discovery;
- scoped semantic and visual observation;
- application/window/element actions;
- declared coordinate spaces;
- route, delivery, effect, evidence, and uncertainty;
- explicit recovery requests;
- artifact and resource cleanup.

It should not absorb:

- YA peer pairing or worker transcripts;
- arbitrary shell and filesystem protocols;
- hypervisor-specific lifecycle policy;
- product-specific pass/fail assertions;
- credentials or generic protected authorization.

The first implementation goal is a Windows target-resident vertical slice with
local and remote facades, not a speculative universal network protocol. Its
contract and conformance behavior should be reusable across later providers.

# Glossary

The same word—especially *host*, *session*, or *target*—can refer to several
different things in this system. Use the terms below in new documents and
interfaces.

## People and agent sessions

**Controller user**  
The human supervising the overall development or test campaign.

**Controller session**  
The YA agent session that plans the campaign, selects systems under test,
creates delegated workers, observes their progress, and requests outer
recovery when necessary. It remains on its original YA peer.

**Worker session**  
A normal YA session created on another authorized YA peer for a bounded task.
It has its own provider process, transcript, tools, cwd, permissions, and YA
session ID.

**Delegation handle**  
The controller's durable supervision relationship to one worker session. It
records worker identity and state; it is not the worker's public session ID and
not a machine-control target.

**Agent placement**  
The decision about where a worker agent executes. Placement is independent of
which machine or device the worker controls.

## Machines and identities

**YA peer**  
A YepAnywhere server with a stable server identity and directional delegation
grants. A route, relay username, browser-saved host, and YA peer are not the
same identity.

**Execution host**  
The OS environment in which the agent provider and worker process run.

**System under test (SUT)**  
The machine, VM, desktop session, application, browser, phone, headset, or
other device whose behavior is being verified.

**Control target**  
The provider-specific object addressed by a machine-control operation. It may
be a whole machine, desktop, application, window, accessibility snapshot, UI
element, or attached device.

**Controller host**  
The machine physically or logically attached to a VM hypervisor or device. It
may host the controller session, but that is not required.

**Testbed ID**  
The stable inventory name for an authoritative testbed, such as `winvm` or
`ios`. It identifies a configured control environment, not necessarily a YA
peer or a single UI session.

## Control planes

**Coordination plane**  
YepAnywhere operations for target discovery, delegation, worker supervision,
steering, attention, results, interruption, and cleanup.

**Administration plane**  
Files, commands, processes, packages, services, logs, build tools, deployment,
and OS facts. This normally uses an in-guest shell, guest agent, SSH, PowerShell,
or another non-UI channel.

**Desktop plane**  
Application/window discovery, semantic UI snapshots, element actions, text
entry, screenshots, and bounded pointer/keyboard input in an interactive user
session.

**Protected plane**  
Narrow operations requiring authority outside the normal user desktop, such as
truthful lock/input-desktop state, companion bootstrap, or explicitly approved
secure-desktop capture/input. It must not become a generic privileged shell.

**Outer plane**  
Control independent of the target user session: hypervisor lifecycle and
console, hardware KVM capture/HID, device-host tooling, or another external
recovery channel.

## Providers and routes

**Provider**  
An implementation of some control capabilities. A provider advertises what it
can currently do, its restrictions, and the routes it may use.

**Target controller**

The target-native service boundary that presents administration, semantic,
visual, input, application/session, and explicitly authorized protected
capabilities through a common contract. Local and remote agents may call it;
it is not itself a YA worker, hypervisor console, or one platform adapter.

**User-session companion**

A target-resident process in the interactive desktop session that can use the
platform's semantic, capture, input, clipboard, window, and application APIs.
It may be supervised by a service, but does not inherit protected authority
merely because a service launched it.

**Inner provider**  
A provider running in or through the target OS. It usually has the richest
semantic state but depends on the guest OS, an interactive session, permissions,
and guest IPC being healthy.

**Outer provider**  
A provider independent of the target user session, such as UTM/Tart console
control, a hardware KVM, CoreDevice, or USB HID. It is usually more resilient
and less semantic.

**Protected broker**  
A separately installed and authenticated component exposing only narrowly
typed protected capabilities. It is not directly agent-facing.

**Authorization lease**

A bounded, expiring, revocable grant for a protected or disruptive capability.
It binds the caller, target and provider generation, capability, scope, and
relevant session/desktop state. A target selector or generic admin flag is not
an authorization lease.

**Target-use claim**

An exclusive, expiring coordination lease on an exact machine or workspace.
It records bounded caller-supplied attribution and a reason, but does not grant
a protected capability or authenticate self-asserted metadata. Its ordinary
use class is sufficient for target-native control; an explicit disruptive
class is required for governed host-visible VM capture or injected input.
Workspace ownership and target-use claiming are separate facts.

**Route**  
The actual mechanism used for an operation. Initial route classes are
`guest.admin`, `guest.user`, `guest.broker`, `host.hypervisor`, `host.device`,
and `human`. Provider-specific routes, such as `windows.uia` or `ios.xctest`,
refine those classes.

**Inner-first routing**  
The policy that ordinary development and testing use guest administration and
guest semantic control. Outer operations are reserved for startup, bootstrap,
independent diagnosis, and recovery.

**Silent fallback**  
A provider changing route, focus impact, privilege, scope, or fidelity without
the caller explicitly authorizing that change. Silent fallback is prohibited.

**Host interference**  
An operation's effect on the controller user's desktop: focusing a VM window,
moving the host pointer, capturing input, typing through the host GUI, or
otherwise disturbing unrelated work.

## State and observations

**Semantic snapshot**  
A bounded representation of accessible UI state: applications, windows,
roles, labels, values, states, bounds, actions, and hierarchy. It is not a
pixel image.

**Snapshot-scoped reference**  
An opaque UI-element token valid only for a particular snapshot/generation.
Navigation, window recreation, process changes, or resnapshotting may make it
stale.

**Visual observation**  
A screenshot or framebuffer capture from a declared scope and coordinate
space.

**Independent oracle**  
An observation route separate enough from the action route to provide credible
evidence of an effect. An outer screenshot can be an oracle for an inner action;
the API response from the same input injector is not necessarily one.

**Delivery**  
Whether and how an action was sent. Delivery does not prove that the intended
state changed.

**Effect**  
The observed application or system-state consequence of an action.

**Effect evidence**  
The bounded semantic, visual, process, file, log, or application-specific
observation supporting an effect conclusion.

**Unknown outcome**  
The action may or may not have occurred, often because transport failed after
dispatch. Mutating actions with unknown outcomes must not be retried blindly.

**Recovery request**  
A structured worker or provider report that inner control is unavailable and
that an outer route may be needed. It states observed failure, requested outer
capability, likely host interference, and whether user approval is required.

**Human gate**  
A boundary requiring direct human action, such as entering a personal password,
performing biometrics, approving account recovery, or resolving a physical
condition that no authorized provider can safely handle.

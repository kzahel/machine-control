# Open Questions and First Slice

## Settled direction

- YepAnywhere delegation is the initial cross-host orchestration mechanism.
- Desktop control is implemented at the target and is directly reachable by
  authorized local or remote callers through the same conceptual interface.
- Workers run inside desktop targets when local build/debug context or an
  in-target-only provider makes that useful; they are not a control
  prerequisite.
- Existing testbed repositories retain lifecycle, bootstrap, recovery, and
  target-specific safety ownership.
- Dotfiles remains discovery/availability, not an operation proxy.
- Ordinary workers receive guest administration and guest semantic control,
  not host/hypervisor input.
- Outer control is startup/bootstrap/recovery and independent observation.
- Cua is a reference and optional provider, not the required foundation.
- Agent Device remains the current iOS semantic provider behind the iOS
  testbed wrapper.
- ChromeOS is the current reference for rich outside access to target-native
  administration, semantics, capture, and input.
- The Windows-first slice should build the resident control shape and validate
  local and remote facades before freezing a universal wire protocol.

## Highest-priority open questions

### What is the Windows resident component boundary?

Validate the smallest repeatable target appliance that can provide:

- a stable installed service identity and authenticated local/remote sessions;
- a companion in the interactive user session for UIA, capture, and input;
- administration adapters and health visible to the outer testbed;
- optional, narrowly typed protected operations under an explicit profile or
  lease; and
- recovery after reboot, logout, lock, user switching, or provider crash.

The implementation may initially use WinApp, PowerShell, SSH, Cua, or other
existing pieces behind the facade. The product boundary is the target
controller, not any one adapter.

### How is inner-first policy enforced?

The preferred initial answer is tool grants at the YA coordination/testbed
adapter boundary. A worker receives no outer mutating tools. We still need to
decide:

- whether read-only outer screenshots are normally visible;
- what constitutes an active recovery context or lease;
- whether host activity can automatically deny focus/pointer/keyboard routes;
- how a worker emits and a controller resolves a recovery request; and
- where route/interference audit records live.

### Where does YA run in each guest?

Once direct resident control works, decide the smallest repeatable YA worker
appliance: server lifecycle, provider credentials, checkout discovery, relay
identity/pairing, and readiness. The worker should be a normal target-owned YA
session, not an SSH-spawned process whose transcript is copied back as if
local. This question must not block outside use of the resident controller.

### What is the adapter boundary?

Do not prematurely require every testbed to rename its CLI. First determine
whether a small adapter can project:

- target and capability inventory;
- independent state dimensions;
- route and host-interference metadata;
- worker-safe versus controller-only operations;
- structured results and recovery requests; and
- artifact references.

### Who can perform outer recovery?

Likely choices are the controller session, a narrow deterministic YA service,
or an explicitly delegated recovery worker on the controller host. The worker
inside the failing guest must not hold the only recovery authority.

### How are protected brokers introduced?

Windows provides the strongest use case. Start with an explicit dedicated test
appliance profile and add a SYSTEM broker only for concrete operations the
user-session companion cannot perform. It needs separate arming, authenticated
peers, request/target/generation binding, expiry, revocation, and conformance
tests. It should never become a privileged copy of the whole desktop API.

For personal/shared machines, same-user policy is not containment when an agent
also has a shell. Decide which OS identity, sandbox, or external authorization
host can issue protected leases without being writable by the agent itself.

### How are artifacts exchanged?

Worker results need stable references to screenshots, logs, traces, builds,
and reports owned by the target YA/testbed. Decide when the controller receives
content, a redacted summary, a downloadable handle, or only target-local
provenance.

## Recommended first integration slice

Use Windows because its existing testbed already has useful administration,
WinApp semantics, and independent outer recovery, while its session and
integrity boundaries expose the hard cases:

1. Create a clean Windows installation through the authoritative testbed and
   bootstrap a stable resident service plus interactive-session companion.
2. Expose capability/state discovery, UIA snapshots/actions, guest-local
   screenshots/input, and administration behind one target-oriented facade.
3. Exercise that facade from an authorized outside agent without spawning a
   Windows agent and without focusing the VM window.
4. Exercise the same contract locally from a Windows process or worker; only
   transport and target selection should differ.
5. Validate snapshot-scoped references, explicit coordinates, observation
   epochs, action/effect evidence, degraded capabilities, and restart/revoke.
6. Cover normal, elevated, locked, logged-out, user-switched, and secure-desktop
   states with truthful results. Add only the narrow protected route the test
   appliance actually requires.
7. Deliberately disable resident control, emit a structured recovery request,
   and let the controller use the independent outer route to diagnose/repair it.
8. Install YA/Computer Use in the guest as optional providers and verify that
   their presence improves selected tasks without becoming the only interface.
9. Let automation validate, shut down, and seal or snapshot the image so the
   golden image is an output of the process.

This slice validates the North Star itself: rich target-native control with the
same ergonomics from outside and inside, independent recovery, truthful
security boundaries, and no routine controller-desktop interference.

## Later questions

- Whether a common machine-control SDK becomes useful after adapters converge.
- Whether Cua should be retained as one provider or only as a conformance
  comparison.
- Whether a worker can move between peers or whether delegation remains the
  long-term preferred model.
- How multiple displays, RDP/console sessions, fast-user switching, and nested
  VMs are represented.
- Which physical machines warrant BMC, power, or hardware-KVM integration.
- Whether simulator and real-device routes should share one target ID with
  different capabilities or remain distinct targets.

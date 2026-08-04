# Open Questions and First Slice

## Settled direction

- YepAnywhere delegation is the initial cross-host orchestration mechanism.
- Workers run inside desktop targets when possible.
- Existing testbed repositories retain lifecycle, bootstrap, recovery, and
  target-specific safety ownership.
- Dotfiles remains discovery/availability, not an operation proxy.
- Ordinary workers receive guest administration and guest semantic control,
  not host/hypervisor input.
- Outer control is startup/bootstrap/recovery and independent observation.
- Cua is a reference and optional provider, not the required foundation.
- Agent Device remains the current iOS semantic provider behind the iOS
  testbed wrapper.
- Common work should begin with vocabulary, adapters, and conformance rather
  than a new daemon or frozen wire protocol.

## Highest-priority open questions

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

For desktop VMs, decide the smallest repeatable guest appliance:

- YA server lifecycle and auto-start policy;
- provider credentials and local security posture;
- target-local checkout discovery;
- guest URL/relay identity and pairing;
- readiness health used by the outer testbed; and
- behavior after reboot, logout, lock, or provider crash.

The worker should be a normal target-owned YA session, not an SSH-spawned
process whose transcript is copied back as if local.

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

Windows provides the strongest use case, but a SYSTEM broker should follow—not
precede—a working delegated inner/outer flow. It needs a concrete capability,
separate arming, peer authentication, request binding, and conformance tests.
It should never become a privileged copy of the whole desktop API.

### How are artifacts exchanged?

Worker results need stable references to screenshots, logs, traces, builds,
and reports owned by the target YA/testbed. Decide when the controller receives
content, a redacted summary, a downloadable handle, or only target-local
provenance.

## Recommended first integration slice

Use Windows because the existing testbed already has rich inner and outer
routes and makes session boundaries obvious:

1. Add or wrap a read-only machine-capability description for WinVM.
2. Start the VM through the authoritative outer testbed.
3. Wait for a YA peer inside Windows to become ready.
4. Delegate a bounded application test to a Windows worker.
5. Give that worker PowerShell and WinApp semantic tools, but no UTM input.
6. Return semantic evidence to the controller.
7. Deliberately stop or disable the inner UI provider.
8. Have the worker emit a structured recovery request.
9. Let the controller capture outer state and restore the inner provider.
10. Verify that no ordinary worker action focused UTM, moved the Mac pointer,
    or typed through the controller desktop.

This slice validates agent placement, delegation, capability projection,
inner-first enforcement, recovery escalation, and result exchange. It gives
more architectural evidence than beginning with a protected broker.

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

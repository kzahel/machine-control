# Capabilities and Results

Topic: `capabilities-and-results`

Status: proposal for common vocabulary, not a frozen wire protocol.

The common layer should let coordination and agents reason about heterogeneous
providers without claiming that all platforms have equivalent behavior.

## Contract and session envelope

Local IPC, SSH, an authenticated tunnel, CLI/SDK calls, and MCP are facades or
transports for the same conceptual contract. A session handshake should expose
at least contract version, target identity and generation, provider/build
identity, authenticated caller scope, current capabilities, and artifact
transfer limits. Public target names, snapshot IDs, and YA session IDs are not
authorization credentials.

The lifecycle needs explicit health, cancellation, lease expiry, revocation,
and session cleanup. Reconnect must not silently preserve stale element
references or protected authority across a target/provider generation change.

## Capability description

A capability should report more than supported/unsupported:

```json
{
  "capability": "desktop.semantic.snapshot",
  "state": "native",
  "plane": "desktop",
  "route_class": "guest.user",
  "provider_route": "windows.uia",
  "scope": ["interactive_user"],
  "requires": ["logged_in", "ui_relay_healthy"],
  "known_omissions": [],
  "host_interference": "none",
  "mutating": false
}
```

Candidate capability states:

- `native`: directly supported through the intended platform facility;
- `emulated`: synthesized from another mechanism with known differences;
- `experimental`: present but version-sensitive or incompletely validated;
- `degraded`: currently usable with material omissions;
- `unavailable`: normally supported but not currently reachable/authorized;
- `unsupported`: no implementation for this target/provider.

## Independent state dimensions

Do not overload one `session_state`. At minimum keep these dimensions separate:

```text
power_state       = off | starting | running | suspended | unknown
admin_state       = ready | degraded | unavailable | unknown
desktop_state     = unlocked | locked | secure_desktop | no_session | unknown
semantic_state    = ready | degraded | unavailable | unknown
agent_state       = reachable | starting | busy | waiting | unavailable
outer_state       = ready | observation_only | unavailable | unknown
```

Platforms can refine these values, but must not report a policy label such as
“desktop allowed” as evidence that the real OS desktop is unlocked.

## Observation results

Every observation identifies:

- SUT and provider;
- actual route and scope;
- timestamp/epoch and freshness;
- process, app, window, display, or device identity as applicable;
- coordinate space and conversion metadata for images/bounds;
- omissions, truncation, degradation, or permission failures; and
- snapshot/generation IDs for semantic references.

A sparse accessibility tree is degraded output, not proof that the screen has
no controls.

When a screenshot and semantic tree claim to describe the same state, the
provider should return them from one observation epoch or say that they may
have drifted. Element and window references should bind enough identity—such
as target generation, snapshot, process, native window ID, and provider
instance—to reject a plausible-looking reference that now names a different
object.

## Action results

An action result separates acceptance, delivery, effect, and evidence:

```json
{
  "request_id": "opaque-id",
  "accepted": true,
  "actual_route": "guest.user/windows.uia",
  "delivery": "confirmed",
  "effect": "confirmed",
  "host_interference": "none",
  "evidence": [
    {
      "kind": "semantic_state",
      "summary": "checkbox value changed from false to true"
    }
  ],
  "retry_safety": "not_needed",
  "escalation": null
}
```

Candidate effect states:

- `confirmed`: independent evidence matches the intended result;
- `partial`: some, but not all, expected state changed;
- `no_effect`: delivery was observed but the intended state did not change;
- `unverifiable`: delivery may be known but no credible effect oracle exists;
- `unknown`: transport or process failure leaves both delivery/effect uncertain;
- `refused`: policy, capability, stale target, state, or platform behavior
  prevented dispatch.

Mutating actions with `unknown` outcome must not be replayed automatically.
The next step is observation and reconciliation.

Refusals should use stable machine-readable reasons such as stale reference,
capability unavailable, wrong session/desktop, authorization required, policy
denied, target generation changed, or unsupported state. Human-readable error
text alone is not sufficient for safe route selection or recovery.

## Route escalation

An operation may return a proposed next route:

```json
{
  "escalation": {
    "route_class": "host.hypervisor",
    "capability": "screen.capture",
    "reason": "guest semantic provider is unreachable",
    "host_interference": "capture_only",
    "requires_controller": true
  }
}
```

The result remains a recommendation. Coordination or the controller explicitly
authorizes the next operation.

## Conformance themes

Providers should eventually be tested for:

- truthful capability/state reporting;
- stale-ref rejection;
- explicit coordinate spaces;
- background/foreground and host-interference honesty;
- unknown-outcome behavior;
- observation after mutation;
- no silent privilege or outer-route escalation;
- revocation and cleanup; and
- recovery independence.

Conformance should use small deterministic native and web fixtures with state
that can be checked independently of the action provider. Event-aware waits,
postconditions, and bounded retries are preferable to fixed sleeps; retries
must still respect unknown outcomes and action idempotency. Test reports should
pin the environment and distinguish provider behavior from fixture or transport
failure.

Existing provider-specific commands do not need to adopt one wire format
immediately. A thin adapter can first project their behavior into this
vocabulary and expose gaps.

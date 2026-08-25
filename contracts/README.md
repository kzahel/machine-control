# Machine-control contract projections

This directory owns the exercised JSON projection used by resident desktop
implementations. It is deliberately a small, evolving facade contract rather
than a frozen cross-device wire protocol.

- [`request-v0.schema.json`](request-v0.schema.json) describes the common
  request envelope and currently exercised desktop fields.
- [`result-v0.schema.json`](result-v0.schema.json) describes the truthful
  result envelope shared by the Windows, macOS, and Linux slices.
- [`doctor-v0.schema.json`](doctor-v0.schema.json) describes the minimized,
  independent readiness dimensions emitted by authoritative testbeds. Desktop
  targets report desktop/resident state; device targets report connection,
  boot, interaction, and runner state without pretending those processes are
  identical. Its optional lifecycle extension reports suspend availability,
  reasons, and the provider's default down action without implying that an
  unavailable operation is safe.
- [`targets-v0.schema.json`](targets-v0.schema.json) describes ignored local
  target selection. It contains adapter commands, never bearer authority.
- [`claim-capabilities-v0.schema.json`](claim-capabilities-v0.schema.json)
  describes exclusive exact-resource claim policy, ordinary/disruptive use
  classes, duration bounds, claimant attribution limits, and queueing behavior.
- [`claim-result-v0.schema.json`](claim-result-v0.schema.json) describes claim
  acquisition, use class, status, validation, renewal, release, and typed
  conflicts without exposing the concrete provider identity.
- [`workspace-capabilities-v0.schema.json`](workspace-capabilities-v0.schema.json)
  describes provider-neutral persistent, isolated, and candidate workspace
  support without naming the hypervisor or a concrete VM.
- [`workspace-result-v0.schema.json`](workspace-result-v0.schema.json) describes
  acquire, inventory, release, and garbage-collection dry-run results. Its
  handles are opaque selectors backed by private provider receipts, not bearer
  authority. Accepted VM acquisition also carries the exact workspace's public
  target-use claim descriptor.
- [`candidate-assertion-v0.schema.json`](candidate-assertion-v0.schema.json)
  is the minimized adapter-to-client proof of an exact candidate role, power
  state, and absence of workspace ownership. It intentionally omits the
  provider identity itself.
- [`maintenance-capabilities-v0.schema.json`](maintenance-capabilities-v0.schema.json)
  describes read-only discovery of explicit platform audit, repair, and
  exact-source certification operations. Profiles and operations may be
  unavailable when a physical target does not have an appliance image.
- [`maintenance-result-v0.schema.json`](maintenance-result-v0.schema.json)
  is the common minimized projection of validated platform-owned maintenance
  evidence. It omits private boot, service, endpoint, and staging details.

Platform adapters may add fields under the permissive schema while the corpus
is still v0. They may not omit route, generation, delivery/effect separation,
host interference, uncertainty, or typed refusal merely because an upstream
provider uses a different response shape.

The physical-iOS adapter now returns this result envelope for its explicitly
iOS application and XCTest operations. `generation: unavailable` is honest
when CoreDevice supplies no public boot generation; semantic payloads preserve
Agent Device's provider-scoped `refsGeneration` instead of fabricating a
target generation.

Transport is outside these schemas. Local IPC, a CLI, SSH, `tart exec`, an
authenticated carrier, and MCP may all carry the same request and result.
The current dependency-free projection is
[`bin/machine-control`](../bin/machine-control); its adapter tests and guarded
three-desktop workflow are documented in
[`tests/client`](../tests/client/README.md).

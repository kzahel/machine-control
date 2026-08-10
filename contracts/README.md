# Machine-control contract projections

This directory owns the exercised JSON projection used by resident desktop
implementations. It is deliberately a small, evolving facade contract rather
than a frozen cross-device wire protocol.

- [`request-v0.schema.json`](request-v0.schema.json) describes the common
  request envelope and currently exercised desktop fields.
- [`result-v0.schema.json`](result-v0.schema.json) describes the truthful
  result envelope shared by the Windows and macOS slices.

Platform adapters may add fields under the permissive schema while the corpus
is still v0. They may not omit route, generation, delivery/effect separation,
host interference, uncertainty, or typed refusal merely because an upstream
provider uses a different response shape.

Transport is outside these schemas. Local IPC, a CLI, SSH, `tart exec`, an
authenticated carrier, and MCP may all carry the same request and result.

# Sky Computer Use

Maintainer: OpenAI. Role: proprietary ChatGPT/Codex desktop Computer Use
implementation and optional architecture benchmark, not a required provider.

## License and provenance

The installed Computer Use plugin declares **Proprietary**. No separate
open-source license grant was found in the bundled `@oai/sky` package manifest;
do not infer one from its readable JavaScript. The separate Codex repository
declares Apache-2.0, which does not relicense the desktop service or runtime.
No proprietary code or assets are adopted. Exact versions, source revision,
artifact hashes and inspection paths live in the
[spike review](../../../machine-control-spike/docs/sky-caller-authorization.md).

## Evidence and architecture

**Current (2026-10-03):** `source-reviewed` for the distributed Mac JavaScript
transport and approval wrapper, supplemented by static native control-flow reconstruction.
Bounded native discovery and connection rejection are now `live-tested` on a
physical Mac with explicit user authorization. Full caller isolation and
desktop effects are not conformance-tested here.
[Official documentation](https://learn.chatgpt.com/docs/computer-use) describes
macOS and Windows support; this authorization review covers only macOS.

| Layer | Finding | Evidence limit |
| --- | --- | --- |
| Local transport | Host-provided native-pipe bridge to a Unix-domain socket; framed JSON-RPC with version negotiation, deadlines and turn metadata | Direct distributed-JS inspection; no password/token in the inspected request envelope |
| Native caller identity | Socket admission reads OS peer audit token, checks signing publisher, then parent/relay ancestry; live Python connections close before request bytes | Predicate reconstructed from pinned native binary; bounded live rejection, not comprehensive isolation |
| Runtime provenance | NativePipeBroker owns native connect/write/close; signed Node launched under the agent shell fails admission | Direct native connect statically traced; immediate-parent restrictions explain why an arbitrary signed ancestor is insufficient |
| App approval | JS obtains app policy and requests host approval with session/always persistence | Source-reviewed; official docs describe saved per-app approval separately from OS consent |
| Open-source integration | Codex includes feature/configuration, app policy and MCP integration | Native Sky transport/authentication implementation was not located in the inspected Rust checkout |

**Current:** After the initial static review, the supported CUA inventory call
started the service. Its executable matched the inspected artifact. The socket
and parent directory were current-user-owned, mode `0600` and `0700`. Native
app discovery passed before and after raw Python/signed-Node probes were
disconnected. A zero-byte connection also closed immediately, and service logs
reported sender authentication failure. No capture, input, app approval or
permission change was requested. The spike owns process-tree, framing and
cleanup detail; private inventory and raw logs are not retained.

### Reconstructed admission boundary

**Current, static native review:** the normal path is JS tool → native runtime
broker → Unix socket → service admission. The broker is a runtime component;
its Mac connect routine opens the socket directly. A separate broker daemon or
per-connection helper launch was not found in that routine.

The service obtains peer identity from the OS rather than trusting a PID or
session name in request JSON. It first checks the peer's signing publisher.
It then requires a trusted immediate parent, or an allowed signed Node relay
parent with a trusted ancestor. The bounded ancestor walk has an eight-parent
limit. An explicit alternate integration is also recognized. The spike records
the requirement initializers, branch interpretation and exact binary anchors.
A signed interpreter with an ordinary shell parent does not meet these rules
merely because Codex appears farther up its process tree.

**Current:** no short-lived client token exchange was found in that admission
flow. The macOS audit token is OS-provided process identity, not a bearer secret
sent by the agent. Per-app approval and OS Accessibility/Screen Recording
permissions remain separate layers.

**Open:** signing-information comparisons were traced, but a
`SecCodeCheckValidity` call was not found in the inspected path. Do not equate
that with a proved signature-validity policy or infer a bypass. Full protection
against process replacement, PID races, cached identity, misuse of the trusted
runtime, other transports and a hostile same-user shell remains unverified.
Neither the inspected admission routine nor live discovery establishes
session-specific cryptographic authority or revocation behavior.

## Fit and next evidence

**Decision:** Use the separation between native caller authentication,
app-specific consent and agent tool advertisement as a design benchmark.
Machine Control must retain an agent-neutral interface and authenticated
local/remote access; an OpenAI-only identity policy would not satisfy that
goal. [Caller authorization](../../topics/caller-authorization.md) owns the
high-priority design investigation.

**Open:** In an isolated authorized test environment, independently test the
reconstructed admission branches, supported runtime launch provenance, reconnect,
process replacement and revocation. Audit the trusted bridge as a potential
confused deputy and establish whether native authorization is bound to a session.
Fresh-install and full desktop-action evidence remain absent from this review.

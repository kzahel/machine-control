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
[caller spike review](../../../machine-control-spike/docs/sky-caller-authorization.md)
and [external MCP experiment](../../../machine-control-spike/docs/sky-mcp-external-host.md).

## Evidence and architecture

**Current (2026-10-03):** `source-reviewed` for the distributed Mac JavaScript
transport and approval wrapper, supplemented by static native control-flow reconstruction.
Bounded native discovery, runtime bridge placement, version-ping admission and
an external MCP host operating TextEdit are `live-tested` on a physical Mac
with explicit user authorization. The TextEdit test includes an independent
saved-file effect check; full isolation and platform conformance remain open.
[Official documentation](https://learn.chatgpt.com/docs/computer-use) describes
macOS and Windows support; this authorization review covers only macOS.

| Layer | Finding | Evidence limit |
| --- | --- | --- |
| Local transport | Host-provided native-pipe bridge to a Unix-domain socket; framed JSON-RPC with version negotiation, deadlines and turn metadata | Direct distributed-JS inspection; no password/token in the inspected request envelope |
| Native caller identity | Socket admission reads OS peer audit token, checks signing publisher, then parent/relay ancestry; live Python connections close before request bytes | Predicate reconstructed from pinned native binary; bounded live rejection, not comprehensive isolation |
| Runtime topology | Ordinary worker uses named RPC; trusted service worker uses native bridge; socket peer is the native supervisor | Embedded-JS review and owned-endpoint live test; production sandbox not audited |
| Admission limit | Signed Node with an ordinary parent fails; signed Node with another signed Node parent receives a version reply | Repeated with a detached controller under launchd; desktop-action authorization remains untested |
| App approval | JS obtains app policy and requests host approval with session/always persistence | Source-reviewed; official docs describe saved per-app approval separately from OS consent |
| External MCP host | Installed launcher exposes persistent JavaScript with app bindings, semantic diffs and app approvals; TextEdit input verified from a saved file | Existing Mac consent/configuration reused; YA integration and fresh installation not tested |
| Open-source integration | Codex includes feature/configuration, app policy and MCP integration | Native Sky transport/authentication implementation was not located in the inspected Rust checkout |

**Current, initial discovery phase:** After the initial static review, the
supported CUA inventory call started the service. Its executable matched the inspected artifact. The socket
and parent directory were current-user-owned, mode `0600` and `0700`. Native
app discovery passed before and after raw Python/signed-Node probes were
disconnected. A zero-byte connection also closed immediately, and service logs
reported sender authentication failure. No capture, input, app approval or
permission change was requested. The spike owns process-tree, framing and
cleanup detail; private inventory and raw logs are not retained.

### Reconstructed admission boundary

**Current, static native review:** the normal path is JS tool → native runtime
broker → Unix socket → service admission. The broker is a runtime component;
its Mac connect routine opens the socket directly. An owned-endpoint probe
confirmed the OS-reported socket peer is the native `node_repl` supervisor,
not the trusted JavaScript worker. A separate per-connection helper was not
found in that routine.

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

### Runtime and launch provenance

**Current, source-reviewed / bounded live-tested:** the host launches the native
runtime through inherited MCP stdio and configures named trusted services.
Submitted JavaScript runs in an ordinary worker with named RPC, while a
separate trusted worker loads configured handlers and receives the native
bridge. File imports are restricted to canonical configured roots. A temporary
standalone MCP client could select an owned handler and prove the bridge's
socket owner without credentials or a production agent session. This measures
host-configured service loading, not control of an existing session; production
sandbox settings and all alternate ingress routes remain unreviewed.

**Current, bounded live-tested:** the publisher/parent rule has a concrete
limit. An owned script running in the bundled signed Node was rejected when
launched by Python. Adding a signed Node parent running an owned launcher
produced a valid service version reply. The same negative/positive pair held
with the Python controller detached under launchd, without a Codex/ChatGPT
ancestor in its ordinary process tree. This matches the reconstructed default
trusted-parent publisher rule. Responsible-process attribution was not tested.

This uses authentic executable identities; it is not signature forgery. It
also shows that this socket admission check does not establish an official
Codex session or the provenance of interpreted scripts. Only version pings were
sent in that ancestry experiment. The subsequent external-host test below
uses the normal policy wrapper; direct-native app-policy bypass and full
same-user isolation remain untested. No backend-issued session token was
needed for these replies.
The spike owns exact process topology, artifact pins, probe method and cleanup.

## MCP surface and external use

**Current, source-reviewed / bounded live-tested:** the installed `@oai/cua-repl`
launcher wraps native `node_repl` as a stdio MCP server. Its model-facing `js`
tool starts a persistent environment containing `cua`. App bindings expose
state, screenshots, semantic clicks, typing, keys and value setting; Mac state
uses indexed accessibility text and subsequent diffs. Bootstrap and first-use
documentation teach this interface. A legacy Sky skill is not the same API and
does not supply runtime installation or permission.

**Current:** installation is a component set, not just one service executable.
The desktop app contains signed Node, native runtime, module packages, launcher,
Sky service and a Codex CLI. The Codex home has a native-service copy and cached
plugin launch configuration in the inspected installation. Runtime-state folder
existence alone is not executable discovery. Version-specific locations and
hashes belong to the linked experiment. The native service may need a working
Codex app-server subprocess in addition to existing OS consent and host approval.

**Current, bounded live-tested:** an independent temporary MCP host accepted
only the user-authorized TextEdit app elicitation. Default service startup
failed because its Codex app-server exited; the built-in CUA tool failed the
same way. An owned service instance with an explicit installed Codex CLI path
and private socket passed the ordinary policy/approval workflow. It exposed
TextEdit state, operated File -> New, typed a marker and saved a test document.
An independent file conversion verified the exact text. The owned document was
closed and removed, prior formatting restored, and owned runtime/service
processes reaped. No MC runtime or YA agent session participated in that route.

**Current, limits:** one shortcut produced a formatting change instead of New;
menu actions provided the observed New effect. The Save As name field treated
a path as a literal filename; the actual owned file was verified and cleaned
up. These are useful reasons to retain independent effect checks. App menus
were observed and operated; system-wide menu coverage and keyboard-layout
fidelity were not established. Screenshot fidelity, native approval-bypass
resistance, revocation, fresh installation and model-performance comparisons
remain untested.

**Open:** the reviewed YA Codex adapter has no explicit MCP elicitation-request
handler. End-to-end integration must test app consent, decline/cancel,
persistence, tool and image output, lifecycle hooks and cleanup. The working
external host is feasibility evidence, not a completed YA feature or a promise
that the proprietary interface is stable or supported for third-party use.

## Fit and next evidence

**Decision:** Use the separation between native caller authentication,
app-specific consent and agent tool advertisement as a design benchmark.
Machine Control must retain an agent-neutral interface and authenticated
local/remote access; an OpenAI-only identity policy would not satisfy that
goal. [Caller authorization](../../topics/caller-authorization.md) owns the
high-priority design investigation.

**Open:** In an isolated authorized test environment, independently test the
remaining admission branches, production sandbox configuration, post-admission
desktop authorization, reconnect, process replacement and revocation. Audit
the trusted bridge as a potential confused deputy and establish whether native
authorization is bound to a session.
Fresh-install and full platform-action conformance remain open beyond the
bounded TextEdit workflow. [Provider landscape](../../topics/provider-landscape.md#optional-sky-provider-and-agent-facing-compatibility)
owns optional-provider and model-interface direction.

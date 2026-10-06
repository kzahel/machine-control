# Sky Computer Use

Maintainer: OpenAI. Role: proprietary ChatGPT/Codex desktop Computer Use
implementation and optional architecture benchmark, not a required provider.

This is the comprehensive entry point for the **observed macOS architecture
and security posture**. Evidence was collected on 2026-10-03 and consolidated
on 2026-10-04. It describes pinned installed artifacts, not a vendor security
specification or a guarantee about later releases. Exact inputs and experiment
records remain in the spike; implementation decisions remain in the topics.

**Current:** Sky has a real native process-identity admission check. It is not
just an obscure socket name. However, an admitted signed interpreter chain
does not prove an official Codex session or trusted script provenance. A
separate external MCP client also performed user-authorized TextEdit actions
through the genuine runtime and normal approval wrapper. These observations
do not establish unrestricted arbitrary-process desktop access, nor do they
establish hostile same-user containment.

Reading map:

- [Process and protocol map](#process-and-protocol-map): what runs where.
- [Approval and configuration ownership](#approval-and-configuration-ownership):
  where app policy, host decisions and OS consent differ.
- [Observed security posture](#observed-security-posture): measured cases and
  conclusions that must not be combined beyond their evidence.
- [Sources and investigation methods](#sources-and-investigation-methods):
  how to trace each claim to its inspected input or experiment.
- [Fit and next evidence](#fit-and-next-evidence): implications for MC and
  unresolved work for future sessions.

## License and provenance

The research repository is
[`kzahel/machine-control-spike`](https://github.com/kzahel/machine-control-spike)
(private; repository access required), with default branch `main`. For local
work, check it out beside `machine-control` as `../machine-control-spike`.
The evidence links below pin the published snapshot
[`674b756`](https://github.com/kzahel/machine-control-spike/commit/674b756f4f44164dfdb19a71b8b64c930826833c)
rather than depending on a local checkout or a moving branch. Later experiments
must record their own snapshot before updating these references.

The installed Computer Use plugin declares **Proprietary**. No separate
open-source license grant was found in the bundled `@oai/sky` package manifest;
do not infer one from its readable JavaScript. The separate Codex repository
declares Apache-2.0, which does not relicense the desktop service or runtime.
No proprietary code or assets are adopted. Exact versions, source revision,
artifact hashes and inspection paths live in the
[caller spike review](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md)
and [external MCP experiment](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md).

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
| Admission limit | Signed Node with an ordinary parent fails; signed Node with another signed Node parent receives a version reply | Repeated with a detached controller under launchd; that detached arrangement was not tested for desktop actions |
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

### Process and protocol map

**Current, reconstructed from source and bounded live tests:**

```text
MCP host: Codex integration OR our temporary Python test client
  | MCP JSON-RPC over child stdin/stdout; approvals return over this channel
  v
Signed bundled Node running the real @oai/cua-repl launcher
  v
Signed native node_repl supervisor
  |-- ordinary Node worker: agent JS / cua app handles
  |       | named RPC via supervisor
  |       v
  |-- trusted Node worker: configured @oai/sky/service handler
  |       | native-pipe connect/write/close messages to supervisor
  |       v
  +-- native broker opens Unix socket (OS sees supervisor as peer)
          |
          v
      Genuine SkyComputerUseService (separately launched application)
          |-- kernel peer identity + signing/parent admission
          |-- native app-policy and desktop-operation handling
          +-- Codex app-server subprocess dependency

      macOS Accessibility / Screen Recording permissions underpin service use
```

The service normally appeared under launchd; it is not necessarily a child
of the MCP runtime. Its app-server subprocess is distinct from any app-server
that the host uses to coordinate its agent. The diagram shows observed
components and communication, not a complete internal service call graph.
“Broker” here names the runtime's native socket bridge, not a demonstrated
standalone authorization daemon or backend token issuer.

There are three different interfaces: MCP exposes tools such as `js` and
`js_reset`; the persistent JavaScript API exposes `cua` app handles and semantic
observations; the trusted implementation sends private framed requests to Sky.
A skill or lazily emitted API documentation teaches tool use; it supplies no
OS permission or session authority. The
[protocol and launch record](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md#three-protocol-layers)
owns exact tool names and installation discovery, and the
[transport record](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#transport-direct-source-findings)
owns framing and startup details.

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

## Approval and configuration ownership

**Current:** these layers must be described separately. A successful check at
one layer does not establish the properties of the others.

| Layer | Owner / observed mechanism | What it does not establish |
| --- | --- | --- |
| Tool availability | Host/plugin selects launcher, enabled surfaces, modules and tool instructions | Installation, OS consent or authority for the agent |
| Socket admission | Native service uses kernel peer identity and reconstructed signing/parent checks | Official agent-session origin or provenance of interpreted scripts |
| App eligibility | Sky wrapper asks the native service for app policy; handles allowed, denied and forbidden results | An `allowed` result is not itself evidence of a human approval or saved Always allow decision |
| App approval | Wrapper requests MCP host elicitation; host may ask the user or resolve saved consent | An `accept` response does not attest that a person clicked a trusted native dialog |
| OS consent | macOS permissions associated with the service's identity | Each upstream caller having separately obtained user consent |
| Continuing authority / Stop | Product behavior requires separate lifecycle investigation | Connection admission and one successful action do not prove revocation or per-operation revalidation |

**Current, source-reviewed:** the wrapper first obtains policy, rejects denied
or forbidden apps, then requests host approval even for an eligible app. Its
metadata identifies the Computer Use connector, app, tool and risk level, and
offers session or session/always persistence according to native policy.
Only an `accept` result permits the wrapped operation. It recognizes a
persisted-state response marker; recognition does not locate the underlying
storage. The [detailed approval trace](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#app-approval-separate-source-and-documented-behavior)
records source paths, fields and the inspected configuration schema.

**Current, experiment ownership:** we wrote a temporary **MCP client/host**,
not a mock MCP server or replacement Sky service. It launched the installed
OpenAI MCP implementation and answered its approval requests. The rule
“accept only Computer Use requests for TextEdit” lived in that Python client.
It was our task-specific allowlist, not a new Sky setting. All 22 elicitation
requests matched it; no persistent Always allow setting was written. The
real service still supplied app policy, admission and desktop operations.

**Upstream-claimed:** [official documentation](https://learn.chatgpt.com/docs/computer-use)
describes per-app approval and Settings -> Computer use management of
Always-allowed apps, separately from macOS OS permissions. This describes
normal product UI, not a UI exercised in the external-host experiment.

**Current / Open:** the pinned open-source Codex schema supports
`computer_use.default_app_access` and `computer_use.macos.bundle_ids` allow/deny
requirements. Source tests demonstrate parsing/round-tripping, not complete
native enforcement. We have **not located or verified the macOS persistent
host-approval backing store**, its precedence against every policy source, or
every service-side operation check. Do not call these app-policy keys the
Always-allowed-apps store or import a Windows-specific setting into macOS.

**Inference:** host elicitation is not an independent human-presence boundary
against a host that can supply its own acceptance. Native caller admission
and any service-side authorization must carry that part of the threat model.
No separate interactive native arming step appeared in the successful test;
it reused existing OS/account/configuration state. This does not prove that
first installation or every product mode lacks such a step. We did not test
direct-native bypass of the wrapper or determine all native app restrictions.

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

## Observed security posture

Each row is a separate evidence claim. In particular, do not combine the
detached ping result with the non-detached TextEdit result and report a
detached hostile client controlling arbitrary applications.

| Caller / test | Strongest observed result | Boundary of the result |
| --- | --- | --- |
| Ordinary Python or bundled signed Node directly below the agent shell | Connection closed before a reply; zero-byte probe closed before parsing; authentication failure logged | Negative admission examples, not proof that every same-user process is excluded |
| Temporary runtime with owned trusted module and owned endpoint | Ordinary worker lacked native bridge; trusted worker had it; kernel-reported peer was supervisor | Host-configured bridge placement; no Sky desktop request, no production sandbox acceptance |
| Signed Node client with a signed Node parent, both running owned scripts | Real Sky version reply; repeated below detached controller with parent PID 1 | Authentic executable chain, no signature forgery; version only, no detached desktop-action test |
| External MCP host with genuine launcher, real user home and TextEdit-only approval responses | App state, menus, typing and saved text verified independently | Existing installation and consent; not detached, fresh-install, multi-app, native-policy-bypass or YA end-to-end evidence |
| macOS service executable strict signature check | Passed for inspected executable | Separate inspection from admission reconstruction; not proof the service itself calls the same validity check |

**Current:** socket and directory modes exclude ordinary other-user filesystem
access in the observed configuration, but do not separate programs running
as the owner. Additional native identity checks explain the rejected callers.
Publisher trust of a generic interpreter still permits scripts authored by
someone other than that publisher; the successful chain demonstrates this
limitation without modifying any signed binary.

**Open:** no test established resistance to a malicious unrestricted same-user
shell, administrator, module/configuration substitution, broker misuse, stale
sender context, PID reuse/reparenting, or alternate Apple-event/XPC/protected
routes. No reviewed code path or test establishes session-bound cryptographic
authority, lease expiry, Stop/revocation semantics, or all-route scope checks.
The absence of a bearer credential in the inspected local envelope does not
prove the product never uses account authentication, cryptography or backend
policy elsewhere. The TextEdit test reused existing account state.

**Current, locked-use footprint (read-only local observation, macOS 27.0):**
an installed Codex Computer Use adds
`/Library/Security/SecurityAgentPlugins/CodexComputerUseAuthorizationPlugin.bundle`
and joins `system.login.screensaver` as
`com.openai.sky.CUAService.AuthorizationPlugin.remote` ahead of
`use-login-window-ui` with `k-of-n = 1`. Any other locked-use provider must
therefore share that rule rather than assume the stock shape; see
[Tactical 106](../../docs/tactical/106-macos-shared-screen-unlock-rule.md).
How the product's own removal edits the rule was not observed.

**Current, capability limits:** app menus worked, and typed text persisted.
One shortcut instead changed formatting; an absolute path in a save-name
field became a literal filename. API acceptance alone would have hidden both
differences. Screenshot fidelity, exact-window confinement, protected/system
UI restrictions, locked-session operation, background-input non-interference
and remote use were not qualified. Neither this record nor a product safety
restriction establishes why OpenAI chose its architecture. No vendor-confirmed
vulnerability or comprehensive security audit is claimed.

## Sources and investigation methods

The spike's [exact inputs](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#exact-inputs)
and [additional pins](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md#inputs-and-discovery)
identify versions, source revisions, relative installation paths and SHA-256
hashes. Binary addresses apply only to those ARM64 artifacts. Readable bundled
JavaScript, native reconstruction, open-source code, product documentation
and experiments are different sources of evidence.

| Question | Source and how inspected | Detailed record |
| --- | --- | --- |
| Installation and provenance | Package/plugin manifests, README, MCP template, selected launch fields and app archive; hashes and `codesign` inspection | [Inputs/discovery](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md#inputs-and-discovery) |
| Native wire protocol and service startup | Distributed `targets/mac/native-pipe.js`, client and service facade; bounded source searches | [Transport](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#transport-direct-source-findings) |
| Admission predicate | `strings`, `nm`, Swift metadata/demangling, bounded ARM64 disassembly and requirement initializers; not source access to the native service | [Control-flow and addresses](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#native-control-flow-follow-up) |
| Runtime authority placement | Launcher and embedded runtime JS; owned handler/endpoint fixture with kernel `LOCAL_PEERPID` | [Runtime topology](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#runtime-topology-and-ancestry-follow-up) |
| Real rejection and acceptance | Process trees, socket ownership/modes, `lsof`, scoped service logs, bounded framed probes and detached negative/positive pairs | [Initial probes](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#authorized-live-follow-up), [signed-parent experiment](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#signed-parent-admission-experiment) |
| App policy versus approval | Distributed `computer-use-policy.js`; pinned Codex configuration schema/tests; official product documentation | [Approval trace](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#app-approval-separate-source-and-documented-behavior) |
| App-server dependency and actual effects | Native locator reconstruction, service error/log, direct CLI initialize control, genuine external MCP client, fresh AX state and `textutil` file oracle | [External experiment](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md#experiment-and-result) |
| Codex/YA host integration | Pinned open-source stdio transport, app-server request schema and YA provider request handler | [Host path](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-caller-authorization.md#host-to-service-path), [YA gap](https://github.com/kzahel/machine-control-spike/blob/674b756f4f44164dfdb19a71b8b64c930826833c/docs/sky-mcp-external-host.md#yepanywhere-integration-gap) |

**Current, retention limits:** records retain sanitized methods, results, pins
and native anchors. Private paths, raw UI/log output, transient scripts,
proprietary extracts and owned test documents were removed. There is no
checked-in automated Sky reproduction/conformance harness and no retained raw
trace from which to re-audit every observation. These are documented bounded
experiments, not a replayable security certification. The owned MC identity
fixture is separate evidence and must not be reported as a Sky test.

**Current, documentation consolidation:** on 2026-10-04 the transport and
approval-wrapper hashes were rechecked against the recorded pins, and the
Codex schema/test source was reread at the recorded revision. No new service
launch, UI operation, permission change or security probe was run for this
documentation pass. Official product claims above were consulted during the
2026-10-03 investigation and are not a fresh product-version qualification.

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

**Decision:** carry forward OS-derived native identity, a narrow broker API,
separate app consent and explicit lifecycle ownership as useful patterns.
Require MC's own evidence for exact broker identity, authenticated upstream
session origin, per-operation scopes and Stop/revocation; do not substitute a
publisher-wide interpreter rule or self-asserted MCP acceptance. This is design
input, not a statement of MC's implementation status; the owning topic tracks
that independently. An optional Sky route must not silently bypass an MC
denial or Stop.

**Open, next investigation order:**

1. Trace macOS policy and persisted approval ownership through the native
   service/app-server/host boundary, including decline, cancel and withdrawal.
2. In a dedicated authorized environment, qualify native per-operation checks
   independently of the JS wrapper and distinguish app scope from window scope.
3. Audit broker ingress, loader/config integrity, production sandboxing and
   process-lifetime/revocation behavior against explicit negative cases.
4. Exercise clean installation, account/OS consent, component discovery and
   YA elicitation/lifecycle handling before describing a usable YA provider.

For future work, first match artifact hashes and source revisions, resolve
the selected installation rather than guessing a cache path, and decide which
specific unknown the experiment tests. Preserve positive and negative controls,
bounded deadlines, an independent effect oracle and ownership-based cleanup.
Record changed evidence in the spike and update this synthesis; do not silently
promote a result from one host, route or consent state to another.

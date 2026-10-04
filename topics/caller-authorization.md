# Caller authorization

Topic: `caller-authorization`

Status: native Mac broker/provenance/proxy source implemented; signed installed
session-origin and effect qualification active.

## Motivation and current boundary

**Decision:** Prioritize preventing unrelated local processes from using
Machine Control merely because the operator has armed desktop access. The
originating request is to investigate this soon, including a small practical
credential or caller check before considering a larger authorization design.

**Current:** Desktop preview grants are target-wide for same-user callers.
An admitted caller may request a native approval dialog; once access is armed,
another same-user caller can use its scopes. Caller attribution and target-use
claims do not authenticate a YA session. The
[host-control topic](host-control.md#workstation-grant-model) owns the existing
approval workflow; the [Mac research gap](../research/platforms/macos.md#caller-authentication-gap)
records the inspected boundary and outstanding platform investigation.

**Current:** YA verifies MC's installed package and advertises its CLI through
agent instructions and PATH. That verifies the tool being invoked, not the
agent invoking it. Selection grants no access; closing YA does not revoke
MC's independent grant. See [installed agent CLI](installed-agent-cli.md).

## Investigation priorities

1. **Open — threat model:** distinguish accidental use, an unrelated process
   under the same user, a malicious unrestricted same-user shell, another OS
   user, and an administrator. State exactly which callers each candidate
   excludes; do not call a convenience interlock hostile-process containment.
2. **Open — authenticated IPC:** compare connection-bound grants, OS-verified
   peer identity and code signing, and scoped session credentials. Inspect
   macOS audit-token/code-identity facilities and Windows/Linux equivalents.
   A socket name or pipe path alone is not authentication; executing a signed
   shared CLI does not prove that its caller originated in YA.
3. **Proposal — credential alternative:** evaluate a separately provisioned
   password or random secret required for control, preferably exchanged for
   short-lived scoped authority. Specify provisioning, secret-safe delivery,
   storage, rotation, revocation, replay handling, and bypass tests. Keep
   secrets out of prompts, ordinary JSON, arguments, environment variables,
   logs and Git. A file readable by the same user is not a strong boundary
   against that user's unrestricted shell. Do not reuse the OS login password
   as a general control credential.
4. **Decision — trusted YA Desktop:** provide explicit operator opt-in for
   automatic grants to the authenticated Desktop integration. Selected eligible
   sessions receive bounded authority without per-session approval prompts.
   Keep the ability for other eligible
   clients to request approval, with truthful caller identification and bounded
   prompt handling. Separate feature visibility, CLI advertisement, approval
   requests, standing trust and actual authorization.
5. **Current / Open — comparison evidence:** the
   [Sky Computer Use review](../research/providers/sky-computer-use.md) identifies
   an ordinary-worker/trusted-service/native-supervisor topology and kernel
   peer-signing/parent checks. An owned-endpoint test confirms that the native
   supervisor owns socket connections. Bounded live probes also show a limit:
   two bundled signed Node processes running owned scripts obtain a version
   reply even when launched below a detached controller, without a Codex
   ancestor. A single signed Node with an ordinary parent is rejected. This
   authenticates an executable chain, not an official agent session. Desktop
   operations, production sandboxing and post-admission policy remain open.
   Use this as measured design evidence, not a claim of security parity.

**Current, follow-up:** an external MCP host subsequently drove user-authorized
TextEdit through the installed Sky runtime and normal policy wrapper, with an
independent saved-file effect check. This demonstrates actual app operations
outside a Codex agent session, not merely version negotiation. The test host
accepted only TextEdit approvals; it did not test direct-native approval bypass.
The [Sky dossier](../research/providers/sky-computer-use.md#mcp-surface-and-external-use)
owns this evidence and the newly observed native-service app-server dependency.
The same broker-ingress and per-operation authorization requirements still apply.

## Provisional Desktop-first plan

**Decision:** Start with YepAnywhere Desktop; defer unsigned npm CLI automatic
trust to the next follow-up. Both remain intended consumers. The first proof
is provisionally macOS, based on the available research; this does not establish
Windows/Linux acceptance or narrow the cross-platform contract.

**Decision:** Automatically granting selected access to a trusted application
is a first-class policy. Session tracking supports scope enforcement,
attribution and revocation without requiring another dialog. Other eligible
clients can request their own approval. The integration remains default-off;
feature visibility, tool selection and standing trust are distinct choices.

**Proposal:** MC owns an explicit "Automatically allow YepAnywhere Desktop"
control with permitted ordinary desktop scopes. Native Stop revokes access and
suspends automatic grants until operator re-enablement, including across
reconnect/restart. Removing trust revokes associated grants. Session closure
revokes delegated access without quitting the independent MC app. Native sudo,
protected control and remote targets retain separate authorization.

The ordered work, feasibility gate, lifecycle table and fresh-install acceptance
matrix live in [Tactical 071](../docs/tactical/071-desktop-caller-authorization.md).
**Current, bounded live-tested:** a standalone Mac socket gate accepts a signed
native fixture and rejects other executable identities, Python and an ad-hoc
identity impostor. An unrelated script run by YA's signed Bun passes a
publisher-only policy but fails the native Desktop identity policy. Signing
therefore supplies an identity primitive, not session provenance. The fixture
is callable by an unrelated process too. The tactical records the matrix and
next native-broker proof; production access policy is unchanged.

**Proposal — admission composition:**
[access admission and pause](access-admission-and-pause.md) adds temporary
availability, live waiting intents and active-session ownership around these
grants. Persistent operator consent may survive a pause/restart, while a closed
session's delegation, queue position and connection authority do not. Pausing
must neither regrant access nor let public claimant labels authenticate a
waiting owner. The plans share this lifecycle boundary.

## Candidate implementation architecture

**Proposal:** use an authenticated session broker plus scoped grants. This is
a design candidate derived from the Sky comparison, not an accepted runtime
change or a claim that Sky implements the session-grant portion.

1. **MC enforces admission and grants.** Keep an operator-facing approval path,
   but require authority on every observation/action route before provider
   dispatch. An unrelated caller must not inherit access because another
   session armed the target. Rate-limit approval requests and display the best
   verified caller identity; a claimed session label is only a label.
2. **Authenticate the integration broker.** On macOS, evaluate kernel peer
   audit tokens and explicit code-validity/designated-requirement checks for
   the YA integration. A publisher signature identifies software, not user
   consent or the calling agent session. Avoid treating a shared signed CLI,
   arbitrary signed interpreter, process name or distant ancestor as authority.
   Review every upstream interface of the broker so unrelated processes cannot
   ask it to reuse a session's access. The live Sky signed-interpreter result
   makes this a required negative test, not a hypothetical concern. Bundling
   YA and MC together or signing them with the same publisher does not establish
   upstream session provenance. Validate the native peer against the intended
   executable requirement and actual code validity; constrain its resource
   loading and request ingress separately.
3. **Bind authority to the approved session.** Prefer a private inherited IPC
   channel to the broker; where a credential is necessary, evaluate a random,
   short-lived capability delivered through a dedicated secret-safe channel.
   Bind it to the authenticated broker/channel, target, scopes and lifetime.
   Require explicit renewal, enforce revocation at MC, and define session
   close/crash, native Stop and reconnect behavior. A short lifetime alone
   does not prevent a stolen bearer credential from being used or replayed.
4. **Keep the Python CLI neutral.** It submits typed requests through the
   session channel rather than carrying target-wide standing authority.
   Other eligible clients can request their own native approval. A persistent
   server, terminal session or remote caller needs an explicit corresponding
   principal/lifecycle instead of pretending to be a YA session.
5. **Separate UI choices.** A default-off experimental setting controls feature
   visibility. Selecting tools advertises their availability. A separately
   described operator choice automatically grants selected scopes to eligible
   authenticated YA Desktop sessions without repeated dialogs. These controls
   must not silently mean “allow every local process.”

**Current:** the existing Mac browser relay already demonstrates peer audit
lookup and `SecCodeCheckValidity` against its own designated requirement in
[BrowserRelay.swift](../platforms/macos/resident/Sources/macui/BrowserRelay.swift).
That narrow relay check is reusable design evidence, not proof that ordinary
MC desktop grants authenticate callers. Development ad-hoc signing also does
not provide the release publisher boundary.

**Open:** a private inherited channel or same-user secret reduces unintended
reuse but does not by itself contain a hostile unrestricted shell. Decide which
components must be protected by a separate OS identity, sandbox or external
authorization service. Prove the broker's own admission and delegation rules,
not merely its outbound signature. Windows, Linux and remote transports need
equivalent authenticated principals, not a literal port of Mac ancestry rules.

## Next bounded broker proof

**Decision:** Keep the next slice focused on the actual YA native Desktop
process as the MC peer. Its desktop-owned server receives a private inherited
bidirectional channel; the native process retains the MC connection. Prove
that typed requests originate through that channel from an eligible session,
with explicit delegation and lifecycle state. Do not accept a localhost HTTP
request, public session label, signed Bun process or trusted ancestor as
substitute authority. Existing permissive YA server modes must not silently
qualify for automatic MC trust.

**Proposal:** Test with an owned MC fixture before desktop effects: the intended
native Desktop path passes; another process running the same signed runtime
and scripts fails; an unregistered session fails; closing the session or broker
invalidates its authority. Then move to the fresh-install acceptance matrix.
A broker must not expose arbitrary evaluation, host-chosen executable loading
from an untrusted request, or an unrestricted forwarding API. A cryptographic
channel credential can authenticate possession but cannot rescue an upstream
interface that gives it to unrelated callers.

**Open:** This is a practical application/session boundary, not a demonstrated
sandbox against an unrestricted same-user attacker. Protecting trust policy,
loaded code and credentials from that attacker may require OS isolation or an
authorization component outside its authority. The npm client may reuse the
MC principal/grant protocol later, but needs its own authenticated enrollment
and launch model; merely shipping the same signed broker is insufficient.

## Completion evidence and constraints

**Decision:** The investigation should produce a threat model, an evidenced
comparison, and the smallest recommended implementation slice with explicit
limits. Require independent tests with two callers: an authorized caller can
act, an unrelated caller cannot reuse its grant, and missing, wrong, expired,
replayed or revoked authority fails before provider dispatch. Cover direct
socket/CLI bypass, observation and capture as well as input, fresh installation,
replacement, reconnect, session close/crash, and native Stop. Define the desired
lifecycle before changing today's independent MC/YA lifetime behavior.

**Decision:** Preserve the agent-neutral Python CLI, native approval path,
explicit appliance standing policy and ordinary local/remote control. A YA
session or signed YA binary must not become mandatory for every client. MC
owns endpoint enforcement; YA owns session coordination. Stronger separation
from a hostile same-user shell requires an OS-enforced boundary or authority
outside that shell's control. Bounded validation is authorized;
the source implementation remains under installed qualification.

**Current:** [Tactical 086](../docs/tactical/086-native-desktop-delegation.md)
implements the default-off MC receiver for a specifically authenticated native
Desktop connection, durable trust/Stop and connection-bound ordinary scopes.
Public session attribution never rescues failed peer authentication or falls
back to ambient access. Native trust presentation and the actual YA private
server/launch proxy path are implemented, with kernel subprocess, credential
origin and closure fixtures. The first profile enrolls observation/input scopes
on the ordinary local unlocked desktop. Signed YA origin, the installed CLI and full signed MC operator app now pass
bounded ordinary native acceptance with independent AX effects, Pause/fresh
Resume, Stop and unrelated-caller refusal. Signed Bun/forged-attribution refusal and provider/native-integration crash
cleanup also pass, with fresh authenticated effects after trust-preserving
recovery. Further replacement/load qualification and positive protected-consent
composition remain open; this is not distribution acceptance. Existing target-wide approval stays
explicitly cooperative.

Native profile discovery is read-only and reflects current operator trust per
launch. Pending sealed verification is bounded and leaves the resident queue
responsive; Stop/revision changes fence its completion. See Tactical 086 for
source and fixture evidence, distinct from installed qualification.

**Decision:** A verified live native session may explicitly compose its trust
with separately approved current-console observation/control consent and the
already enabled locked-use helper for a finite covered task. Trust alone remains
ordinary unlocked access. Tactical 087 owns this additive prepared-console
profile; direct unlock, administrator, browser/devtools and outer routes remain
excluded.

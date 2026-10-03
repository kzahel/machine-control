# Trusted YepAnywhere Desktop access

Status: active; bounded native identity experiment passed. Product broker,
session grants and installed integration acceptance remain pending.

Owning topics: [caller authorization](../../topics/caller-authorization.md)
and [installed agent CLI](../../topics/installed-agent-cli.md).

## Objective

Let an operator explicitly trust YepAnywhere Desktop to receive selected
Machine Control capabilities automatically. Eligible YA sessions should work
without another access dialog, while unrelated callers cannot reuse their
grants. Preserve native approval requests for other eligible clients.

**Decision:** Desktop integration comes first. Authentication for the unsigned
npm-distributed YA CLI is the next follow-up, not a requirement for this slice.
**Proposal:** Prove the first implementation on macOS, where the current
[Sky comparison](../../research/providers/sky-computer-use.md) and owned native
peer-identity code provide a starting point. Other platforms retain the same
policy vocabulary but require their own enforcement and acceptance evidence.

The user authorized bounded implementation/validation and commits after the
provisional plan. This slice does not authorize release or claim fresh-install
acceptance. The results below distinguish the experiment from product changes.

## Boundaries and ownership

- MC owns caller admission, trust policy, approval dialogs, grant enforcement,
  capability limits, revocation and operator Stop.
- [YepAnywhere](../../../yepanywhere/README.md) owns its desktop integration,
  session creation, tool advertisement and authenticated session delegation.
  Resolve its checkout through [SYSTEM-MAP.md](../../SYSTEM-MAP.md); read its
  repository instructions before implementation there.
- The installed MC Python CLI remains the agent-facing interface. Its package
  signature verifies the tool, not the caller. Preserve offline help,
  identity and instructions without granting desktop access.
- The initial automatic policy covers the local ordinary desktop. It does not
  grant native sudo, lock/unlock, protected desktop, outer VM control or remote
  targets. Those authorities retain their explicit existing requirements.
- Preserve separate appliance and remote-control profiles. Their standing
  policy must not become a fallback for a denied workstation request.
- Defer arbitrary publisher lists, executable selection, publisher-wide trust,
  an unrestricted-local-access switch, and npm CLI trust enrollment. Do not
  introduce an unrestricted fallback when YA authentication fails.

## Proposed operator experience

**Proposal:** Keep the YA Machine Control feature setting off by default. Hide
the new-session checkbox while it is off. Enabling visibility or selecting
tools is not itself a grant of access.

MC offers an explicit **Automatically allow YepAnywhere Desktop** setting,
with the ordinary desktop capabilities it covers. Enabling it establishes
standing trust for the verified integration. Sessions selected for Machine
Control receive bounded grants automatically, without a per-session dialog.
Session attribution is internal authorization/accountability, not a new prompt.

Other eligible clients may request a native approval dialog for their own
bounded access. Display verified identity where available and label unverified
claims honestly; rate-limit requests. An unrelated client never inherits an
existing session's grant. MC shows active access and provides trust removal
and Stop independently of YA.

## Ordered work

### 1 — specify trust and grant lifecycle

Write the small contract before changing dispatch: verified integration
principal, session binding, target, permitted scopes, expiry, connection/runtime
generation, trust-policy revision and revocation state. Public session IDs and
claim IDs remain attribution, never bearer authority.

Use these provisional lifecycle rules as testable defaults:

| Event | Required behavior |
| --- | --- |
| Trusted, eligible YA session requests allowed scopes | Grant automatically while automatic access is enabled |
| Untrusted eligible client requests access | Native approval for that client's grant; no inherited authority |
| Request exceeds trusted scopes | Refuse the excess; any broader approval is an explicit separate request |
| Session ends or disables MC | Revoke that session's grant |
| YA broker disconnects/crashes | Invalidate its channel-bound grants; expiry bounds missed cleanup |
| Reconnect or MC restart | Authenticate again and issue fresh grants; old handles fail |
| Trust removed or scopes reduced | Revoke affected authority before further dispatch |
| Native Stop | Revoke active access and suspend automatic grants until operator re-enablement |

Stop suspension must survive reconnect and restart. Keeping a saved trust entry
must not immediately re-arm the target. Session closure revokes delegated
authority; it does not quit the independently owned MC app. Specify cancellation
of in-flight work and report any already delivered effects honestly.

### 2 — prove the desktop authentication route

Inspect the release YA Desktop package, signing identities and actual native,
Node and agent process placement. Determine which component can hold an
authenticated MC connection and securely delegate session access. Do not
assume the desktop UI is itself the socket peer.

Prototype the smallest Mac route using kernel peer identity and explicit
code-validity/designated-requirement checks for the intended integration.
Treat process ancestry as supporting evidence, not sufficient authority.
Verify the code/resources the trusted component loads and every interface
through which it accepts requests, including any local server exposed by YA.
An arbitrary local caller must not be able to command the trusted broker to
borrow another session's authority.

Prove a positive signed-desktop connection and negative unrelated-process,
shared-CLI, signed-interpreter and forged-session-label cases. Development
ad-hoc signing does not establish release publisher identity. If this proof
fails, revise the design before adding automatic grants; further Sky research
is optional and should answer a specific remaining question.

### 3 — enforce session authority in MC

Implement a narrow authenticated integration endpoint and grants checked before
every protected observation/action dispatch, including alternate direct routes.
Prefer a private inherited session channel. If a credential is necessary,
specify provisioning, binding, expiry, replay handling and a dedicated
secret-safe transport; keep it out of prompts, ordinary JSON, argv, environment
variables, logs and Git. A short lifetime alone does not prevent replay.

Route the shared Python CLI through that session authority. Distinguish missing
identity, unapproved access, expired/revoked grants and unavailable providers.
Retain the native approval route for other clients with client-bound grants.
Inventory existing target-wide grants and define explicit migration so they
cannot silently defeat the new policy. Keep offline discovery available.

### 4 — connect YA Desktop and expose trust controls

Add the YA session handoff, eligibility checks and cleanup hooks; retain
installed-package verification and normal CLI instructions. MC owns the
automatic-trust controls, active-grant state and revocation. YA owns the
default-off feature gate and new-session tool selection. Trust-policy changes
must use an operator-authorized path, not a general agent-callable setter.

Ensure the unsigned npm server cannot gain the desktop trust identity merely
by presenting the same session label or reaching the desktop broker. Explain
its unsupported automatic-trust status without silently widening access.

### 5 — validate installed behavior on a fresh Mac test appliance

Use the common private registry to select a dedicated Mac VM, run doctor and
acquire an exclusive claim before use. Use stored credentials through supported
secret transport, renew the claim as needed and release it in cleanup. Preserve
credentials for any newly provisioned appliance. Do not test on the personal
desktop or drive the VM through its host window during ordinary acceptance.

Start from a documented clean state without MC/YA trust, grants or installation
residue. Install the signed MC and YA Desktop artifacts through their supported
distribution path, complete required OS consent, enable the experimental
integration, explicitly trust YA, and create an agent session. Record actual
versions and sanitized outcomes; private identities and raw artifacts stay in
the private evidence store. Any unavoidable human-only setup remains explicit.

## Completion conditions and validation

**Proposal:** Require focused contract tests plus installed acceptance:

- Feature off: new-session control hidden and no automatic authority. Feature
  on without trust: selecting tools does not grant access.
- Trusted Desktop: two successive eligible sessions receive allowed access
  without repeated grant dialogs. Verify observation, capture and input using
  a fixture with independently observed effects, not just API success.
- Concurrent unrelated callers cannot reuse grants through raw IPC, the same
  Python CLI, signed generic runtimes or forged session identifiers. They can
  request their own approval; denial must leave them without authority.
- Missing, wrong, expired, revoked and cross-session authority fails before
  provider dispatch. Test replay where the selected protocol makes it relevant.
- Session exit, crash, reconnect, app/resident restart, trust removal, scope
  reduction and Stop obey the lifecycle table. Stop cannot trigger immediate
  automatic re-grant. Updating to a valid signed release reauthenticates;
  a replaced or invalid integration is refused.
- Native sudo and protected/locked-use approval do not become implicit. Existing
  appliance and remote-control profiles keep their explicit authorization.
- Fresh installation passes without a development checkout, prior grants or
  residual permissions. Record architecture coverage and any untested cells.

The threat model distinguishes accidental/unrelated use from a malicious
unrestricted same-user shell. Publisher identity and a private channel alone
do not prove containment of the latter. Document the achieved boundary and
any need for a sandbox, separate OS identity or external authority.

## Next follow-up and result

**Decision:** Address npm CLI automatic trust next. Compare a signed YA
executable/native broker distributed through npm with explicit credential
pairing. Package provenance alone is not live caller authentication. Reuse the
same principal/grant contract; assess same-user secret exposure and broker
misuse before choosing packaging. This follow-up must preserve headless use
without making YA Desktop mandatory.

### Bounded validation result — 2026-10-03

**Current, source-reviewed:** YA Desktop's native Tauri process launches bundled
Bun with the server entry point. The checkout's
[server launcher](../../../yepanywhere/packages/desktop/src-tauri/src/server.rs)
uses a piped startup frame for desktop bootstrap, then closes that pipe; it is
not an existing bidirectional MC session channel. These source findings are
separate from the installed 0.1.1 artifact used below.

The [auth middleware](../../../yepanywhere/packages/server/src/middleware/auth.ts)
accepts desktop credentials and other operator credentials. Its explicit
auth-disabled and localhost-open configurations can admit requests without
those credentials. The [YA security contract](../../../yepanywhere/topics/security.md)
and [principal vocabulary](../../../yepanywhere/topics/principals-and-grants.md)
already distinguish credentials, principals, grants and execution boundaries.
Existing [shared-credential limitations](../../../yepanywhere/gaps/sandbox-shared-provider-credentials.md)
are not repaired by this experiment. MC must not infer authenticated session
origin from a request arriving through YA's local HTTP server alone.

**Current, live-tested:** the standalone
[native identity harness](../../tests/macos/caller-authorization/README.md)
ran on ARM64 macOS 26.6.2 with installed YA Desktop 0.1.1. App, native executable
and bundled Bun passed strict static signature checks. Temporary native
fixtures were Developer ID signed using the locally available matching app
publisher; no signing identity or key material is retained here. The gate
verified the kernel socket audit token, dynamic code validity and a designated
requirement before reading client-supplied bytes.

| Case | Observed result |
| --- | --- |
| Signed native fixture with expected publisher and identifier | Accepted |
| Renamed copy of that fixture, launched by the Python test controller | Accepted; identity is not launch provenance |
| Same publisher, different executable identifier | Rejected |
| Ordinary Python client | Rejected |
| YA bundled Bun running an unrelated script claiming a YA session | Rejected by the fixture's identity requirement |
| Same Bun script against installed YA native executable's requirement | Rejected |
| Same Bun script against publisher-only policy | Accepted; demonstrates why that policy is too broad |
| Ad-hoc executable with the expected identifier | Rejected by the publisher-backed requirement |
| Malformed requirement | Refused before listening |

All nine Developer ID cases passed. The default no-keychain mode also passed
its eight cases using an ad-hoc fixture pinned by code hash; that mode does not
claim publisher authentication of the fixture. Documentation links and
whitespace checks passed. No production resident tests were required because
this slice adds only a standalone experiment and documentation.

**Decision:** specific executable identity with actual signature validation is
a viable admission primitive; publisher-only trust is not the selected first
policy. A signed executable is still callable/copyable by unrelated processes,
so a generic signed CLI that forwards arbitrary requests would not establish
YA session origin. The native broker must constrain its upstream entry points.

**Next:** prove a real YA native broker connection and a private channel to the
desktop-owned server, with explicit eligible-session delegation. Automatic MC
trust must fail closed when the integration cannot establish its upstream
authentication boundary, including permissive local-server configurations.
Do not silently change YA's ordinary authentication settings. Validate resource
loading and request provenance before adding automatic grants or the trust UI.
The follow-up [Sky topology/admission review](../../research/providers/sky-computer-use.md#runtime-and-launch-provenance)
measured a signed-interpreter chain receiving version replies without a Codex
ancestor. Include that shape in the owned fixture's negative cases; exact
native identity plus authenticated upstream delegation is the intended proof,
not publisher/ancestor matching or common-package membership.

**Limits:** the live positive client was a signed test fixture, not YA's actual
native executable. This completes the OS-primitive experiment, not step 2's
end-to-end Desktop proof. No resident, trust setting, grant, agent launch,
screen operation or TCC permission was changed. The installed app was not
launched; its Bun was invoked only with an owned fixture. Private temporary
sockets/files and test processes were removed. Fresh-install VM acceptance,
revocation and cross-session isolation remain untested.

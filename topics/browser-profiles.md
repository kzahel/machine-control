# Named browser profiles

Topic: `browser-profiles`

Status: **scoped; implementation and multi-profile live qualification pending**.

## Scope and current evidence

**Decision:** support multiple named Chrome extension installations connected
to the same resident, with explicit profile availability and selection. The
user selected this direction after reporting reconnect contention with two
Chrome profiles. Do not ship a separate single-provider takeover workaround.
Preventing one profile from evicting another is part of the full registry.

The [extension dossier](../research/providers/chrome-extension.md#multiple-profile-limit)
owns the source-reviewed singleton limitation and evidence boundary.
[Browser control](browser-control.md) owns ordinary browser semantics;
this topic owns profile identity, selection and authority. Native messaging
remains the transport, with existing native-host authentication. No new
provider, private inventory or coordination owner is introduced.

## Proposed product behavior

**Proposal:** each extension installation has an editable local label such as
**Work** or **Personal**, a persistent opaque identity and an **Enable this
profile** switch. Fresh and upgraded installations begin unavailable for
control until explicitly enabled. Disabled installations may announce bounded
connection metadata, but cannot enumerate tabs, attach debuggers or execute
browser work. This permits setup and profile discovery without page access.

The desktop Permissions surface lists known profiles with connected, enabled,
access and version states. Access controls and native approval prompts name
the profiles being approved. Connection, availability and approval are distinct
states. The extension can withdraw its own availability; enabling it cannot
create a Browser or DevTools grant. Stop remains global.

Multiple profiles can remain connected and be approved. The first version
preserves existing desktop admission and target-use arbitration; it does not
promise simultaneous independent agent owners just because two providers
are connected.

## Proposed identity and routing contract

**Proposal:** persist an installation UUID, label and availability preference
in extension-local storage, never synchronized storage. Use an opaque
resident-facing `browserProfileId` namespaced by extension origin. The store
and development copies remain distinguishable installations, even inside the
same Chrome profile. Labels do not grant authority and are not stable keys.
Do not derive identity from account emails, filesystem profile paths or the
Chrome process ID. No identity/account permission is needed for a manual label.

The resident allocates a new connection generation for each accepted provider.
An identity survives worker/browser restarts; its current connection generation
does not. Reinstalling the extension creates a new identity requiring fresh
approval. Duplicate live identities, including copied profile storage, must
produce an explicit conflict without silently replacing the incumbent or
transferring authority. Provide an explicit reset-identity repair that requires
new approval; do not resolve collisions by silently minting approved identities.

**Proposal:** expose the following common surface, retaining machine target
selection independently:

```text
machine-control browser profiles
machine-control browser tabs --browser-profile work
machine-control browser snapshot --browser-profile work --tab 7
machine-control browser endpoint --browser-profile work
```

These are proposed commands, not currently implemented. Existing target and
claim arguments still apply. The endpoint still requires the platform's
retained DevTools authority. Labels in examples are fictional.

`browser.profiles` returns bounded metadata only: opaque ID, label, origin,
extension/protocol version, connection generation and availability/access
state. It does not query tabs, URLs, account details or page content. Treat it
as ordinary same-user discovery, with documented remote transport boundaries.
Per-profile health belongs in status; aggregate connection remains useful for
existing setup UI. A connected profile is not proof of successful page work.

`browserProfileId` is the canonical request field. The resident resolves a
unique label once at admission and returns the canonical ID. Duplicate labels
require an ID. With several authorized profiles, omitted selection refuses
with `browser_profile_required`; there is no mutable global default in the
first version. Existing no-selector calls work when authority unambiguously
names one profile, even if other unapproved profiles are connected.

Resolve against the fixed authorized set, not whichever profiles happen to
be online. A sole authorized but disconnected profile is unavailable; it is
never substituted with another connected profile. Before approval, an omitted
selector may identify a sole enabled known profile; multiple candidates
require explicit selection before requesting authority.

Each browser-capable control session pins one canonical profile on explicit
selection or its first unambiguous browser operation. Later conflicting
selectors refuse. A native-only owner need not select a browser. Changing a
label never retargets an existing session, grant or endpoint.

## Proposed authority and lifecycle rules

**Proposal:** Browser and DevTools grants carry exact approved profile IDs.
For the initial version, one profile set applies to both scopes; the existing
separate scope approvals still distinguish ordinary control from scripts/CDP.
Operator arming can approve several profiles; an agent request names the
profile it needs and cannot alter the operator's allowed set. A pending
approval snapshots exact IDs and availability revisions, rechecked at decision
and dispatch. Newly discovered or newly enabled profiles never join a live
grant implicitly.

Remember selected profile IDs with editable access choices, separately from
authority. Mac same-console consent restoration retains the exact approved
IDs and existing expiry/session checks. Old saved consent without profile IDs
cannot safely restore browser authority: require fresh browser approval while
preserving independent desktop scopes and remembered form choices. Existing
appliance standing policies need explicit profile enrollment or an exact
fixture-owned profile set; do not turn them into future-profile wildcards.

Disabling/removing a profile immediately withdraws its effective authority,
closes its CDP sessions and fences its pending work. Re-enabling it requires
fresh profile approval. Unrelated profiles retain their own route state.
Reconnect of the same still-approved installation permits fresh work under
remaining valid consent, but cannot revive old references, owners or streams.

Scope tab IDs, references, dialog IDs, pending requests, debugger ownership and
CDP sessions by profile and connection generation. Cross-profile use refuses,
including synthetic collisions in numeric tab IDs. Bind each endpoint token
to a profile as well as the platform's existing owner/grant fences. Browser-root
CDP describes only that selected profile, including created tabs and popups;
do not merge profiles into a synthetic browser or isolated browser contexts.

Pause, Stop, expiry, lock policy, console replacement and resident restart
retain their current meaning. Fan out authority changes to the appropriate
providers. A profile disconnect affects its own requests and streams. Preserve
refused-before-dispatch versus unknown-after-dispatch outcomes; never replay
uncertain work through another profile. Keep profile labels out of public
evidence and ordinary payload-free audit; local diagnostics can use opaque IDs
and generations under the existing private retention policy.

## Delivery and next work

**Current:** the [shared resident core](shared-resident-core.md) passes the
deterministic reference slice in [Tactical 150](../docs/tactical/150-shared-resident-core.md)
and a bounded two-process, headless real-browser fixture in
[Tactical 151](../docs/tactical/151-shared-core-real-browser.md). Durable
extension identity, native authentication and installed profile selection
remain pending.

**Decision:** adopt the shared core for native integration.
The following product plan remains proposed and is
subject to the shared boundary and later deployment evidence.

**Proposal:** implement a versioned profile-aware handshake before granting or
dispatching any browser work. Native transport registration is not admission
of an unidentified browser provider. Bound pre-handshake connections, workers,
queues and metadata. macOS/Linux need per-connection state; Windows also needs
a concurrent named-pipe accept loop instead of its current single connection.

Require matching profile-aware runtime and extension versions for this first
implementation. Mixed versions must present an actionable update state, stay
unarmed and avoid a rapid retry loop; do not promise a legacy singleton
compatibility mode. Test both update orders. Old desktop binaries cannot gain
multi-profile behavior from an extension update alone. Desktop packaging and
Chrome Web Store delivery remain separate acceptance/release steps.

Do not broaden Chromium browser support, add incognito support, discover Chrome
account names, merge store/development identities, or redesign desktop admission
as part of this work. Explicitly exclude incognito tabs from the initial route
even if Chrome's extension setting permits incognito execution.

[Tactical 149](../docs/tactical/149-browser-profiles.md) owns ordered work,
source ownership and the multi-profile acceptance matrix. Implement the common
contract and Windows vertical slice first, then macOS and Linux parity; no
platform inherits another platform's execution qualification.

# Named browser profiles

Topic: `browser-profiles`

Status: **Windows named-profile browser cutover accepted in an unsigned ARM64
candidate; Mac ordinary/streamed and protected packaged slices passed;
Linux adoption follows**.

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

## Product behavior

**Decision, implemented on Windows and in the unreleased Mac adapter:** each extension installation has an editable local label such as
**Work** or **Personal**, a persistent opaque identity and an **Enable this
profile** switch. Fresh and upgraded installations begin unavailable for
control until explicitly enabled. Disabled installations may announce bounded
connection metadata, but cannot enumerate tabs, attach debuggers or execute
browser work. This permits setup and profile discovery without page access.

The Windows and unreleased Mac Access surfaces list known profiles with connected, enabled and
approved states, plus protocol/conflict repair guidance. Access controls and native approval prompts name
the profiles being approved. Connection, availability and approval are distinct
states. The extension can withdraw its own availability; enabling it cannot
create Browser authority. The unified Browser surface includes supported
CDP, evaluation and streams; there is no separate scripts consent tier. Stop remains global.

Multiple profiles can remain connected and be approved. The first version
preserves existing desktop admission and target-use arbitration; it does not
promise simultaneous independent agent owners just because two providers
are connected.

## Identity and routing contract

**Decision, implemented:** persist an installation UUID, label and availability preference
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

**Current Windows client surface:** retain machine target
selection independently:

```text
machine-control browser profiles
machine-control browser tabs --profile Work
machine-control browser snapshot --profile Work --tab 7
machine-control browser endpoint --profile Work
```

These commands require a profile-aware resident. The Python client checks that
capability before forwarding an explicit selector; pre-cutover Linux and older Mac residents
refuse it. Existing target and claim arguments still apply. The endpoint still requires the platform's
retained DevTools authority. Labels in examples are fictional.

`browser.profiles` returns bounded metadata only: opaque ID, label, extension origin,
connection and availability state. The Windows state projection additionally
identifies the exact approved set. Operation results carry the canonical
profile ID and provider generation. Protocol/version diagnostics can be
extended later without querying browser content. It does not query tabs, URLs, account details or page content. Treat it
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
never substituted with another connected profile. Windows operator approval always selects exact enabled known IDs; none are
automatically checked when a new native approval form opens.

**Decision:** one retained desktop owner may address different members of the
exact operator-approved profile set with explicit per-operation selectors.
There is no mutable session default or implicit profile transfer. Every
reference, endpoint and stream is pinned to its canonical profile and
generations. A native-only owner need not select a browser. Changing a label
never retargets a grant, reference or endpoint.

## Authority and lifecycle rules

**Current Windows source:** one Browser permission includes supported CDP
and page JavaScript, carrying exact approved profile IDs. The earlier accepted
[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md) slice used
separate legacy scope approvals; that is historical evidence for its own build.

**Decision:** Browser’s independent Off / Ask first / Automatic mode and exact
profile set follow the [unified permission contract](access-admission-and-pause.md#unified-permissions-and-handoff-contract).
The separate user-facing scripts/DevTools tier is removed on Windows. Native
provider scope mappings remain internal and cannot widen old consent silently.

**Decision, retained profile invariants:** operator arming and native approval can select several profiles. An agent
request cannot alter that exact set; its operation selects within existing
consent. Approval revalidates the selected IDs and availability before issuing
shared authority, which is rechecked at dispatch. Newly discovered or newly enabled profiles never join a live
grant implicitly.

**Decision:** remember selected profile IDs with editable access choices,
separately from authority. The unified model restores no consent after resident
restart. Legacy Mac same-console consent must not be imported as broader Browser
authority; preserve only explicitly compatible form preferences. Existing
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

Preserve expiry, lock/session safety and generation fences. The unified
permission contract owns surface/global Pause, Stop and quiet Off
semantics. Fan out authority changes to the appropriate providers. A profile
disconnect affects its own requests and streams. Preserve
refused-before-dispatch versus unknown-after-dispatch outcomes; never replay
uncertain work through another profile. Keep profile labels out of public
evidence and ordinary payload-free audit; local diagnostics can use opaque IDs
and generations under the existing private retention policy.

## Delivery and next work

**Decision for incremental adoption:** retain native-messaging frame protocol
v1 and negotiate the additional profile protocol v1 through `hello.profile`
and `profile.accepted`. The migrated Windows resident requires persistent
profile metadata and keeps incompatible or colliding copies connected but
unarmed with a typed refusal, avoiding a reconnect fight. Extension-local
identity/name/availability are persistent; profile-aware enable/name/reset UI
appears when the resident negotiates support. Pre-cutover Mac/Linux residents
retain their existing single-profile behavior; this does not qualify them for
named profiles or provide a legacy fallback on the migrated Windows resident.

**Current:** the [shared resident core](shared-resident-core.md) passes the
deterministic reference slice in [Tactical 150](../docs/tactical/150-shared-resident-core.md)
and a bounded two-process, headless real-browser fixture in
[Tactical 151](../docs/tactical/151-shared-core-real-browser.md). Windows now integrates durable extension identity, concurrent authenticated
pipe peers, exact operator/native approval selection and shared CDP routing.
[Tactical 152](../docs/tactical/152-shared-runtime-windows-adoption.md) owns
its complete bounded 39-check real-browser/Settings candidate acceptance,
source identity and cleanup. No Mac/Linux adoption or publication is implied.

**Decision:** qualify unified permissions/handoff on Windows with the shared
core and reference/synthetic clients before Mac/Linux adoption. Temporary
integration breakage/disablement is acceptable; optional legacy behavior must
be isolated and removed after cutover. Each platform adopts the same policy,
removes its replaced engine and passes its declared native/package gates.

**Current Windows requirement:** a versioned profile-aware handshake precedes
grants and browser work. Native transport registration is not admission
of an unidentified browser provider. Bound pre-handshake connections, workers,
queues and metadata. macOS/Linux need per-connection state; Windows uses a concurrent bounded named-pipe accept loop; Mac/Linux still
need independent per-connection native transport adapters.

Require matching profile-aware runtime and extension versions for this first
implementation. Mixed versions must present an actionable update state, stay
unarmed and avoid a rapid retry loop; do not promise a legacy singleton
compatibility mode. Test both update orders. Old desktop binaries cannot gain
multi-profile behavior from an extension update alone. Desktop packaging and
Chrome Web Store delivery remain separate acceptance/release steps.

Do not broaden Chromium browser support, add incognito support, discover Chrome
account names or merge store/development identities as part of named profiles.
The original profile slice excluded desktop admission redesign; that is now
explicitly the next slice in [Tactical 153](../docs/tactical/153-unified-permissions-and-handoff.md).
Explicitly exclude incognito tabs from the initial route
even if Chrome's extension setting permits incognito execution.

[Tactical 149](../docs/tactical/149-browser-profiles.md) owns ordered work,
source ownership and the multi-profile acceptance matrix. Implement the common
contract and Windows vertical slice first, then macOS and Linux parity; no
platform inherits another platform's execution qualification.

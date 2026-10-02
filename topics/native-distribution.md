# Native Distribution

Topic: `native-distribution`

Status: signed Windows workstation preview and direct YA Node/Codex consumer
accepted; signed Mac desktop candidates are verified and accepted in ARM64
Tart. Mac desktop `0.3.5` is published; public packages, latest download routes,
production feeds, and installed ARM64 public-client acceptance are verified.
Fixed sender code passes automatic production-feed handoff; legacy 0.3.3/0.3.4
senders may need one reopen after installation. YA
download/update code is implemented, while public Windows consumer acceptance
is open. The shared Windows Tauri candidate passes signed x64 VM acceptance;
its ARM64 product execution and public feed remain open.

The [desktop acceptance matrix](../docs/desktop-acceptance.md) indexes behavior
by package family, architecture, and virtual/physical environment.

## Direction

**Decision:** Distribute Machine Control as an optional headless native
component with a stable public entry point and platform-specific helpers.
Reuse existing residents and provider boundaries. A consumer such as
YepAnywhere owns install/enable controls, supervision, and agent-tool exposure.
Machine Control owns artifacts, the desktop contract, capability reporting,
and providers. The shared Tauri desktop product is an optional operator and distribution
surface; headless resident/CLI use remains independent.

Reuse Desktop Release Kit's signing and validation patterns. Keep the package
key independent of consumer updater keys. Native signing/notarization and
package authenticity are separate checks.

**Decision:** First prove an inert signed CI fixture, then package a Windows
resident pilot and extend to macOS and a named Linux profile. The first
workstation scope is logged-in ordinary desktop control. Preserve appliance
protected control as explicitly installed/armed profiles rather than weakening
its authority or silently installing it on personal machines.

## Current implementation

**Current:** [Native signing smoke](../release/README.md) defines manual,
main-only Windows x64, macOS ARM64, and Linux x64 builds, publisher signing and
notarization, and a minisign-authenticated three-package manifest. The complete
hosted run passed, and its downloaded manifest, package hashes, and Mac bundle
were independently verified. CI artifacts are temporary evidence; the workflow
does not publish releases or install residents. Accepted evidence is tracked in
[Tactical 035](../docs/tactical/035-native-signing-smoke.md).

The smoke manifest is not the future product update contract. The eventual
consumer needs compatibility/version selection, verified staging, activation,
rollback, and clean disable/removal.

## Remaining product work

**Decision:** [Tactical 036](../docs/tactical/036-windows-workstation-distribution.md)
implements Windows distribution additively: retain appliance defaults, share
ordinary providers, select user endpoints explicitly, and keep privileged
control in the authorized appliance profile. Candidate and appliance acceptance
are separate required gates before migration of existing deployments.

**Current:** Windows has an explicit `user --instance NAME` host and
`call --profile user` client selection alongside unchanged appliance defaults.
The Medium-only host shares ordinary providers, isolates user artifacts, and
refuses protected operations. Exact signed ARM64/x64 previews pass ordinary
desktop acceptance with independent fixture effects. Signed ARM64 upgrade/
rollback and isolated x64 appliance regression also pass.
Both final signed architectures also passed idle-session recovery, stale
references, provider failure and IPC resilience. Fresh observations can reopen
the owned capture session; expired actions are refused without replay.
Tactical 036 records the accepted source and CI artifacts. No public release
has been published.

**Current:** The Windows package also carries an optional signed unlock setup
entry. It installs a separate privileged service, starts unarmed, and requires
UAC plus explicit account/controller/lifetime approval. The
[protected unlock topic](windows-protected-unlock.md) owns its contract and
[tactical 037](../docs/tactical/037-windows-unlock-arming.md) its native acceptance.

**Open:** Complete the first public Windows release and packaged YepAnywhere
acceptance; complete physical Mac and Intel runtime acceptance; package Linux
dependencies and validate a workstation portal/input profile. Mac bundle-relative
providers and signed-upgrade consent have passed ARM64 Tart acceptance.
Keep actual routes and unsupported capabilities visible.

**Current:** An isolated YepAnywhere experiment exercised a small authenticated
MCP adapter against the signed Windows user resident. Real Codex and Claude
sessions discovered the tools lazily, performed one semantic action each, and
read native screenshot results; independent fixture state confirmed both
effects. No YA provider or resident implementation changes were required.
The [spike findings](../../machine-control-spike/docs/ya-computer-mcp-findings.md)
own exact versions, route evidence, latency and remaining acceptance gaps.

**Decision:** Keep agent adapters over the existing typed resident contract.
YA's requested product path uses direct local IPC and on-demand, session-scoped
activation; MCP is a proven optional adapter, not a required server registered
in every session. YA's [computer-control topic](../../yepanywhere/topics/optional-computer-control.md)
owns consumer mechanics and the Codex/Sky reference. Unlock remains a separate
native flow.

**Current:** YA's Windows Node/Codex preview now installs an authenticated local
package, exposes default-off settings and explicit session selection, and
registers a deferred namespaced dynamic tool over the existing provider
connection. First use launches an ordinary user resident over direct local
IPC. Native screenshot results reach the model and live/reloaded YA browser
views. A private YA-owned Windows Job Object reclaims resident/provider
descendants on consumer failure; the appliance service, common CLI, SSH and
independent supervisor remain available. No native runtime change was required.
The YA topic owns [direct consumer acceptance and its limits](../../yepanywhere/topics/optional-computer-control.md#direct-windows-acceptance-2026-09-12).
This evidence covers the signed ARM64 preview with source-run Node YA and
Codex, not public release-feed delivery or other consumer platforms.

The [common desktop](unified-desktop-client.md),
[Windows](windows-resident-control.md), [macOS](macos-resident-control.md), and
[Linux](linux-resident-control.md) topics own runtime behavior. The
[Cua dossier](../research/providers/cua-driver.md) owns provider facts and
distribution caveats. Exact dependency/license audits and signed-provider
digest handling remain prerequisites to shipping those providers.

## Public Windows release contract

**Decision:** Every published release requires a checked-in changelog section
for its exact version with meaningful change bullets. Desktop and Windows
workstation publication both refuse missing, empty, duplicate, or placeholder
notes. The version section is the GitHub release body; desktop updater metadata
uses the same notes. CI candidates without publication remain independent.

The Windows workstation workflow accepts an optional stable `version` input.
Empty input retains CI-only preview behavior. A version produces both
architectures and `release.json` with its minisign detached signature.
Publication runs only after both builds and manifest verification succeed,
in the main-only release environment. It creates `workstation-v<version>` as
a draft with all assets before publishing. Existing releases are never
overwritten by the workflow.

`machine-control-workstation-release/v1` binds the version/tag, native protocol
`machine-control/v0`, consumer protocol 1, exact source/workflow identity,
Windows publisher and both archive names, SHA-256 hashes and sizes. The existing
Machine Control package key authenticates this metadata. The publisher in this
authenticated manifest is trusted consumer configuration; native signature and
catalog checks still apply to the package before executing its installer.

YA pins the public package key in its shipped code and owns version selection,
bounded downloads/staging, per-user installation, health checks, session-aware
update timing and recovery to the prior package. A release does not update
appliances or install/arm protected unlock. Incompatible or unverifiable
releases leave the installed version usable. Component publication does not
deploy a new YA server or hosted client.

## Shared desktop product

**Current:** the standalone Mac candidate has verified signed/notarized CI
DMGs and updater archives for both architectures. The ARM64 app passed native
Tart operator and installed-upgrade acceptance. The published `0.3.3` source
also passed a signed `0.3.2` upgrade, visible approval/scope narrowing, independent
fixture effects, global Stop, and tray Quit. This is a developer preview with
target-wide grants; Intel execution and physical-host acceptance remain open.
Production-feed acceptance subsequently passed in Tactical 052. Initial
candidate evidence and bounded omissions live in [tactical 051](../docs/tactical/051-tauri-macos-desktop.md).

**Current:** The shared Windows Tauri candidate passes exact signed
x64 installation, grants, tray/lifecycle, signed fixture-feed update, and
local/outside control acceptance. Signed `0.4.4` to `0.4.6` replacement also
passes with Chrome open, retaining registration and startup while revoking
access. ARM64 artifacts pass signing and byte
verification, but product execution remains open. [Windows desktop](windows-desktop.md)
owns the workstream; [Tactical 053](../docs/tactical/053-windows-desktop.md) and
[054](../docs/tactical/054-windows-browser-and-arm64.md) own the evidence.
Physical hardware is later environment coverage; existing
physical appliance-engine evidence does not establish this new operator app.

**Decision:** Use the shared Tauri UX and Desktop Release Kit update contract
for the standalone desktop product, with a unique updater key and product
route. macOS initially embeds the native Swift resident as a framework in the
application process. Its operator UI does not move enforcement into the
WebView. Windows and Linux keep their native providers and separate evidence
gates. [Tactical 051](../docs/tactical/051-tauri-macos-desktop.md) owns the first
signed Mac candidate and Tart acceptance. CI candidates do not publish releases
or deploy the update service.

**Current:** [Tagged desktop publication](../release/macos-desktop.md) uses a
clean main checkout, explicit changelog notes, and annotated `desktop-v` tags.
The main-only workflow requires exact tag/source identity, verifies both Mac
packages and GitHub-uploaded hashes, and publishes the complete draft once.
The website resolves the latest desktop DMGs independently of Windows component
releases. [Mac desktop 0.3.3](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3)
is the first public preview. Both final packages passed
[CI signing and publication staging](https://github.com/kzahel/machine-control/actions/runs/36820029330).
The first publication stopped after upload because its by-tag lookup could not
resolve the draft. Recovery authenticated both exact CI packages, checked all
nine draft asset hashes/sizes, source identity, changelog and updater metadata,
then published the same draft by ID without replacing bytes or its tag. Future
CI publication now resolves and verifies the draft by ID. Both re-downloaded
public DMGs and archives passed publisher signatures, notarization/stapling,
updater signature/version and tamper rejection. The live download page selects `0.3.5`, and both architecture routes redirect
to its exact installers. Both the shared server and website proxy return signed
archive metadata with cumulative required changelogs for older clients and 204
for current clients. Product registration and the website proxy preserve the
endpoint already embedded in 0.3.3.

**Current:** [Tactical 052](../docs/tactical/052-macos-production-updates.md)
owns production update acceptance and immutable 0.3.4/0.3.5 publication. The
0.3.4 release cleared Apple's agreement gate without moving its tag; installed
testing exposed a legacy sender relaunch failure. The bounded native repair's
signed fixture passes Permissions Restart and automatic installation of the
actual public update. Public 0.3.3 installs public 0.3.5 with one native reopen
for its old defect. Released 0.3.5 then passes automatic Permissions Restart,
retained permissions, access revocation, stale-reference refusal, native
approvals/fixture effects, global Stop, tray commands and Quit without respawn.
Original testbed app, policy, LaunchAgent and power are restored and claims
released. Both final public package families are authenticated; physical Mac
and Intel runtime execution remain open.

**Decision:** Share the bounded native handoff between Permissions Restart and
explicit update installation. Preserve normal Exit cleanup, wait for the old
process to exit, and keep the replacement outside the predecessor's process
group. Native sockets are close-on-exec. No automatic installation is enabled;
access and pending approvals are checked immediately before replacement.
Older 0.3.3/0.3.4 senders may require reopening the app after their first update;
the required 0.3.5 notes state that limitation. Published tags and bytes remain
immutable.

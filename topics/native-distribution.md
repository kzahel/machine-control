# Native Distribution

Topic: `native-distribution`

Status: signed Windows headless workstation preview remains available; YA now
consumes the installed desktop CLI and has retired its component lifecycle. Unified Mac/Windows/Linux desktop `0.5.4` is published; package
signatures, public downloads, and production metadata are verified for all six
architectures.
ARM64 Tart has targeted signed browser-indicator evidence; Windows x64 retains
its earlier installed product acceptance. Public 0.5.4 adds focused indefinite
access and fixture-effect acceptance on all three ARM64 VMs, plus Windows
production replacement from 0.5.3. Intel and full physical product acceptance
remain separate. Linux x64 Debian/AppImage installed acceptance and signed
replacement pass on Ubuntu GNOME Wayland; ARM64 portal/browser/lifecycle
coverage remains open. Legacy Mac `0.3.3`/`0.3.4` update senders may need one reopen;
fixed senders pass production-feed handoff. YA installed Mac/Windows consumer
model/media/lifecycle use and Linux x64 core control are accepted within
[their declared scope](../../yepanywhere/topics/optional-computer-control.md).

The [desktop acceptance matrix](../docs/desktop-acceptance.md) indexes behavior
by package family, architecture, and virtual/physical environment.

## Direction

**Decision:** distribute the desktop operator app with its bundled Python CLI,
while keeping headless residents as independent explicitly installed profiles.
Reuse residents and provider boundaries. For the installed desktop route MC
owns installation, updates, native access, lifecycle, artifacts and the control
contract; YA owns verified discovery, launch eligibility and agent/media
exposure. It does not install or supervise a second resident. Headless CLI and
appliance use remain independent of YA and the desktop UI.

Reuse Desktop Release Kit's signing and validation patterns. Keep the package
key independent of consumer updater keys. Native signing/notarization and
package authenticity are separate checks.

**Decision:** First prove an inert signed CI fixture, then package a Windows
resident pilot and extend to macOS and a named Linux profile. The first
workstation scope is logged-in ordinary desktop control. Preserve appliance
protected control as explicitly installed/armed profiles rather than weakening
its authority or silently installing it on personal machines.

## Current implementation

**Decision:** Adopt Desktop Release Kit's Stable discovery cadence: a silent
check after five seconds and daily while running, with a bounded timeout and
deduplication. The native desktop process owns scheduling/results independently
of its settings WebView. Settings/tray and metadata-only `update.check|status`
requests use that same controller. Discovery does not focus, download, install,
restart, approve, or revoke access. Installation stays an explicit local operator
action behind the resident's access/approval replacement gate.

**Current:** Public desktop 0.5.3 ships this integration for Mac/Windows/Linux;
older released clients keep their shipped behavior until updated.
[Tactical 060](../docs/tactical/060-native-update-discovery.md) records validation
and installed-platform limitations.

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
Tactical 036 records the accepted source and CI artifacts. No public
workstation-family release has been published; the desktop family is separate.

**Current:** The Windows package also carries an optional signed unlock setup
entry. It installs a separate privileged service, starts unarmed, and requires
UAC plus explicit account/controller/lifetime approval. The
[protected unlock topic](windows-protected-unlock.md) owns its contract and
[tactical 037](../docs/tactical/037-windows-unlock-arming.md) its native acceptance.

**Open:** Headless workstation-family publication and packaged YA distribution
acceptance remain separate from the accepted desktop CLI consumer; complete physical Mac and Intel runtime acceptance; extend Linux
coverage beyond the accepted Ubuntu GNOME Wayland x64 desktop profile. Mac bundle-relative
providers and signed-upgrade consent have passed ARM64 Tart acceptance.
Keep actual routes and unsupported capabilities visible.

**Current:** An isolated YepAnywhere experiment exercised a small authenticated
MCP adapter against the signed Windows user resident. Real Codex and Claude
sessions discovered the tools lazily, performed one semantic action each, and
read native screenshot results; independent fixture state confirmed both
effects. No YA provider or resident implementation changes were required.
The [spike findings](../../machine-control-spike/docs/ya-computer-mcp-findings.md)
own exact versions, route evidence, latency and remaining acceptance gaps.

**Decision:** keep agent adapters over the existing typed resident contract.
The installed Python command and native image tools provide YA's ordinary
agent route; MCP remains an optional adapter rather than a mandatory server
registered for every session. Unlock retains its separate native flow.
[YA's topic](../../yepanywhere/topics/optional-computer-control.md) owns current
consumer configuration, authority and compatibility.

**Current:** YA's former Windows Node/Codex workstation component is retired.
Its signed local installation, deferred tool, session grants, direct IPC and
private Windows Job Object remain historical evidence in
[YA Tactical 131](../../yepanywhere/docs/tactical/131-optional-windows-computer-control.md).
The accepted installed consumer instead authenticates public desktop 0.5.3,
uses the bundled CLI for actual native/browser model turns and capture/media,
and leaves the independent resident unchanged through YA close/restart/crash.
Native Stop/expiry/MC restart owns revocation, not YA session close.
[Installed agent CLI](installed-agent-cli.md) and
[YA Tactical 142](../../yepanywhere/docs/tactical/142-machine-control-desktop-consumer.md)
own the cutover and explicit platform/provider limits.

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

The old YA consumer pinned this package key and owned downloads, installation
and session-aware updates. That consumer is now retired; the workstation-family
release contract remains available for other explicit consumers. Installed
desktop consumers use the desktop family's authenticated CLI and MC-owned
updates. Neither release family implicitly updates appliances or installs/
arms protected unlock, and MC publication does not deploy a YA release.

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
passes with Chrome open; `0.4.6` to `0.4.7` and ordinary `0.4.7` uninstall also
pass. Updates retain registration and startup while revoking
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

**Current:** [Tagged desktop publication](../release/desktop.md) uses a
clean main checkout, explicit changelog notes, and annotated `desktop-v` tags.
The main-only workflow requires exact tag/source identity, verifies all six
Mac/Windows/Linux packages and GitHub-uploaded hashes, and publishes the complete
draft once. The website resolves current desktop installers independently of
workstation component releases. [Mac desktop 0.3.3](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3)
is the first public preview. Both final packages passed
[CI signing and publication staging](https://github.com/kzahel/machine-control/actions/runs/36820029330).
The first publication stopped after upload because its by-tag lookup could not
resolve the draft. Recovery authenticated both exact CI packages, checked all
nine draft asset hashes/sizes, source identity, changelog and updater metadata,
then published the same draft by ID without replacing bytes or its tag. Future
CI publication now resolves and verifies the draft by ID. Both re-downloaded
public DMGs and archives passed publisher signatures, notarization/stapling,
updater signature/version and tamper rejection. The live download page selects
unified `0.5.4` for all eight installer/package routes. Both the shared server and website proxy return signed
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

**Decision:** The standalone desktop product has one release script, version,
required changelog, tag and updater manifest for every implemented platform.
Mac ARM64/Intel, Windows x64/ARM64, and Linux x64/ARM64 publish together. A
successful exact-source unified candidate can be promoted without rebuilding
its accepted signed bytes. Focused Windows ARM64 Tauri execution is recorded
for public 0.5.4; broader capability claims require their own evidence.
[The unified process](../release/desktop.md) owns operator guidance;
[Tactical 055](../docs/tactical/055-unified-desktop-publication.md) owns execution.

**Current:** [Public desktop 0.5.4](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.4)
promotes all six authenticated candidates without rebuilding. It adds Windows
and Linux indefinite manual access, matching Mac.
[Tactical 091](../docs/tactical/091-desktop-until-stopped.md) owns exact source,
workflow, public-byte authentication, focused native acceptance on all three
ARM64 VMs and production Windows replacement from 0.5.3. All six installed CLI
payloads also pass hosted offline relocation checks. Earlier CLI publication
evidence remains in [063](../docs/tactical/063-six-platform-desktop-release.md).

Linux x64 Debian/AppImage installed acceptance and signed browser-open
replacement retain their exact public 0.5.0 evidence in
[Tactical 059](../docs/tactical/059-public-linux-desktop.md).
[Linux desktop](linux-desktop.md) owns the supported profile and the limits of
focused ARM64 0.5.4 acceptance.

Earlier public-release execution remains in [055](../docs/tactical/055-unified-desktop-publication.md),
[057](../docs/tactical/057-macos-until-stopped-release.md), and
[058](../docs/tactical/058-browser-tab-indicators.md). Mac until-stopped access
and browser indicators are retained in 0.5.0; their signed native execution
evidence remains the recorded ARM64 Tart tests. Other architecture and physical
execution gaps are indexed in the acceptance matrix.

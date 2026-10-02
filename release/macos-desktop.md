# Mac desktop publication

The desktop release entry point follows lid-awake's clean-checkout and changelog
pattern. Tags use `desktop-vX.Y.Z`, independently of `workstation-vX.Y.Z`
Windows component releases. Both Mac architectures now publish alongside Windows through the unified flow.

## Release

Use the [unified desktop release process](desktop.md). The single script now
publishes both Mac architectures and both Windows architectures together.
Direct `macos-desktop.yml` dispatches produce CI candidates only.
The immutable Mac-only releases below retain their historical evidence.

## Website downloads

[The download page](https://machinecontrol.dev/downloads/) resolves published
`desktop-v` releases independently of other release families. It exposes:

- `/download/macos/arm64` — Apple silicon DMG;
- `/download/macos/x86_64` — Intel DMG.

These paths redirect to exact versioned GitHub assets and cache for five
minutes. Drafts and prereleases are excluded; numeric version ordering picks
the newest desktop release. Both installers, updater archives/signatures, and
`latest.json` must be present. An incomplete newest release fails closed rather
than silently selecting an older one. Before first publication the page shows
no public Mac release; upstream failures show temporary unavailability.
The website needs no rebuild for a new release.

## Updates

The public `latest.json` follows Desktop Release Kit's Tauri metadata contract.
The existing simple-app-update-server owns production update routing. Register
the product there using `githubRepo: kzahel/machine-control`,
`tagPrefix: desktop-v`, and `tauriUpdates: true`. Optional installer patterns are
`MachineControl_*_arm64.dmg` and `MachineControl_*_x86_64.dmg`.
Concrete host/path configuration and proxy deployment belong in private
infrastructure configuration.

The product configuration is [update-server/machine-control.json](../update-server/machine-control.json).
Deploy it through the shared server's product-config directory. The website
proxies `machinecontrol.dev/updates/tauri/...` to the product's public shared
server route. The proxy accepts only supported Mac targets and numeric versions,
forwards optional anonymous check metadata, and does not forward website
credentials. Publication alone does not deploy the server or website.
The first installed production-feed update is tracked in tactical 052. Native code requires
access and pending approvals to be off before bundle replacement, and verifies
the updater signature and its trusted version.

## Verify completion

Check the successful workflow, public tag, downloaded package authenticity,
website redirects for both architectures, and the published updater metadata
before calling package publication accepted. Production in-app updates require
separate feed deployment and installed-update acceptance.

The first public preview is
[`desktop-v0.3.3`](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3),
from source `15dbb63471dda2938cc9d2de905d28c33a8a2ef3`. The exact signed
[candidate](https://github.com/kzahel/machine-control/actions/runs/36817620234)
passed ARM64 Tart native UI and signed-upgrade acceptance. The
[publication run](https://github.com/kzahel/machine-control/actions/runs/36820029330)
passed both final package builds and staging, then left a complete draft when
its by-tag lookup returned 404. Verified recovery published that same draft by
ID after checking all nine uploaded assets, source identity, changelog and
updater metadata. The workflow now uses IDs for draft verification/publication.
Public package and website download verification is recorded in the
[native distribution topic](../topics/native-distribution.md).
The production route is deployed and returns signed metadata for older clients
and 204 for current clients on both Mac architectures. Installed 0.3.3 to
0.3.4 production testing installed the new bundle but found an automatic
relaunch defect, repaired in 0.3.5.

[Tactical 052](../docs/tactical/052-macos-production-updates.md) owns deployment
and the first production-feed update acceptance.

## 0.3.4 publication and updater status

[Tagged CI](https://github.com/kzahel/machine-control/actions/runs/36830572285)
attempt 2 published 0.3.4 after the Account Holder resolved Apple's agreement
HTTP 403. All jobs were rerun at the original tag/source; both receipts share
attempt 2. At publication, public package authenticity, the required changelog,
exact installer links and signed update routes were verified.

The production 0.3.3 to 0.3.4 test installed the new bundle but failed automatic
relaunch. Older 0.3.3/0.3.4 clients may require reopening Machine Control after
installation. The 0.3.5 bounded restart handoff and public-client acceptance are
complete in ARM64 Tart; tactical 052 records the exact evidence. Published
bytes and tags remain immutable.

## 0.3.5 publication and update acceptance

[Tagged CI](https://github.com/kzahel/machine-control/actions/runs/36852715035)
published 0.3.5 with the required restart-repair and legacy-reopen notes. Both
public package families, source/run receipts, exact assets, latest download
links, signed update routes, cumulative changelogs and current-client 204 pass
independent verification. A signed repair fixture automatically installs the
actual public update. Public 0.3.3 installs public 0.3.5 with one native reopen;
released 0.3.5 passes automatic Permissions Restart, permission retention,
revoked access, stale-reference refusal, operator/tray/Stop/Quit acceptance and
testbed restoration. Tactical 052 owns exact execution and remaining physical
Mac/Intel runtime limits. Published tags and bytes are immutable.

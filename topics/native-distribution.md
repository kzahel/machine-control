# Native Distribution

Topic: `native-distribution`

Status: signed Windows workstation preview accepted; consumer and other
platform work remains.

## Direction

**Decision:** Distribute Machine Control as an optional headless native
component with a stable public entry point and platform-specific helpers.
Reuse existing residents and provider boundaries. A consumer such as
YepAnywhere owns install/enable controls, supervision, and agent-tool exposure.
Machine Control owns artifacts, the desktop contract, capability reporting,
and providers. Tauri is not a runtime prerequisite.

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

**Open:** Add YepAnywhere download/enable/supervision and release version
selection;
make macOS providers bundle-relative and prove consent across signed upgrades;
package Linux dependencies and validate a workstation portal/input profile.
Keep actual routes and unsupported capabilities visible.

The [common desktop](unified-desktop-client.md),
[Windows](windows-resident-control.md), [macOS](macos-resident-control.md), and
[Linux](linux-resident-control.md) topics own runtime behavior. The
[Cua dossier](../research/providers/cua-driver.md) owns provider facts and
distribution caveats. Exact dependency/license audits and signed-provider
digest handling remain prerequisites to shipping those providers.

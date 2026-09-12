# Native Distribution

Topic: `native-distribution`

Status: active; first signing infrastructure implemented, hosted validation
pending.

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
notarization, and a minisign-authenticated three-package manifest. CI artifacts
are temporary evidence; the workflow does not publish releases or install
residents. Hosted acceptance is tracked in
[Tactical 035](../docs/tactical/035-native-signing-smoke.md).

The smoke manifest is not the future product update contract. The eventual
consumer needs compatibility/version selection, verified staging, activation,
rollback, and clean disable/removal.

## Remaining product work

**Open:** Separate ordinary Windows startup from the appliance service;
make macOS providers bundle-relative and prove consent across signed upgrades;
package Linux dependencies and validate a workstation portal/input profile.
Keep actual routes and unsupported capabilities visible.

The [common desktop](unified-desktop-client.md),
[Windows](windows-resident-control.md), [macOS](macos-resident-control.md), and
[Linux](linux-resident-control.md) topics own runtime behavior. The
[Cua dossier](../research/providers/cua-driver.md) owns provider facts and
distribution caveats. Exact dependency/license audits and signed-provider
digest handling remain prerequisites to shipping those providers.

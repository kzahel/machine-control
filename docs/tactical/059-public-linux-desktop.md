# 059 — Public Linux desktop and unified 0.5.0

Status: complete

Owning topics: [Linux desktop](../../topics/linux-desktop.md) and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

The user explicitly requested public availability after Linux candidate
acceptance. Publish one 0.5.0 release for all six Mac/Windows/Linux architectures,
including subsequent Mac and shared-browser improvements.

- Required changelog notes describe the supported profile and execution gaps.
- A fresh exact-source unified candidate passes every native packaging gate.
- Exact Linux x64 packages and browser-open replacement remain accepted.
- One immutable annotated tag promotes those bytes through the release script.
- All 29 public assets, signatures and update/download routes are verified.

## Boundaries

Preserve unrelated working changes and use a clean temporary release checkout.
Do not move tags, replace published assets, skip missing platforms, or weaken
native signature/source verification. No outer UI or primary-browser tests.
Use read-only doctor and an exclusive claim for the accepted Linux VM; preserve
its credential handoff, clean owned state and restore its original power.

## Ordered work

### 1 — prepare the complete release

Update the required changelog and unified release guidance. Build a main-only
0.5.0 candidate at the current source, retaining the newer Mac/browser features.

### 2 — accept the exact Linux packages

Authenticate both Linux architectures. Repeat installed x64 Debian/AppImage
acceptance and signed browser-open replacement through the claimed inner route.
Earlier lock/reboot/uninstall evidence remains in Tactical 056.

### 3 — publish and verify public access

Run the single tagged release script against the accepted candidate. Download
and authenticate the complete public asset set. Verify every stable download
redirect and signed production metadata for old/current clients on all platforms.

## Validation and result

**Current:** Required notes and release guidance were committed at
`2b0d8856091e5b610acea0e19ada182acc3568e1`. Unified candidate
[37001606825.1](https://github.com/kzahel/machine-control/actions/runs/37001606825)
passes every native check and signed target. Both Linux architectures authenticate
compiled source/version identity, all 17 payload files, final container digests,
signed versions, and tamper rejection.

The claimed Ubuntu 24.04 GNOME 46 Wayland x64 VM passes 29 fresh source-browser
checks, 54 checks for each exact Debian/AppImage installed package, and 40 signed
replacement checks with Chrome for Testing kept open. The strict localhost HTTPS
sender is an explicit older update fixture; incoming bytes are the exact public
0.5.0 package. Tampering and active-access installation are refused; replacement
relaunches Off with stale authority rejected and browser tasks independently
observed. Production metadata verification does not claim an installed positive
production-feed handoff.

The single release script creates immutable annotated `desktop-v0.5.0` at that
source. Publication run
[37004218394](https://github.com/kzahel/machine-control/actions/runs/37004218394)
stops before draft creation: Tauri uses `aarch64` for its ARM AppImage filename,
while the public contract uses `arm64`. Tooling fix `99b7927` preserves original
receipt names and signed bytes while mapping only the public filename. Its
regression fixture uses actual native names; all 12 publication tests pass.
Local recovery reauthenticates the original tag, required notes, successful
candidate identity and six packages, then stages/uploads/verifies all assets
and publishes the single draft by ID. No tag, receipt, or signed bytes change.
Future candidates now run the full staging gate before promotion is allowed.
All 29 re-downloaded public assets match GitHub SHA-256 digests and candidate
bytes. Native Mac signatures, Gatekeeper and notarization/staples; Windows
installed-payload/signature receipts; and both Linux container inventories and
updater signatures authenticate, with tamper rejection. The required notes and
six-platform manifest match publication. All eight stable download redirects
and the downloads page select 0.5.0. Both shared production and website-proxy
feeds return exact signed metadata for older clients and 204 for current clients
on all six targets.

Owned processes, Debian installation, test CA, dedicated Chrome sandbox helper
and staging are removed; the appliance doctor remains ready. The canonical
stored credential stays mode 0600, initial power is restored, and the exclusive
claim is released. Raw evidence and private target details remain private.

[Desktop 0.5.0](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.0)
and [public downloads](https://machinecontrol.dev/downloads/) are available.
Linux ARM64 desktop execution, physical hardware and other compositors remain
open. Mac/Windows product execution is not rerun by this packaging publication;
the acceptance matrix preserves their existing version-specific evidence.
[Tactical 056](056-linux-desktop.md) owns original Linux acceptance, including
lock/reboot/removal. Subsequent retained Mac/browser features are recorded in
[057](057-macos-until-stopped-release.md) and [058](058-browser-tab-indicators.md).

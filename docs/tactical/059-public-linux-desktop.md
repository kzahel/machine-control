# 059 — Public Linux desktop and unified 0.5.0

Status: in progress

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

Pending candidate and publication. [Tactical 056](056-linux-desktop.md) owns the
first Linux product acceptance; subsequent Mac/browser changes are recorded in
[057](057-macos-until-stopped-release.md) and [058](058-browser-tab-indicators.md).

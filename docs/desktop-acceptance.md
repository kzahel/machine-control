# Desktop product acceptance matrix

Reviewed: 2026-10-02.

This is an index of recorded acceptance for the shared Tauri desktop product,
with earlier runtime evidence kept separate. Linked tactical records own exact
versions, source identity, workflow artifacts, procedures, and limitations.
An unrecorded cell is not a failure or a requirement to test that environment
immediately. Concrete targets and raw evidence stay in private inventory/storage.

## Terms

- **Executed:** the target OS ran the relevant application and independently
  observed its effects. A VM can provide execution evidence.
- **ARM64 Windows execution:** the ARM64 Windows app runs in ARM64 Windows,
  including a Windows VM hosted on Apple silicon. Running macOS on an ARM64
  Mac, cross-building, or installing files on an x64 runner does not establish it.
- **Physical:** the target OS runs directly on hardware rather than in a VM.
  This is a separate environment dimension from executable architecture.
- **Package verified:** signatures, provenance, versions, inventories, and
  tamper rejection passed; this alone does not establish desktop behavior.

## Shared Tauri product by environment

| Target environment | Package evidence | App execution evidence | Record |
| --- | --- | --- | --- |
| macOS ARM64, Tart VM | Signed/notarized public 0.4.8 verified | Operator, grants, effects, tray, restart, and installed production update accepted | [052](tactical/052-macos-production-updates.md), [055](tactical/055-unified-desktop-publication.md) |
| macOS ARM64, physical Mac | Local signed/notarized package verification exists | Full signed Tauri desktop acceptance not recorded; earlier source-native setup/browser evidence below | [051](tactical/051-tauri-macos-desktop.md), [host topic](../topics/host-control.md) |
| macOS Intel | Signed/notarized public packages verified | Intel execution not recorded | [052](tactical/052-macos-production-updates.md) |
| Windows x64, Windows VM on Linux/KVM | Exact signed public 0.4.8 installer and payload verified | Public 0.4.8 UI/grants/lifecycle, browser tasks, production update and uninstall accepted; outside parity, lock/sign-in startup and component compatibility recorded on 0.4.7 | [053](tactical/053-windows-desktop.md), [054](tactical/054-windows-browser-and-arm64.md), [055](tactical/055-unified-desktop-publication.md) |
| Windows ARM64, Windows VM | Signed public 0.4.8 verified; CI package checks run on x64 | New Tauri operator execution not recorded; earlier ARM64 component execution below | [053](tactical/053-windows-desktop.md), [054](tactical/054-windows-browser-and-arm64.md), [055](tactical/055-unified-desktop-publication.md) |
| Windows x64, physical Windows | New candidate package verification does not establish physical execution | New Tauri operator acceptance not recorded; earlier appliance engine evidence below | [physical engine record](evidence/windows-physical-x64.md) |
| Linux x64, Ubuntu GNOME Wayland VM | Initial 0.5.0 Debian/AppImage CI signatures and inventories verified; corrected final candidate pending | 43 development AppImage lifecycle checks; source-native control and browser conformance pass. Signed installed replacement acceptance in progress | [056](tactical/056-linux-desktop.md) |
| Linux ARM64 | Native Ubuntu CI builds, compiled identity, final package inventories/signatures verified | GNOME desktop execution not yet established | [056](tactical/056-linux-desktop.md) |

## Shared Tauri behavior checklist

The two live product environments are macOS ARM64 Tart and Windows x64 VM.
Other environments retain the execution gaps above; do not copy a passing VM
cell into a physical, architecture, or different package-family cell.

| Behavior | macOS ARM64 Tart | Windows x64 VM |
| --- | --- | --- |
| Exact signed installed package | Pass, public 0.4.8 | Pass, public 0.4.8 |
| Off-state refusal and native approval/denial | Pass | Pass |
| Scope narrowing and input pause during approval | Pass | Pass |
| Request timeout and live bounded grant expiry | Not established by the Tauri live record; native contract coverage exists | Pass |
| Stop and stale-generation refusal | Pass | Pass |
| Native emergency Stop shortcut | Pass | Pass |
| Self-interface and protected-operation refusal | Pass | Pass |
| Independent fixture action and capture | Fixture action passed; Tauri-specific capture/hash acceptance not claimed by 052 | Action, Cua capture, artifact hashes passed |
| Capture-superseded Cua token refusal | Not established for this Mac package | Pass, no replay/effect |
| Common CLI | CLI/doctor work with Tauri resident; explicit outside/local product parity not established | Local/outside desktop parity passed on 0.4.3 and browser parity on 0.4.7: shared generation, independent effects, exact artifacts |
| Tray Open/Settings/Check for Updates/Stop/Quit | Pass | Pass |
| Platform permissions/status | Accessibility and Screen Recording ready through restart/update | Ordinary unlocked Medium session/integrity availability; no protected service installed |
| Restart with access revoked | Pass, public 0.4.8 | Pass |
| Close-to-tray and login-startup registration/removal | Not separately established by 052 | Pass; cold-boot/sign-in starts 0.4.5; actual logoff/sign-in starts 0.4.7 in background with access off |
| Companion/provider cleanup on operator failure | No separate companion; forced operator-failure acceptance not recorded | Pass; user-launched fixture survives |
| Lock revokes access, followed by recovery | Live signed Tauri lock/recovery not established by 052 | Lock revocation and logoff/stored-credential sign-in passed |
| In-place unlock integration | Not part of ordinary desktop acceptance | Not tested with this app; optional broker was absent |
| In-app signed update | Pass, production 0.3.5 to 0.4.8 installation, automatic relaunch and Restart; immutable 0.3.3 sender needs one reopen | Pass, 0.4.7 to public 0.4.8 through production with Chrome open; earlier fixture 0.4.4 to 0.4.6 and 0.4.6 to 0.4.7; incoming installer fixes the older 0.4.5 file-lock failure |
| Update refused while access is active | Pass | Pass |
| Permissions/access/generation after replacement | Permissions retained, access off, new generation, stale references refused | Access off, exact new source, new generation, stale requests refused |
| Full extension/browser task | Not rerun on signed Tauri; native-messaging framing passed in 051 | Pass, public 0.4.8: setup, scopes, effects, PNG/hash and restart; local/outside parity recorded on signed 0.4.7 |
| Ordinary uninstall with connected browser and user app | Not separately established | Pass, public 0.4.8: complete payload/registration/startup removal; Chrome and fixture survive; held-image failure preserves exact payload and allows retry |
| Touch ID/out-of-band approval, away mode, presence guard | Not implemented/accepted in this preview | Not implemented/accepted in this preview |
| Public download and production update route | Pass for ARM64/Intel packages; execution evidence is ARM64 | Public x64/ARM64 packages and both production routes verified; execution evidence is x64 |

“In-app update” means the app checks, downloads, verifies, installs, and
relaunches after explicit installation. Automatic unattended installation is
not enabled. A legacy sender requiring reopening and a fixed sender relaunching
automatically are distinct results.

## Earlier evidence that still matters

| Implementation | Environment | Recorded acceptance | Limit |
| --- | --- | --- | --- |
| Source-native Mac resident and extension | ARM64 Tart, Chrome for Testing | Browser typing/click/navigation/capture, grants/revocation, provider identity refusal | [050](tactical/050-macos-host-control-mvp.md); precedes signed Tauri packaging |
| Source-native Mac browser bridge | Physical Mac and guest, real signed-in Chrome | Per-tab raw CDP WebSocket reads/actions/events | [Browser topic](../topics/browser-control.md); not full signed Tauri desktop acceptance |
| Windows ordinary-user component | ARM64 and x64 Windows VMs | Exact signed runtime, Cua effects/capture, provider/IPC resilience; ARM64 upgrade/rollback | [036](tactical/036-windows-workstation-distribution.md); distinct package/profile from Tauri desktop |
| Optional Windows protected unlock component | ARM64 and x64 disposable local-console VMs | Signed install/arming, key/caller/replay refusal, password unlock retaining the same account/logon session | [037](tactical/037-windows-unlock-arming.md); separately installed privileged service, not bundled/armed by Tauri |
| Windows appliance runtime | Physical x64 Windows | Ordinary shell, native/Cua effects/capture, local/remote parity, UAC/elevated control, lock, PIN/password login, boot recovery | [Physical record](evidence/windows-physical-x64.md); older appliance engine, not new Tauri grant/UI lifecycle |
| Linux resident/provider composition | Ubuntu 24.04 GNOME Wayland, ARM64 UTM and x64 KVM VMs | Target-native semantics, capture, input and fixture conformance | [Linux topic](../topics/linux-resident-control.md); no standalone Tauri product |

In-place unlock returns an already logged-in, locked Windows session to its
desktop while preserving its applications and logon session. Logoff followed
by sign-in closes that session and is not equivalent. The optional unlock
component has earlier VM acceptance; its integration with the new Tauri app
has not been exercised. It is not an ordinary desktop-preview prerequisite.

## Follow-up priorities

**Proposal:** Repeat exact signed product tests in ARM64 Windows when a
registered target with a ready credential handoff is available. No such local target is currently
registered. Repeat a full extension task on the signed Mac Tauri package.
These do not require physical-machine approval or privileged unlock integration.

**Open:** Physical-machine product testing should target specific gaps such as
multi-monitor/DPI, GPU capture, suspend/resume, and personal-workstation
permission/startup behavior before broader support claims. It is useful later
environment coverage, not an immediate blocker for the accepted VM preview.

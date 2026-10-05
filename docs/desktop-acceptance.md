# Desktop product acceptance matrix

Reviewed: 2026-10-05.

This is an index of recorded acceptance for the shared Tauri desktop product,
with earlier runtime evidence kept separate. Linked tactical records own exact
versions, source identity, workflow artifacts, procedures, and limitations.
Current public 0.5.4 package verification for all six targets is recorded in
[091](tactical/091-desktop-until-stopped.md); execution keeps its specific
versions. All six installed CLI payloads authenticate and pass hosted offline
relocation smoke, including native Windows ARM64; this is separate from GUI
execution.
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
| macOS ARM64, Tart VM | Signed/notarized public 0.5.4 verified | Signed 0.5.4 indefinite selection, null countdown, narrowed approval, fixture effect, prompt pause and Stop pass. Installed CLI replacement from an owned signed 0.5.2 fixture to public 0.5.3 passes with active-access refusal, automatic relaunch, access off and YA reauthentication; targeted signed 0.4.10 browser indicators and fixture effects pass under appliance policy; 0.4.9 until-stopped access, Stop, restart and bounded approval pass; earlier full operator and production-update evidence is 0.4.8 | [052](tactical/052-macos-production-updates.md), [055](tactical/055-unified-desktop-publication.md), [057](tactical/057-macos-until-stopped-release.md), [058](tactical/058-browser-tab-indicators.md), [062](tactical/062-installed-agent-cli.md#published-mac-installed-cli-replacement); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |
| macOS ARM64, physical Mac | Public signed/notarized 0.4.8 package authenticated | Partial smoke: consent/readiness, off-state refusal, visible approval, independent AX counter effect, exact-window capture, keyboard delivery and revoke; full desktop acceptance remains open | [host topic](../topics/host-control.md) |
| macOS Intel | Signed/notarized public 0.5.4 verified | Intel GUI execution not recorded | [052](tactical/052-macos-production-updates.md), [057](tactical/057-macos-until-stopped-release.md), [058](tactical/058-browser-tab-indicators.md); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |
| Windows x64, Windows VM on Linux/KVM | Exact signed public 0.5.4 installer and payload verified | Public 0.4.8 UI/grants/lifecycle, browser tasks, production update and uninstall accepted; outside parity, lock/sign-in startup and component compatibility recorded on 0.4.7 | [053](tactical/053-windows-desktop.md), [054](tactical/054-windows-browser-and-arm64.md), [055](tactical/055-unified-desktop-publication.md), [057](tactical/057-macos-until-stopped-release.md), [058](tactical/058-browser-tab-indicators.md); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |
| Windows ARM64, Windows VM | Signed public 0.5.4 verified; native ARM64 CLI relocation smoke passes | Signed 0.5.4 visible indefinite access, fixture effect, Pause/Resume, Stop and bounded approval pass; production 0.5.3 to 0.5.4 update relaunches off with a new generation and rejects stale requests | [053](tactical/053-windows-desktop.md), [054](tactical/054-windows-browser-and-arm64.md), [057](tactical/057-macos-until-stopped-release.md), [058](tactical/058-browser-tab-indicators.md); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |
| Windows x64, physical Windows | New candidate package verification does not establish physical execution | New Tauri operator acceptance not recorded; earlier appliance engine evidence below | [physical engine record](evidence/windows-physical-x64.md) |
| Linux x64, Ubuntu GNOME Wayland VM | Exact signed public 0.5.4 Debian/AppImage bytes, signatures and inventories verified | Public 0.5.0 fresh installed UI/grants/effects/lifecycle and signed replacement with browser tasks pass; earlier same-core lock, reboot/startup and removal evidence remains in 056 | [056](tactical/056-linux-desktop.md), [059](tactical/059-public-linux-desktop.md); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |
| Linux ARM64, Ubuntu GNOME Wayland VM | Public 0.5.4 native Ubuntu CI builds, compiled identity, container inventories/signatures and tamper rejection verified | Exact 0.5.4 Debian visible indefinite access/status, null countdown, AT-SPI delivery, independent GTK counter effect and Stop pass; portal/browser/lifecycle execution remains separate | [056](tactical/056-linux-desktop.md), [059](tactical/059-public-linux-desktop.md); [063](tactical/063-six-platform-desktop-release.md), [091](tactical/091-desktop-until-stopped.md) |

## Focused Windows desktop UAC candidate acceptance

The unsigned x64 development candidate passes 21 checks in a Windows-hosted
VirtualBox VM through the real operator UI and desktop owner channel. Setup
cancellation/install/removal, secure consent capture/hash, typed cancellation
and approval, independent elevated counter effects, caller/scope/credential
refusals, stale references, disconnect, Pause and Stop pass with UAC policy
unchanged. The helper is removed afterward. [Tactical 097](tactical/097-windows-desktop-uac.md)
records the exact runtime hash, methodology, friction and limits.

These checks do not promote the public 0.5.4 package or establish signed
replacement, ARM64 live, physical, localized consent or credential support.
The historical ordinary-profile checklist below retains its own scope.

## Shared Tauri behavior checklist

Focused unreleased Windows bounded locked-use evidence is recorded in
[Tactical 101](tactical/101-windows-desktop-locked-use.md), using an unsigned
x64 development app and the native route in a Windows-hosted VirtualBox VM.
It adds existing-session unlock and independently guarded relock; it does not
retroactively qualify the historical signed ordinary-profile cells below.
[Tactical 102](tactical/102-windows-covered-control.md) adds focused opaque
one-display VM presentation, underlying native capture/input and initial-state
cleanup checks. Signed installed, broad Cua post-unlock, ARM64 live and hardware
takeover acceptance remain open.

[Tactical 103](tactical/103-windows-activity-pause.md) adds focused native
activity monitoring and real ordinary/covered virtual-keyboard takeover,
retained consent and fresh ownership after quiet. Its evidence does not
qualify physical hardware or owner-unlocked local-use presentation.

[Tactical 104](tactical/104-windows-pointer-gestures.md) adds 36 focused x64
VM checks for native movement, both signed wheel axes, left/right drag effects
and timing, operator-path protection and mid-drag Pause/Stop release. This
unsigned source evidence does not qualify signed installs, live ARM64,
physical/multiple-display or broader protected-transition behavior.

This historical broad checklist covers macOS ARM64 Tart, Windows x64 VM, and
Linux x64 GNOME Wayland VM. Focused 0.5.4 ARM64 results are recorded separately
below; the broad checklist is not a claim that every cell was rerun on 0.5.4.
Linux installed tests execute the exact signed bytes
promoted to public 0.5.0; production metadata is verified separately.
Other environments retain the execution gaps above; do not copy a passing VM
cell into a physical, architecture, or different package-family cell.

| Behavior | macOS ARM64 Tart | Windows x64 VM | Linux x64 GNOME VM |
| --- | --- | --- | --- |
| Exact signed installed package | Pass, public 0.4.8 | Pass, public 0.4.8 | Pass, exact public 0.5.0 Debian/AppImage bytes |
| Off-state refusal and native approval/denial | Pass | Pass | Pass |
| Scope narrowing and input pause during approval | Pass | Pass | Installed prompt pause passes; narrowing has contract coverage |
| Request timeout and live bounded grant expiry | Not established by the Tauri live record; native contract coverage exists | Pass | Installed grant expiry passes; request timeout has contract coverage |
| Manual until-stopped access | Pass, signed public 0.4.9; targeted 0.5.4 regression below | Implemented in 0.5.4; new installed evidence is ARM64 below | Implemented in 0.5.4; new installed evidence is ARM64 below |
| Stop and stale-generation refusal | Pass | Pass | Pass |
| Native emergency Stop shortcut | Pass | Pass | Pass, opt-in GNOME shortcut |
| Self-interface and protected-operation refusal | Pass | Pass | Operator/approval protected; protected control unavailable |
| Independent fixture action and capture | Fixture action passed; Tauri-specific capture/hash acceptance not claimed by 052 | Action, Cua capture, artifact hashes passed | Independent semantic, pointer and Unicode effects; portal PNG/hash passes |
| Capture-superseded Cua token refusal | Not established for this Mac package | Pass, no replay/effect | Not applicable; this app uses the portal provider |
| Common CLI | CLI/doctor work with Tauri resident; explicit outside/local product parity not established | Local/outside desktop parity passed on 0.4.3 and browser parity on 0.4.7: shared generation, independent effects, exact artifacts | Local/outside generation, effects and artifact hashes pass |
| Tray Open/Settings/Check for Updates/Stop/Quit | Pass | Pass | Pass; near-clock icon visually inspected |
| Platform permissions/status | Accessibility and Screen Recording ready through restart/update | Ordinary unlocked Medium session/integrity availability; no protected service installed | Ordinary unlocked GNOME Wayland; visible sharing consent, no root input service |
| Restart with access revoked | Pass, public 0.4.8 | Pass | Pass, access Off and sharing closed |
| Close-to-tray and login-startup registration/removal | Not separately established by 052 | Pass; cold-boot/sign-in starts 0.4.5; actual logoff/sign-in starts 0.4.7 in background with access off | Pass; real reboot starts exact candidate in background with access/sharing Off |
| Companion/provider cleanup on operator failure | No separate companion; forced operator-failure acceptance not recorded | Pass; user-launched fixture survives | Pass; independent user fixture survives |
| Lock revokes access, followed by recovery | Live signed Tauri lock/recovery not established by 052 | Lock revocation and logoff/stored-credential sign-in passed | Lock revocation passes; reboot returns to accepted unlocked session |
| In-place unlock integration | Not part of ordinary desktop acceptance | Not tested with this app; optional broker was absent | Not tested; no protected unlock integration |
| In-app signed update | Pass, production 0.3.5 to 0.4.8 installation, automatic relaunch and Restart; immutable 0.3.3 sender needs one reopen | Pass, 0.4.7 to public 0.4.8 through production with Chrome open; earlier fixture 0.4.4 to 0.4.6 and 0.4.6 to 0.4.7; incoming installer fixes the older 0.4.5 file-lock failure | Pass, strict signed localhost HTTPS fixture to exact public 0.5.0 bytes, Chrome stays open; installed positive production-feed handoff not exercised |
| Update refused while access is active | Pass | Pass | Pass, including access armed during download |
| Permissions/access/generation after replacement | Permissions retained, access off, new generation, stale references refused | Access off, exact new source, new generation, stale requests refused | Access/sharing Off, exact source, new generation and stale request refusal |
| Full extension/browser task | Targeted signed 0.4.10 snapshot/click/navigation and marker lifecycle pass under appliance policy; workstation browser approval not rerun | Pass, public 0.4.8: setup, scopes, effects, PNG/hash and restart; local/outside parity recorded on signed 0.4.7 | Pass after signed replacement: native setup, scopes, navigation, effects and PNG/hash |
| Controlled-tab favicons and new-tab groups | Pass, signed 0.4.10: 20 live checks and fresh native capture; user/site edits preserved | New markers not executed | New markers not executed |
| Ordinary uninstall with connected browser and user app | Not separately established | Pass, public 0.4.8: complete payload/registration/startup removal; Chrome and fixture survive; held-image failure preserves exact payload and allows retry | Pass; installed files removed, Chrome and user app survive, user data retained |
| Touch ID/out-of-band approval, away mode, presence guard | Not implemented/accepted in this preview | Not implemented/accepted in this preview | Not implemented/accepted in this preview |
| Public download and production update route | Pass for ARM64/Intel packages; execution evidence is ARM64 | Public x64/ARM64 packages and both production routes verified; execution evidence is x64 | Public x64/ARM64 packages, all four Linux download routes and both production metadata routes verified in 059 |

“In-app update” means the app checks, downloads, verifies, installs, and
relaunches after explicit installation. Automatic unattended installation is
not enabled. A legacy sender requiring reopening and a fixed sender relaunching
automatically are distinct results.

## Focused public 0.5.4 ARM64 acceptance

All three installed packages were authenticated at the exact release source.
[Tactical 091](tactical/091-desktop-until-stopped.md) owns workflow identities,
procedures, outcomes and limits. All access was stopped after testing.

| Environment | Executed checks | Limits |
| --- | --- | --- |
| Mac ARM64 Tart | Visible indefinite selection, null countdown, native approval/denial/narrowing, independent fixture action, self/protected refusal, prompt pause, Stop | Focused native regression; no new physical, browser, restart or updater claim |
| Windows ARM64 VM | Exact signed installed inventory, visible indefinite selection, null countdown, independent fixture action, Pause/Resume, Stop, timed agent approval; actual 0.5.3 production update with access exclusion, automatic relaunch off, exact new source and stale-generation refusal | No new ARM64 browser, lock/login, startup or physical claim |
| Linux ARM64 GNOME Wayland VM | Exact signed Debian source, ready session, visible indefinite selection/status, null countdown, AT-SPI action, independent GTK counter effect and Stop | No new ARM64 portal capture/input, AppImage replacement, browser, lifecycle or physical claim |

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

**Proposal:** Extend the focused ARM64 Windows/Linux execution above to
browser and lifecycle coverage. Repeat a full extension task on the signed
Mac Tauri package. These are separate from physical-machine and privileged
unlock integration coverage.

**Open:** Physical-machine product testing should target specific gaps such as
multi-monitor/DPI, GPU capture, suspend/resume, and personal-workstation
permission/startup behavior before broader support claims. It is useful later
environment coverage, not an immediate blocker for the accepted VM preview.

# Implementation Tacticals

- [090 — Retained desktop appliance rebuild](090-retained-desktop-appliance-rebuild.md)
  (complete): disk analysis and retained Windows/Linux provisioning acceptance.
- [092 — Dated provisioning journals](092-provisioning-journals.md): automatic
  command/phase observations and private agent friction notes.

Bounded implementation plans and execution records live here.

Tacticals are selected from current [`topics/`](../../topics/README.md) and
should link the relevant [provider/platform research](../../research/README.md)
rather than embedding another candidate survey or experiment log.

Use zero-padded numeric prefixes for new tactical documents, such as
`000-topic.md` and `001-next-topic.md`. Keep one coherent implementation slice
per document. A coordinating parent tactical is acceptable when it makes the
ordering of several independently reviewable slices explicit.

Every tactical should identify:

- status: `proposed`, `active`, `blocked`, `complete`, or `superseded`;
- the owning topic or topics;
- objective and observable completion conditions;
- boundaries and explicit non-goals;
- named implementation steps in recommended order;
- validation and evidence requirements; and
- the result, deviations, and remaining work when execution ends.

Name steps for the product surface or work they cover, using headings such as
`### 3 — prove remote direct control`. Do not invent letter-and-number lane
codes that require a separate lookup table. If a step is difficult to name,
its boundary probably needs more work.

Completed tacticals remain as execution records. Continuing guidance belongs
in the owning topic and architecture documents; if they disagree with an old
tactical, update the tactical's status or add a short supersession note rather
than treating its historical plan as current truth.

When a tactical produces a related commit series, use the owning topic slug in
the commits' `Topic:` trailers and register that exact string in
[`topics.md`](../../topics.md) when the first commit is created.

## Tactical index

| Tactical | Status | Scope |
| --- | --- | --- |
| [`076-resident-pause-enforcement.md`](076-resident-pause-enforcement.md) | active | Windows operator pause and dispatch fencing; shared UI and Mac integration/native acceptance gates |
| [`075-admission-contract-and-arbiter.md`](075-admission-contract-and-arbiter.md) | complete (contract slice) | Versioned intents/status, composed pause, complete resource sets, offers, owner fencing and deterministic deadline/race checks |
| [`074-access-admission-and-pause.md`](074-access-admission-and-pause.md) | active | Coordinating plan for resumable access pauses, polite admission, queue liveness, fencing and shared physical/VM desktop resources |
| [`073-macos-locked-display-wake.md`](073-macos-locked-display-wake.md) | complete (bounded) | Inactive-display startup and two successive physical covered tasks passed without external wake or new approval |
| [`072-macos-helper-update-maintenance.md`](072-macos-helper-update-maintenance.md) | complete (bounded) | Physical signed-update maintenance and same-build relaunch passed; preserve the locked-use choice |
| [`071-desktop-caller-authorization.md`](071-desktop-caller-authorization.md) | active; identity primitive validated | Opt-in automatic grants for trusted YA Desktop, authenticated session authority, revocation and fresh Mac installation acceptance; npm CLI trust next |
| [`070-macos-locked-access-retention.md`](070-macos-locked-access-retention.md) | complete (bounded) | Physical idle-lock, successive-task and expiry retention passed; takeover/recovery live-tested, scripted timing caveat |
| [`069-desktop-audit-and-diagnostics.md`](069-desktop-audit-and-diagnostics.md) | complete; source-native VMs accepted | Durable native audit history, private diagnostics, retained Activity, export and storage-failure validation |
| [`068-windows-agent-discovery.md`](068-windows-agent-discovery.md) | implemented; x64 accepted; release gates open | Main-executable CLI forwarding, bare-launch guidance, user PATH registration and resolved installation identity |
| [`064-macos-locked-use.md`](064-macos-locked-use.md) | complete | Mac locked use with covered displays, native takeover, and failure relock; open-lid only |
| [`065-macos-helper-permission.md`](065-macos-helper-permission.md) | complete | Native helper approval in Permissions; locked-use checkbox only changes the preference |
| [`066-macos-physical-locked-use.md`](066-macos-physical-locked-use.md) | trial complete; acceptance open | SIP-enabled physical helper setup passed; automatic covered unlock failed and manual recovery passed |
| [`067-macos-physical-unlock-trigger.md`](067-macos-physical-unlock-trigger.md) | bounded completion trial passed | Native physical lock, integrated targeted unlock, covered effects/capture and completion relock; further acceptance in 070 |
| [`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md) | complete | Coordinating Windows milestone; full control, reproducible bootstrap, sustained real-app acceptance, and disposable seal verification |
| [`001-windows-system-shell-acceptance.md`](001-windows-system-shell-acceptance.md) | complete | Cua-first acceptance run across the real Windows system shell; selected a hybrid facade |
| [`002-windows-full-target-native-control.md`](002-windows-full-target-native-control.md) | complete | Full resident Windows control across ordinary, elevated, UAC, lock/login, lifecycle, and physical hardware boundaries |
| [`003-windows-credential-login.md`](003-windows-credential-login.md) | complete | Secret-safe stock PIN and password Credential Provider login from pre-login Windows |
| [`004-windows-provider-composition-and-agent-ergonomics.md`](004-windows-provider-composition-and-agent-ergonomics.md) | complete | Compose Cua and native Windows routes behind the owned facade and prove a realistic local/remote agent workflow |
| [`005-windows-clean-appliance-and-real-application-acceptance.md`](005-windows-clean-appliance-and-real-application-acceptance.md) | complete | Bootstrap a clean MachineControl-layer Windows appliance, run sustained inbox-app workflows, and verify a retained seal; source-isolation deviation recorded |
| [`006-windows-safety-launch-efficiency-and-image-factory.md`](006-windows-safety-launch-efficiency-and-image-factory.md) | complete | Fail-closed UUID target identity, native packaged-app/window control, compact unchanged-aware semantics, four-app local/remote acceptance, and a generalized-image factory with disposable OOBE proof |
| [`007-windows-iso-factory-acceptance.md`](007-windows-iso-factory-acceptance.md) | complete | Live official unactivated Windows ARM64 ISO-to-appliance acceptance through unattended Setup, resident bootstrap, product installation, and cleanup |
| [`008-macos-ordinary-session-resident-control.md`](008-macos-ordinary-session-resident-control.md) | complete | Tart-based macOS resident facade, native/Cua comparison, guest-local input, real system/application workflows, and stopped appliance acceptance |
| [`009-macos-administrator-sheet-control.md`](009-macos-administrator-sheet-control.md) | complete | Target-resident control of normal macOS administrator sheets with a one-shot non-echoing credential channel and independent effects |
| [`010-macos-full-aqua-software-testing.md`](010-macos-full-aqua-software-testing.md) | complete | Accepted logged-in Tart software-testing control through target-native semantics, visual fallback, privacy prompts, system dialogs, and administration with outer UI prohibited; image omissions recorded |
| [`011-macos-java-electron-framework-coverage.md`](011-macos-java-electron-framework-coverage.md) | complete | Closed the prepared Tart image's Java and Electron omissions with pinned runtimes and four-framework target-native acceptance |
| [`012-linux-gnome-wayland-resident-control.md`](012-linux-gnome-wayland-resident-control.md) | complete | Accepted guarded Ubuntu GNOME Wayland resident semantics, capture, input, system surfaces, provider composition, and reboot recovery |
| [`013-unified-desktop-entry-and-conformance.md`](013-unified-desktop-entry-and-conformance.md) | complete | Common target lifecycle/readiness and resident-control client with explicit platform escape hatches and three-desktop conformance |
| [`014-repository-consolidation-and-cutover.md`](014-repository-consolidation-and-cutover.md) | complete | History-preserving import and atomic cutover of public platform testbeds into the canonical monorepo, with dotfiles retaining private inventory |
| [`015-cross-platform-coordinator-portability.md`](015-cross-platform-coordinator-portability.md) | complete | Native macOS/Linux/Windows coordinator execution, typed controller eligibility, portable launchers, CI, and in-appliance validation |
| [`016-device-readiness-and-android-unlock.md`](016-device-readiness-and-android-unlock.md) | complete | Common outer device doctor, shared Android-family ADB transport, guarded Android PIN unlock, and bounded iOS reboot/reconnect evidence |
| [`017-vm-workspaces-and-storage-policy.md`](017-vm-workspaces-and-storage-policy.md) | complete | Portable persistent/isolated/candidate workspace intent, provider capabilities, storage policy, and guarded UTM/Tart implementations |
| [`018-appliance-readiness-and-promotion.md`](018-appliance-readiness-and-promotion.md) | complete | Reuse-in-place Windows/Linux readiness, bounded ensure-ready, exact candidate promotion, and live UTM disposable outcomes |
| [`019-ios-runner-and-common-control.md`](019-ios-runner-and-common-control.md) | complete | Explicit iOS common controls, runner signing-lifetime refresh, and passcode-state conformance |
| [`020-windows-post-update-and-appliance-certification.md`](020-windows-post-update-and-appliance-certification.md) | complete | Minimized Windows post-update audit/repair, reproducible development bootstrap, and on-demand appliance certification |
| [`021-linux-post-update-and-appliance-certification.md`](021-linux-post-update-and-appliance-certification.md) | complete | Minimized Linux post-update audit/repair, reproducible package profiles, and on-demand appliance certification |
| [`022-common-maintenance-and-macos-certification.md`](022-common-maintenance-and-macos-certification.md) | complete | Common platform-maintenance dispatch plus minimized macOS audit/repair, reproducible profiles, and exact-source certification |
| [`023-chromeos-common-readiness-and-maintenance.md`](023-chromeos-common-readiness-and-maintenance.md) | complete | Common ChromeOS doctor plus partial runtime audit/repair and current-boot SSH persistence proof |
| [`024-quest-wireless-adb.md`](024-quest-wireless-adb.md) | complete | Guarded temporary Quest ADB-over-TCP bound to the pinned USB identity, with private endpoint state and cable-free fallback |
| [`025-windows-non-pty-administration-readiness.md`](025-windows-non-pty-administration-readiness.md) | complete | Native PowerShell OpenSSH shell, single bounded Windows doctor probe, and changed-epoch reboot persistence |
| [`026-exclusive-target-use-claims.md`](026-exclusive-target-use-claims.md) | complete | Coordinator-neutral expiring exclusive-use claims for accepted VM targets, exact-resource arbitration, workspace composition, and agent-facing enforcement |
| [`027-windows-claimed-direct-transport.md`](027-windows-claimed-direct-transport.md) | complete | Single-validation direct Windows administration and resident transport under an exclusive target-use claim |
| [`028-linux-libvirt-controller-host.md`](028-linux-libvirt-controller-host.md) | complete | Native x86_64 Windows and Linux appliances on a hardware-accelerated Linux libvirt/QEMU/KVM controller host |
| [`029-disruptive-target-use-claims.md`](029-disruptive-target-use-claims.md) | complete | UI-less ordinary/disruptive claim classes and authoritative outer VM capture/input enforcement |
| [`030-chromeos-closed-lid-readiness.md`](030-chromeos-closed-lid-readiness.md) | in progress | Required ChromeOS closed-lid power policy, boot reapplication, doctor enforcement, and live SSH proof |
| [`031-ios-adb-parity-operations.md`](031-ios-adb-parity-operations.md) | complete | Adaptive physical-iOS diagnostics with app management and file exchange, typed uninstall, bounded app/system logs, and native crash-report collection; weakly attributable process inventory remains limited |
| [`032-macos-authorization-unlock-investigation.md`](032-macos-authorization-unlock-investigation.md) | complete | Disposable macOS authorization-plug-in unlock, explicit arming, normal-password fallback, and removal; screen shielding deferred |
| [`033-macos-sip-authorization-unlock.md`](033-macos-sip-authorization-unlock.md) | complete | Ad-hoc plug-in loaded and unlocked twice with SIP, authenticated-root protection, and Gatekeeper enabled; native consent bootstrap without outer control |
| [`034-macos-session-state-and-unlock.md`](034-macos-session-state-and-unlock.md) | complete | Truthful lock and unlock readiness in doctor/status, explicit installer and authenticated helper, guarded native unlock, and SIP-enabled appliance conformance |
| [`035-native-signing-smoke.md`](035-native-signing-smoke.md) | complete | Main-only native CI fixtures, publisher signing/notarization, and a verified three-platform manifest without release publication |
| [`036-windows-workstation-distribution.md`](036-windows-workstation-distribution.md) | complete | Ordinary-user Windows package with explicit privilege boundaries and appliance/CLI compatibility |
| [`037-windows-unlock-arming.md`](037-windows-unlock-arming.md) | complete | Optional privileged unlock service with UAC consent, controller-bound arming and native Windows acceptance |
| [`038-windows-factory-stage-diagnostics.md`](038-windows-factory-stage-diagnostics.md) | complete | Claimed Linux factory stage checks, exact media-state projection, and resumable first-logon attestation |
| [`039-linux-windows-factory-stages.md`](039-linux-windows-factory-stages.md) | complete (Linux route) | Linux libvirt Windows precreation stages, unique Pro catalog, bootstrap recovery, and fresh-candidate acceptance |
| [`040-linux-kvm-ubuntu-factory-stages.md`](040-linux-kvm-ubuntu-factory-stages.md) | complete (Linux route) | Native x86_64 Ubuntu precreation and claimed factory stages with fresh-candidate acceptance |
| [`041-macos-utm-ubuntu-precreation-stages.md`](041-macos-utm-ubuntu-precreation-stages.md) | complete | Read-only Mac UTM Ubuntu precreation report and fresh-candidate smoke |
| [`042-macos-utm-ubuntu-candidate-stages.md`](042-macos-utm-ubuntu-candidate-stages.md) | complete | Claimed UTM Ubuntu stages with fresh-candidate certification and clean stop |
| [`043-macos-utm-windows-factory-stages.md`](043-macos-utm-windows-factory-stages.md) | complete | Read-only Mac UTM Windows stages and fresh exact-source certification |
| [`044-macos-tart-bootstrap-stages.md`](044-macos-tart-bootstrap-stages.md) | complete | Fresh prepared and Apple IPSW paths reached all stages complete and ready doctor |
| [`045-macos-tart-outer-keyboard.md`](045-macos-tart-outer-keyboard.md) | complete | Guest-oracle diagnosis and correction of Tart Shift/Command delivery; untested modifiers remain guarded |
| [`046-scoped-target-tasks.md`](046-scoped-target-tasks.md) | complete | Scoped claim/workspace runner, failure fixtures, and live Mac renewal/release; native Windows and live workspace acceptance unverified |
| [047-macos-resident-resource-reliability.md](047-macos-resident-resource-reliability.md) | complete | Idle probe descriptor ownership, readiness diagnostics, bounded regressions, and live workload/recovery evidence |

- [`048-linux-rebuild-credential-handoff.md`](048-linux-rebuild-credential-handoff.md):
  disposable Linux recreation, stored-password handoff and installed readiness.
- [`049-linux-credential-promotion-gate.md`](049-linux-credential-promotion-gate.md):
  enforced Linux credential verification and factory/promotion completion gate.
- [`050-macos-host-control-mvp.md`](050-macos-host-control-mvp.md) (active):
  shared resident package, grant broker, menu bar approval, local host target,
  and unpacked browser extension; host installation remains.
- [`051-tauri-macos-desktop.md`](051-tauri-macos-desktop.md) (active):
  shared Tauri desktop UX, embedded native Mac resident, signed CI artifacts,
  and exact-artifact Tart acceptance.
- [`052-macos-production-updates.md`](052-macos-production-updates.md) (complete):
  production update routing, menu-bar commands, signed 0.3.5 publication,
  automatic repair-fixture handoff, and legacy public-client Tart acceptance.
- [`053-windows-desktop.md`](053-windows-desktop.md) (complete for x64 VM preview):
  native Windows desktop grants, shared Tauri operator, supervised companion,
  signed installers, and installed VM acceptance.
- [`054-windows-browser-and-arm64.md`](054-windows-browser-and-arm64.md) (active):
  Windows native browser integration, signed VM acceptance, and separately
  observed ARM64 product execution.

- [`055-unified-desktop-publication.md`](055-unified-desktop-publication.md) (complete):
  one Mac/Windows release script, complete signed publication, downloads, and
  production update acceptance.
- [`056-linux-desktop.md`](056-linux-desktop.md) (complete for x64 preview): ordinary-user GNOME
  Wayland portal control, shared Tauri app, grants, packages, and acceptance.
- [`057-macos-until-stopped-release.md`](057-macos-until-stopped-release.md) (complete):
  manual Mac access without a timer, signed VM acceptance, and stable 0.4.9
  Mac/Windows publication.
- [`058-browser-tab-indicators.md`](058-browser-tab-indicators.md) (complete):
  owned browser favicon markers and new-tab groups, lifecycle cleanup, claimed
  Mac VM acceptance, and desktop 0.4.10 publication.
- [`059-public-linux-desktop.md`](059-public-linux-desktop.md) (complete): one
  public six-architecture desktop release, exact Linux acceptance, downloads
  and production update metadata.
- [`060-native-update-discovery.md`](060-native-update-discovery.md) (complete):
  native silent startup/daily checks, shared Settings/tray state, and metadata-only
  CLI discovery through existing resident transports.

- [`061-native-sudo.md`](061-native-sudo.md) (complete for signed ARM64 helper acceptance): bundled native administrator authentication and dedicated Mac appliance acceptance.

- [062-installed-agent-cli.md](062-installed-agent-cli.md) (completed): package the shared Python client and prove installed desktop consumers.

- [`063-six-platform-desktop-release.md`](063-six-platform-desktop-release.md) (complete):
  desktop 0.5.3 publication for all six Mac/Windows/Linux architectures.

- [`064-windows-exact-semantic-references.md`](064-windows-exact-semantic-references.md) (complete):
  exact native UIA reference resolution and duplicate-label regression coverage.

- [077 — Mac locked quiet resumption](077-mac-quiet-resumption.md): root pause reasons, locked quiet eligibility and operator Resume; physical acceptance pending.

- [078 — Live desktop admission channels](078-live-admission-channels.md): owner-bound queues, fenced dispatch, activity monitor and standalone client; native acceptance pending.

- [079 — Consent and control notices](079-consent-and-control-notices.md): Mac consent/pause persistence, native notices and dispatch fencing; physical acceptance pending.

- [080 — Live claim channel enforcement](080-live-claim-channel-enforcement.md): adapter-side exact claim checks, periodic liveness and prompt transport cleanup.
- [081 — Mac admission presentation and consent acceptance](081-macos-admission-physical-acceptance.md).
- [082 — Live queued target-use claims](082-queued-target-claims.md).
- [083 — Long-lived admission channels](083-long-lived-admission-channels.md).
- [084 — Native outer desktop admission](084-native-outer-desktop-admission.md).

- [085 — Mac admission transport cleanup](085-macos-admission-transport-cleanup.md).

- [086 — Native desktop delegation](086-native-desktop-delegation.md).
- [087 — Prepared console delegation](087-prepared-console-delegation.md).

- [088 — Targeted native effect observation](088-targeted-native-effect-observation.md).

- [089 — Durable target claim and command history](089-target-operation-audit.md).

- [091 — Indefinite manual desktop access](091-desktop-until-stopped.md):
  Completed: Windows/Linux lifetime support, Mac regression, ARM64 VM acceptance
  and unified public 0.5.4 with production Windows replacement.

- [094 — Windows development host and Hyper-V test loop](094-windows-hyperv-development-host.md):
  QEMU/WHPX Home probes pass; Windows 11 TPM preflight blocks qualification.
  Pending native builds, provider lifecycle,
  Windows provisioning, isolated workspaces and host-to-guest acceptance.

- [093 — Session entry-point and authority audit](093-session-entry-point-audit.md):
  completed bounded source inventory, claim/channel fixtures and first session
  migration boundary; no runtime changes.

- [095 — Windows required owner session and CLI compatibility](095-windows-required-owner-session.md):
  desktop dispatch enforcement, negotiated short sessions and retained CLI
  streams; installed Windows acceptance pending.

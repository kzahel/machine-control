# 053 — Windows desktop application

Status: complete for the signed x64 VM preview; remaining gates below

Owning topics: [Windows desktop](../../topics/windows-desktop.md),
[host control](../../topics/host-control.md),
[native distribution](../../topics/native-distribution.md), and
[Windows resident control](../../topics/windows-resident-control.md).

## Objective and completion conditions

Deliver a signed Windows preview of the shared Tauri app, bundling the existing
self-contained ordinary-user runtime with native grants, process supervision,
compact tray/settings UX, and an installed lifecycle proved on dedicated VMs.

- Ordinary operations refuse before dispatch when access is off, insufficient,
  paused, expired, revoked, or bound to a stale generation.
- Agent requests support approval, denial, narrowed scope/duration, and timeout;
  only the native operator channel can approve.
- Stop, Quit, restart, lock/session change, operator failure, and replacement
  revoke access and invalidate references. Child processes are cleaned up.
- Controlled routes cannot approve or act on the operator's own interface.
- Standard-user installation supports the shared tabs, tray Open/Settings/
  Updates/Stop/Quit, startup preference, and an emergency Stop shortcut.
- ARM64/x64 candidates carry publisher/updater signatures. Verification checks
  final bytes, provenance, and tamper rejection.
- Exact signed installed candidates prove independent fixture action/capture,
  grants, lifecycle, update handoff, and local/outside parity.
- Existing component/appliance profiles remain compatible. Report unmet gates
  honestly rather than treating a build as installed acceptance.

## Boundaries

Keep the .NET engine and providers as a bundled companion with a distinct
desktop instance. Do not install protected services, weaken UAC, or widen user/
session authority. Browser integration, Linux, protected workstation control,
connection-bound grants, and physical hardware acceptance are subsequent work.

Use the common doctor and exclusive claims for VM operations. Outer control is
authorized for setup/recovery when needed. Preserve initial power state and
credential handoff; private captures/logs stay outside Git. Signed CI candidates
are the initial acceptance surface; publication is a separate final step.

## Ordered work

### 1 — enforce Windows desktop grants

Add a tested native broker: off by default, scopes, bounded requests/decisions,
local arming, revoke/expiry, prompt pause, update guard, bounded activity, and
generation invalidation. Connect before provider dispatch. Keep approval off
the public pipe. Add native self-interface and desktop/session protection.

### 2 — connect the operator and supervise the resident

Implement the Tauri Windows adapter and private duplex operator transport.
Bundle the self-contained runtime; own companion/provider lifetime with a
kill-on-close process job. Implement Stop, Quit/restart, and startup preference.
Adapt permissions and scopes while preserving the concise settings UX.

### 3 — build and verify signed installers

Add Windows bundle configuration, main-only ARM64/x64 signed candidate CI,
final-byte/provenance evidence, installer/updater verification, and mandatory
versioned notes for publication. Preserve Mac releases and the independent
workstation component family.

### 4 — prove the installed app

Use claimed accepted appliances and exact candidate bytes. Test approval,
denial, narrowing, timeout, expiry, Stop, own-interface refusal, independent
fixture action/capture, session change, restart, close-to-tray, tray commands,
companion failure, installation/removal, and signed update handoff. Check stale
references after revocation/update and component/appliance regressions. Record
architecture-specific omissions.

## Validation

Run broker contracts, `dotnet format --verify-no-changes`, native Windows static
checks, ARM64/x64 publishes, frontend TypeScript/build, Rust format/clippy,
portable checks, and release tests. Prefer deterministic resident/fixture
interfaces; outer input is for unavailable inner setup/recovery. Provider
acknowledgement is not an application-effect oracle.

## Result

Steps 1–4 complete for the signed x64 VM preview. The accepted product is
`0.4.3`, source `4468add959f8d591f8fcd1b1e8cf788e3a6af24f`, from
[workflow run 36906816804](https://github.com/kzahel/machine-control/actions/runs/36906816804).
Both ARM64 and x64 candidate jobs and the authentication job succeeded.
Independent controller verification accepted the unmodified provenance,
version, updater signatures, required payload names, and tamper rejection for
both architecture artifacts. ARM64 CI installation checks bytes on an x64
runner; it does not prove native ARM64 desktop execution.

The exact signed x64 installation passed full payload hashes, Authenticode,
timestamps, catalog, source/version, and compiled provider digest checks before
UI acceptance. The native installed probe then passed:

- Off-state refusal, approval/denial/timeout, scope/duration narrowing, pending
  prompt input pause, expiry, Stop, and stale generation rejection.
- Own-WebView semantics without a caller-supplied HWND, operator relaunch,
  Explorer tray/taskbar semantics, and guarded coordinate/overlay refusal.
- Bundled Cua observation and capture without fallback, independently observed
  counter effects, PNG byte hashes, and capture-superseded token refusal without
  replay or fixture effect.
- Native emergency shortcut, startup registration/removal, close-to-tray,
  tray Open/Settings/Updates/Stop/Quit, restart with access off, recovery after
  companion failure, and job cleanup after Quit or operator failure. User
  applications survive the operator's exit.

The final signed 0.4.2 to 0.4.3 updater test passed active-access exclusion,
ordinary TLS validation, automatic relaunch with access off, exact new source,
new generation, rejection of the old generation after rearming, and survival
of a user application. An isolated target-local HTTPS fixture served the exact
signed installer through the configured endpoint. No production feed changed.

The common local CLI passed doctor, exclusive claim/release, grant status,
off-state refusal, and active fixture effect/capture. An outside common caller
reached the same native grant and runtime generation, observed a fresh reference,
confirmed another counter effect, and verified transferred capture bytes. Both
routes rejected capture-superseded references without replay. The final bundled
runtime also passed the separately selected ordinary-user component conformance
probe: Cua routes, fixture effect/capture, protected-operation refusal, generation
fences, and malformed/disconnected IPC recovery.

Locking the final signed installation revoked its grant, changed its generation,
and refused observation. Native logoff followed by canonical stored-credential
sign-in recovered the appliance. After re-logon the app started with access off
in the newly observed session. The appliance has no optional existing-session
unlock broker; this proves lock revocation and re-logon, not in-place unlock.

Portable grant contracts, native x64 static/build/format and unlock contracts,
ARM64/x64 self-contained publishes, frontend TypeScript/build, Rust format and
clippy, workflow validation, Windows portable checks, and 43 release tests pass.

Acceptance found and corrected two defects: canonical installed inventory paths
must account for Windows 8.3 temporary aliases, and Cua's successful CLI exit
can carry a structured tool refusal. Inventory rejection tests and native
short-alias verification cover the first. The owned provider adapter now treats
structured errors as refused; independent native and signed installed probes
cover stale tokens without replay. These provider facts belong to the
[Cua dossier](../../research/providers/cua-driver.md).

The tray actor waits for finite actionable bounds rather than accepting a
transient Explorer ghost icon; native menus are read through their actual HMENU
and owner. Earlier incomplete candidates are superseded by the exact signed
source above. This actor correction changes no accepted product bytes.

All VM work used read-only doctor, exclusive target-use claims, and target-native
routes. An expired maximum-lifetime claim was released and replaced before
further target operations. Canonical stored credentials were verified; no
protected service was installed and no outer control was used. The signed test
installation and owned staging/processes were removed. Temporary update-feed
trust and hosts changes were reverted with original hosts bytes/hash verified;
fixture keys were deleted. The canonical credential still verifies. A clean
guest shutdown restored the original powered-off state, and the claim was
released afterward.

## Remaining gates

Native ARM64 desktop execution, physical hardware, browser integration,
in-place unlock recovery, and production Windows publication remain open.
The candidate workflow builds and signs reviewable installers; publishing a
Windows download or updater feed is a separate release step with required
versioned notes. Broader desktop scope is not established by this x64 VM run.

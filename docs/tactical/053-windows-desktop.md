# 053 — Windows desktop application

Status: active

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

Step 1 is implemented. Portable grant contracts and the native x64 source
probe passed: off-by-default refusal, no public approval operation, narrowing,
prompt pause, Stop, stale generation, independent fixture counter, verified
PNG/hash, and update gating. Native Windows static/build/format and unlock
contracts pass; ARM64/x64 self-contained publishes pass.

Step 2 builds and installs the shared Tauri app on x64. Installed unsigned UI
checks pass approval/denial/narrowing, prompt pause, independently confirmed
fixture action/capture, Stop/stale generation, restart with access off,
companion-failure recovery, job cleanup, and survival of a user-launched app.
Own-WebView invocation is refused. The native local CLI passes coordination
claim/release, doctor, grant state, guest-local discovery, and grant refusal.

Step 3 has main-only signed candidate CI. Its first run passed native/frontend
checks and publisher signing, then exposed packaging failures: stale package
version in Cargo.lock and a transient lock in an excluded setup-tool build.
Version updates now preserve the lock and the desktop build excludes component
tools. A second candidate run is active. Signed installed execution,
tray/shortcut/session/update acceptance, and component regressions remain in
progress.

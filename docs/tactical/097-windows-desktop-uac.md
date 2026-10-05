# 097 — Windows desktop UAC and elevated application control

Status: completed bounded source and x64 development-VM acceptance.
Owning topic: [Windows desktop](../../topics/windows-desktop.md).

## Objective and completion conditions

The operator requested UAC support in the desktop app now that native Windows
builds and the VirtualBox development VM work, with incremental commits and
VM validation. Reuse Windows native protected providers behind desktop grants
and live ownership. Prove actual UAC cancellation/approval and an independent
elevated fixture effect through the desktop instance.

## Boundaries

- The desktop and ordinary companion remain Medium integrity. An optional
  administrator-installed service and protected payload provide the privileged
  route; installing it does not enable access.
- Native Permissions owns installation through Windows elevation. A separate
  operator choice enables UAC/elevated control for the current app run. Existing
  observe/control grants, live owner, Pause, Stop, expiry and update exclusion
  apply before dispatch and again before native effects.
- Keep the appliance service independent. Never use its endpoint as a product
  fallback. Never expose SYSTEM process launch, arbitrary provider dispatch,
  credentials, lock/login, other sessions or remote desktop through this route.
- Secure-desktop effects are typed approve/cancel for an independently resolved
  stock consent prompt. Credential prompts and uncertain desktop state refuse.
  Keep UAC, secure desktop and credential policy unchanged.
- Use the claimed development VM for disruptive acceptance. Keep the controller
  desktop, protected base, private inventory and credentials untouched. Ordinary
  UI tests use target-native commands and fixtures without host focus/input.
- This slice does not publish a release or claim physical/ARM64 live acceptance.
  Same-user unrestricted shells are not contained by desktop grants.

## Ordered work

### 1 — define and test the protected desktop authority

Add the typed policy and refusal fixtures. Bind privileged requests to the
verified resident process, console/session, provider generation and live
request authority. Fail closed on lost authority, uncertain delivery and
unsupported operations. Do not retry mutations through another provider.

### 2 — install and expose the optional helper

Reuse the protected native provider/session launcher behind a separate service.
Protect its payload from ordinary writes and authenticate both pipe peers.
Add Permissions setup/removal and a default-off operator setting. Preserve
ordinary behavior without the helper and keep payload replacement explicit.

### 3 — validate real desktop UAC workflows in the Windows VM

Build natively and deploy exact candidate bytes under an exclusive claim. Prove
setup cancellation, off/unauthorized refusals, real secure-desktop capture,
typed cancellation/approval, elevated UI effects, stale references, Pause,
Stop, disconnect and helper removal. Inspect UAC policy independently.

### 4 — record acceptance and commit the finished slice

Run formatting, contract tests, ARM64/x64 publishes and frontend/native checks.
Update the desktop topic, platform research and product guide with honest
source/candidate acceptance and remaining signed-release gates. Release the
claim in cleanup and leave access off.

## Validation and final result

Completed on 2026-10-05. The actual Tauri Permissions UI cancels installation,
installs the administrator-owned helper with access off, and removes it after
Stop. Settings opts into the protected route for the current run; the ordinary
companion remains Medium. Setup uses Windows elevation, separate SCM service
identity, protected payload ACLs, kernel pipe/process identities, and a closed
operation list. Launch/activation remain Medium; credential and lock/login
operations are excluded. Worker callbacks recheck the exact owner's grant and
fences before native effects. Desktop epochs invalidate semantic references.

The checked-in [interactive actor](../../tests/windows/desktop-uac-live.py)
passes 21 checks on the claimed x64 development VM through the actual GUI and
desktop named-pipe owner channel:

- UAC/secure desktop enabled, ordinary Off refusal, setup cancellation,
  protected helper installation and default-off state;
- untrusted Medium caller, idle grant, observe-only owner and credential
  transport refusals;
- protected secure-desktop PNG/hash, generic secure input refusal, typed
  cancellation with no elevated marker, and stale semantic-reference refusal;
- typed approval followed by the fixture-owned process marker and elevated
  counter effect, with exact process identity;
- owner disconnection, Pause and Stop fences, native window closure, helper
  removal and unchanged UAC policy.

The separate appliance actor handles only install/remove prompts. Application
consent and elevated effects use `windows.desktop_uac/windows.native` routes;
there is no product fallback to the appliance. Controller actions are claimed
guest-native transport; no VM-window input, host focus or controller installation
is used. Final cleanup independently confirms no optional service/payload,
candidate process or acceptance task remains. Private evidence stays outside
Git. The inactive private staging directory was subsequently removed through
claimed guest PowerShell after an explicit cleanup request, with its exact path
and absence of links verified before deletion and absence verified afterward.
The first wrapped cleanup command had been rejected before execution by the
controller's command tool; no guest filesystem refusal was observed.
The VM returns to its original powered-off state and the validation and cleanup
claims are
released. The accepted runtime SHA-256 is
`2ff7d4bc648b9d554f2f21a01191b660bb63478d5b87cee08a20982167ea8b02`.
The final native shell SHA-256 is
`2bd5c109bf6d5f41e0b418e42e0871c05509554362ec69e1ea5fec68681aa53a`.

To repeat, stage the runtime/provider/fixtures, desktop executable, bundled
Python, `client/`, and `tests/windows/desktop-uac-live.py` in a private candidate
directory. Run the actor in the interactive Medium session with `--install`,
`--evidence` and `--mailbox` private paths. The claimed controller observes
`setup-cancel`, `setup-approve` and `remove-approve` mailbox phases, responds
only to their independent setup prompts, and writes the matching `.done`
files. Do not run another target operation concurrently with that controller.

Validation passes: runtime/desktop-contract formatting, desktop and unlock
contracts, self-contained x64/ARM64 publishes, TypeScript/Vite build, Rust
formatting/clippy and the native Tauri Windows build. Release/client Python
regressions pass with their recorded platform skips; the live actor compiles.

Friction and resulting fixes:

- Named-pipe impersonation must follow a read. Identification-level clients,
  actual server PIDs and a narrowly scoped SYSTEM ACL allow authenticated
  resident validation without changing the ordinary user pipe.
- STA initialization can create a window before desktop binding. Protected
  requests use UIA's MTA route and bind before authority callbacks; ordinary
  requests retain STA. Win32 failures report their native code.
- Stock consent owns a background Pane as well as its dialog. Discovery requires
  one visible enabled Window of the unique stock consent process, while keeping
  edit/password-field and unique response refusals.
- Cold payload copies, companion restart and elevated window creation need
  bounded state waits. The test mailbox uses atomic replacement. Earlier test
  coordination errors were corrected before the passing complete run.
- The independent appliance relay needed typed revocation before setup prompt
  handling. This is testbed friction, not an adopted product fallback.
- A cold ordinary `app.launch` held the existing grant gate long enough to lose
  owner heartbeat. This run starts its independent fixture before acquiring
  product ownership; repairing that separate launch/watchdog concern is deferred.

No public release is published. Exact signed installed/update/uninstall-helper
qualification, ARM64 live and physical execution, localized consent, helper
fault/restart campaigns and broader elevated application/input coverage remain
open. Credential prompts and lock/login remain explicitly unsupported.

# 097 — Windows desktop UAC and elevated application control

Status: active.
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

Pending implementation and VM acceptance.

# Tactical 051: Tauri macOS desktop and signed packaging

Status: active.
Topics: `host-control`, `native-distribution`, `macos-resident-control`.

## Objective and completion conditions

Package a new version of the Mac application with a shared Tauri UX, adopt
Desktop Release Kit's signed CI patterns, and validate actual signed bundles
locally and in a claimed Tart VM before public distribution. Preserve the
native resident contract and its permission, policy, grant, and self-control
boundaries. Windows and Linux UI architecture must remain possible without
rewriting their providers.

Completion requires a self-contained Mac bundle, actual signed/notarized CI
artifacts, strict local verification, and native guest evidence for setup,
approval/denial/narrowing, Stop, protected-operation refusal, ordinary desktop
effects, restart, and an upgrade of the installed signed application.

## Boundaries

No public release, update-server deployment, host permission changes, protected
helper installation, Windows/Linux product acceptance, or appliance promotion.
The shared desktop shell initially embeds the existing Swift resident as a
framework in its native process. The public agent socket cannot approve a
grant. Approval stays target-wide for this preview; connection binding is a
separate follow-up. Existing appliance source deployment remains available.

## Ordered work

### 1 — build the shared desktop UX

Tauri operator window and native tray, setup, approval, activity, settings,
bundled browser extension, and native Swift bridge with closed operator methods.

### 2 — preserve resident enforcement and lifecycle

Same process and code identity, grant checks, self-interface refusal, native
Stop hotkey, pending-decision validation, exclusive endpoint ownership, and
compatible CLI/browser native-messaging modes.

### 3 — build and authenticate Mac packages

Unsigned source checks and protected manual CI builds for both Mac
architectures; nested signing, hardened runtime, notarization, stapling,
updater signature, exact source identity, and archive validation. Publisher
configuration and keys stay outside public source.

### 4 — prove the actual application in Tart

Read-only doctor, exclusive claim, credentials lookup, resident-native
permission bootstrap, visible UI and grant checks, independent fixture effects,
signed upgrade, cleanup, initial power-state restoration, and prompt claim
release. Keep captures and concrete target values private.

## Validation and result

**Current:** the shared app builds locally; all 44 Swift tests, strict Rust
Clippy, and portable repository checks pass. A local Developer ID bundle and
DMG have been notarized and stapled. Fresh archive extraction and updater
signature/tampering checks pass. Local packages are identified as working-tree
builds rather than exact clean-source releases.

**Current:** the locally signed app rendered correctly in a claimed Tart
guest. Visible denial and scope narrowing, self-interface and protected-route
refusals, pausing existing control during a new prompt, Stop, and explicit
restart passed. An Increment action changed the independent fixture oracle.
Accessibility and Screen Recording were ready before and after restart.
The reusable [guest test](../../tests/macos/tauri-desktop.py) has no approval
bypass and uses the separate appliance resident's native AX input.

CI artifact acceptance and signed upgrade remain pending. The configured
public update feed is reserved and has not been deployed. No public release
has been created.

# Windows desktop packages

The standalone product uses the shared Tauri UI and a bundled self-contained
.NET companion. It installs per user and starts with access off. It does not
install or arm the protected service. The workstation component workflow
remains a separate distribution family.

## Signed candidates

Commit the intended source on main and add meaningful notes for its candidate
version to [the desktop changelog](../desktop/CHANGELOG.md), then dispatch:

```bash
gh workflow run windows-desktop.yml --ref main -f version=0.4.3
```

The unsigned check job precedes protected main-only ARM64/x64 signing. Private
Azure publisher/account/profile values stay in protected CI configuration;
updater signing uses the desktop product's existing key.

The pipeline verifies the pinned provider, signs it, and compiles its final
digest into the resident. Companion staging retains audited dependency notices
and omits component/protected setup tools. A signed catalog covers every runtime
resource. Tauri's custom signing command signs the app, generated uninstaller,
and NSIS installer. The updater signature covers final bytes and version.

[Artifact Signing CLI](https://github.com/Levminer/artifact-signing-cli), MIT,
is pinned to `0.11.0`; it succeeds the signing tool used by sibling desktop
apps. [Tauri signing configuration](https://v2.tauri.app/reference/config/#customsigncommandconfig)
owns its custom command integration. No signing identity is checked in.

CI installs each architecture into a private scratch directory, checks publisher
and timestamps, installed source/version, provider digest, runtime catalog, and
payload inventory, then removes it. A separate job authenticates both updater
signatures and rejects changed bytes.

## Independent verification and acceptance

Download exact workflow artifacts and verify the known source, version, workflow
attempt, and target with `minisign` installed:

```bash
python3 desktop/scripts/windows-package.py verify CANDIDATE_DIRECTORY \
  --revision SOURCE_SHA --version 0.4.3 --run RUN_ID.ATTEMPT \
  --target x86_64-pc-windows-msvc --test-tampering
```

Installed Windows verification also checks Authenticode, timestamps, the entire
runtime catalog, and payload bytes. Signing/build checks are not desktop
acceptance. [Tactical 053](../docs/tactical/053-windows-desktop.md) owns native
approval/effect/Stop/session/tray/lifecycle/update acceptance through claimed VMs.

Public signed x64 preview `0.4.8` passes installed UI, browser, updater,
startup, and uninstall acceptance; [tactical 055](../docs/tactical/055-unified-desktop-publication.md)
records its source and workflow. ARM64 package verification does not establish
native ARM64 execution.

Use the [unified release script](desktop.md) to publish Mac and Windows together
with one version and required changelog. Direct Windows workflow dispatches
remain candidates only. Public downloads include x64 and ARM64 with execution
gaps recorded in the [acceptance matrix](../docs/desktop-acceptance.md).

## Lifecycle

Approval uses inherited stdin/stdout; agent calls use the same-user pipe with
instance `desktop`. Tauri's kill-on-close job owns the resident and provider
children. User applications explicitly leave that job so Quit preserves them.

Ctrl+Alt+Shift+Period stops access on a separate native message thread. Startup
is an explicit per-user preference. Updates recheck native idle state before
replacement. The Windows
[updater exit hook](https://v2.tauri.app/plugin/updater/#windows-before-exit-hook)
cleans up the companion and Tauri before installation.

## Common CLI

On Windows, `python bin/machine-control --target host target doctor` selects
the installed desktop product in the current interactive user session.
Acquire a common target-use claim before `grant request|status|revoke` or
`desktop` operations. Claims coordinate callers; the native operator grant
decides authority. The adapter never starts or approves the resident.

An outside VM controller explicitly selects `WINVM_RESIDENT_PROFILE=desktop`
and the interactive `WINVM_USER_SESSION_ID` in its private target environment.
This uses the same instance, grant requests, generations, and artifact IDs.
The appliance remains the default; `user` continues selecting a separately
installed workstation component. There is no fallback among profiles.

Both adapters default to the per-user `Machine Control` installation.
Controller-local `MACHINE_CONTROL_DESKTOP_INSTALL_DIR` (local) or
`WINVM_DESKTOP_INSTALL_DIR` (outside) can locate a custom acceptance install.
Locators are private configuration; requests cannot override them. Metadata
must identify the ordinary desktop profile and instance before any call.

## Installed acceptance probes

Run `tests/windows/desktop-installed.ps1` in the interactive user session with
the exact installer directory, independent fixture, expected source/publisher,
and the authenticated candidate's `-Payload` inventory. It verifies every
installed file before UI, grant, tray, shortcut, expiry, and failure checks.
Signed runs require the bundled provider for fixture observation and capture.
`-AllowUnsigned` is only for explicitly labelled developer evidence.

`tests/windows/desktop-update.ps1` uses the installed native UI against a
controller-owned HTTPS fixture feed. It checks active-access exclusion, automatic
relaunch, revoked grants, new generation, and preservation of a user app.
Restore temporary fixture trust and DNS/hosts configuration after the run.

`tests/windows/desktop-cli.ps1` proves local doctor, claim/release, off-state
refusal, and, with an independently armed grant and `-Fixture`, packaged Cua
counter effects, artifact hashes, and capture-superseded reference refusal.
An outside parity probe must take a fresh observation after the local capture;
it cannot reuse that capture-superseded reference.

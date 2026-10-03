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

### Agent discovery in the next desktop package

The Windows desktop executable now forwards CLI commands to its bundled Python
runtime before starting the GUI. This is checked-in implementation; public
0.5.3 retains its original nested-command entry until updated.

```powershell
machine-control --help
machine-control agent instructions
machine-control agent identity --paths
```

Explicit help and agent discovery are offline. Bare terminal/captured launch,
or `--start`, starts the app if needed, reports bounded readiness and returns
instruction pointers. Use `--gui` to open the operator window. Ordinary commands
produce their existing output without a banner and do not start a resident.
Starting the app leaves native access approval and target-use claims unchanged.
An interactive Windows user session is required to start the desktop product;
offline discovery also works from noninteractive shells.
The EXE retains the Windows GUI subsystem for graphical launch. In PowerShell
scripts, pipe output (for example, `machine-control agent identity | Out-String`)
or use `Start-Process -Wait` to wait reliably and inspect completion. Interactive
shells can display their next prompt before an unpiped GUI command finishes.

The installer offers **Add to user PATH**, with the previous preference retained
for repair and passive updates. Silent callers can set `/ADDTOPATH=1` or
`/ADDTOPATH=0`; the first-install default is on. The installer appends only its
directory, preserves registry value types, and removes only an entry it owns.
Existing terminals/agent hosts may need restarting to inherit the new PATH;
absolute-path invocation works immediately. The root `README.txt` and runtime
pointer explain this discovery path. No global agent instructions are edited.

`agent identity` remains the exact static receipt for existing consumers.
`agent identity --paths` adds resolved launcher, interpreter, CLI and bundled
resident locations. These are client diagnostics, not authenticated live
resident identity. Bare launch verifies the answering resident image before
claiming this installation is running; a different installation is not replaced.

Tests: `tests/windows/discovery.py` exercises offline EXE and shell/pipe behavior;
`discovery-console.ps1` checks a real console buffer; `discovery-session.ps1`
checks startup and a claimed fixture effect; `discovery-installer.py` exercises
the installer lifecycle with finally-style registry restoration. Run session
and installer tests only in an exclusively claimed dedicated appliance. Exact
acceptance and remaining coverage live in
[Tactical 068](../docs/tactical/068-windows-agent-discovery.md).

### Target selection and access

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

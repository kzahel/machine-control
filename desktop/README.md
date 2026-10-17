# Machine Control desktop

The desktop app provides access controls, permissions, activity, and settings
on macOS, Windows, and Ubuntu GNOME Wayland. Public packages cover Apple
silicon/Intel on Mac and x64/ARM64 on Windows and Linux, and include the control
CLI and its Python runtime. [Download the app](https://machinecontrol.dev/downloads/).

The shared Tauri application embeds the Mac Swift resident. Windows bundles
the .NET resident as a supervised companion with native grants; installed GUI
acceptance is recorded on x64 and ARM64 VMs. Linux uses an ordinary-user
Python/GI companion with AT-SPI semantics and visible GNOME portal consent for
capture/input, independently of the appliance's root input broker. Installed
x64 Debian/AppImage acceptance and focused ARM64 Debian semantic/access checks
pass; broader ARM64 portal/browser/lifecycle coverage remains open.

See the [acceptance matrix](../docs/desktop-acceptance.md) for tested behavior
by package, architecture, and VM/physical environment.
The [Windows pointer guide](WINDOWS-POINTER-INPUT.md) describes native move,
drag and scroll requests, units and interruption behavior.

The operator uses a compact settings window with Access, Permissions, Activity,
and Settings tabs. Labels and status rows replace banners and explanatory
subtitles; same-user grant reach stays visible beside access controls.

## Development and installation

Requires Node 24+, pnpm, Rust, and Xcode on macOS.

```bash
cd desktop
pnpm install --frozen-lockfile
pnpm tauri build --bundles app --no-sign
```

Local development builds are unsigned. Do not use them to establish production
permission retention. The assembled bundle includes its native framework,
session probe, and unpacked Chrome extension; no checkout path is embedded.
The main executable retains `macui request SOCKET JSON`, `credential`,
`screen-capture-preflight`, and Chrome native-messaging modes before it starts
Tauri. This preserves the common CLI and browser code-identity check.
Optional Cua routes still require an independently installed provider; they
are not bundled. Capability reporting exposes unavailable routes.

Use the existing per-user installer for a development/test deployment:

```bash
# From the repository root:
platforms/macos/resident/scripts/install-user.sh --app APP_PATH
```

That installer verifies integrity, but it is not a release authenticator. For
an external package, verify the product updater signature, exact publisher,
notarization, and final bytes before installation. The manual desktop workflow
produces CI candidates with an empty release tag. Tagged publication uses
[the desktop release script](../release/desktop.md).

## Approval and control boundaries

On macOS, Windows and GNOME Wayland Linux, Settings has an unreleased,
default-off **Allow approved browser
access while locked** option. Enable it and approve browser access before
locking. Browser tabs and separately approved browser scripts/DevTools can
continue through the extension while the computer stays locked, without an unlock
helper. Mixed approvals retain their original expiry, while desktop observation
and input remain unavailable until unlock unless covered desktop control is
separately enabled. Pause, Stop and expiry still apply; turning the option off
while locked ends retained access. New or broader approval requires unlocking.
This covers an awake existing console, not system sleep or browser/OS
authentication dialogs. See [macOS validation](../docs/tactical/130-macos-browser-while-locked.md) and
[Windows/Linux validation and limits](../docs/tactical/131-windows-linux-browser-while-locked.md).

Linux targets Ubuntu 24.04 GNOME 46 Wayland first. Install the Debian package to
resolve its Python/GI, portal, PipeWire/GStreamer, and Wayland clipboard
dependencies. AppImage uses those same system dependencies; it is not a bundled
Python desktop stack. GNOME must expose an AppIndicator tray for the tray UI.
The Stop shortcut is an explicit GNOME settings preference. Other desktops,
lock/login control, arbitrary top-level window activation, and multi-monitor
input are not accepted by this profile. See [Linux desktop](../topics/linux-desktop.md).

Build Linux on Ubuntu 24.04 with the dependencies in `linux-desktop.yml`, then:

```bash
python3 desktop/scripts/prepare-linux.py --revision "$(git rev-parse HEAD)"
cd desktop
pnpm tauri build --config src-tauri/tauri.linux.conf.json --bundles deb,appimage --no-sign
```

Local packages establish development behavior, not production authentication.
See the [Linux guide](LINUX.md) for dependencies, sharing, updates, and removal.

On a Linux workstation, `bin/machine-control --target host` reaches the app's
ordinary-user socket. For a claimed Linux appliance, select the product explicitly
in the private target's environment with `MACHINE_CONTROL_LINUX_INSTANCE=desktop`.
The common remote/local desktop and artifact commands then reach that same
resident. The default `appliance` instance retains its privileged test profile;
the product never falls back to it. Claims coordinate target use; native grants
authorize operations.

Windows uses a separate `desktop` instance and inherited private operator
channel. Its public pipe enforces grants and cannot approve them. Ordinary
control does not cross UAC, elevated apps, lock/login, or other user sessions.
The 0.5.7 [optional UAC helper](WINDOWS-UAC.md) adds administrator-approved,
default-off UAC consent and elevated application control behind native grants
and a live owner session. The 0.5.7 [bounded locked-use profile](WINDOWS-LOCKED-USE.md)
adds separately approved, owner-bound existing-session password unlock and
independent relock behind an opaque single-display cover. Tasks that start
unlocked finish without requesting lock. Cold login and other users remain
unavailable.
Ctrl+Alt+Shift+Period is the native emergency Stop shortcut. Startup is an
explicit preference. See [Windows packages](../release/windows-desktop.md)
and [Tactical 053](../docs/tactical/053-windows-desktop.md) for current evidence.

The resident still loads the trusted deployment policy and checks every
operation. The operator WebView calls only closed in-process native methods;
the agent socket has no approval method. Pending decisions are matched to
request ID and may only narrow scope and lifetime. Native self-interface
screening, input pausing during prompts, expiry, lock revocation, and a native
Control–Option–Command–Period Stop shortcut remain in force.

Mac Settings additionally offers **Allow Machine Control while screen is
locked**, initially off. The experimental macOS 14+ profile uses native
helper approval in Permissions, a bounded task connection, covered displays, native
capture underneath, physical takeover, and failure relock. Keep the Mac awake
with its lid open. Turning it off immediately revokes temporary use; no login
password is stored. See the [Mac locked-use guide](../platforms/macos/docs/locked-use.md)
for setup, agent lifecycle, removal, and the precise VM/physical acceptance scope.

Preview grants remain target-wide for same-user callers. This app is not a
sandbox for an agent with unrestricted same-user shell access. Closing the
operator window keeps the tray and resident running; Quit ends the process.
Permission changes may require Restart. Browser integration is optional and
currently uses the bundled unpacked extension, with explicit user setup.
The 0.5.7 [Windows browser upload](WINDOWS-BROWSER-UPLOAD.md) operation
attaches validated target-local files through that extension without the OS
picker, under browser grants and live ownership.
The 0.5.7 [Windows streaming CDP](WINDOWS-STREAMING-CDP.md) bridge adds
per-tab and browser-level WebSockets, debugger events and flattened target
sessions under a retained DevTools owner. Real Playwright/Puppeteer tasks use
the existing default profile; unsupported browser-wide operations refuse.

Mac 0.4.9 offers **Until I turn it off** for manually enabled access.
It removes the timer for the selected scopes; Stop, screen lock/session loss,
Quit, and Restart still end access. Agent-requested approvals remain timed.
The exact signed ARM64 package passes targeted Tart acceptance; see
[Tactical 057](../docs/tactical/057-macos-until-stopped-release.md).

## Mac presentation and recovery

The Mac candidate uses one resident and one package for three launch modes:

- **Personal desktop** opens Settings at launch and keeps the menu bar.
- **Minimal** starts with the menu bar; Settings is created only when opened.
- **Dedicated appliance** starts without Settings and hides its idle menu bar.
  Required approval, control notices, active-access status and the native Stop
  shortcut remain available. This mode does not create unattended authority.

Closing Mac Settings destroys its WebView while the resident, browser channels,
approvals and safety controls continue. Reopen through **Settings…** in the
menu bar, open the same app again, or launch the app executable with
`--settings`. Explicit Settings recovery works in every mode and does not
change the saved preference. Selecting a mode in Settings preserves active
access and permissions; changes wait until a pending approval is finished.

The packaged local CLI provides supported provisioning and recovery:

```bash
machine-control presentation status
machine-control presentation set minimal
machine-control presentation set appliance
machine-control presentation reset
```

The native executable also accepts `presentation status|set PROFILE|reset`.
Use `--socket SOCKET` with either command for an isolated installation.
Residents on isolated sockets do not automatically maintain the canonical
protected helper; explicit operator setup remains available. The
versioned, owner-only `presentation.json` lives beside that resident socket;
updates use an atomic replacement. Missing or invalid configuration falls back
to personal with a diagnostic. Reset writes personal, so recovery does not
require deleting files. Unsafe ownership, directories and symlinks refuse writes.
A running resident reads saved changes without restarting, deferring during an
approval. A temporary `--presentation personal|minimal|appliance` launch override
lasts until restart or an explicit Settings choice and does not write the file.
Launch flags follow `serve SOCKET` for isolated candidates. Mac second-launch
forwarding is bound to the resolved resident endpoint, so candidates on
separate sockets do not attach to the installed app. The private same-user
forwarding channel supports only Settings recovery and liveness.

Presentation is separate from the root-owned deployment policy displayed in
Settings. Selecting appliance presentation on a workstation still requires
native approval. Returning to personal presentation on a provisioned appliance
preserves that policy; remove unattended authorization explicitly when needed.
These local controls assume the operator's OS identity and do not contain an
agent with a same-user shell. Windows and Linux have separate native candidate
qualification; Mac acceptance does not cover either OS.

## Signed releases and candidates

[Mac desktop `0.3.3`](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3)
is the first public preview for Apple silicon and Intel. Its exact signed source
passed ARM64 Tart approval, fixture effects, Stop, tray Quit, and a `0.3.2` to
`0.3.3` installed upgrade with permissions retained and grants revoked.
Candidate `0.3.2` supplied the earlier signing and native acceptance baseline.
[Tactical 051](../docs/tactical/051-tauri-macos-desktop.md) records the exact run
and omissions. This is historical release evidence. Current environment
coverage is recorded
in the [acceptance matrix](../docs/desktop-acceptance.md).

`.github/workflows/macos-desktop.yml` runs unsigned source checks on changes.
A manual main-only dispatch builds Apple silicon and Intel candidates in the
protected `release` environment. Signing configuration uses the existing
publisher variables and certificate/notarization secrets. Machine Control
has its own Tauri updater key and password; private values stay in the
maintainer's owner-only store and CI secrets.

The finalizer signs the native framework, session probe, and application,
notarizes/staples the app and DMG, and signs the final update archive with the
product updater key and version. `build.json` binds hashes and source/workflow
identity. Verification also extracts fresh bytes and rejects a modified
archive before checking code signatures, Gatekeeper, and the stapled ticket.

```bash
python3 desktop/scripts/verify-package.py ARTIFACT_DIRECTORY \
  --revision EXPECTED_SOURCE_SHA --team-id EXPECTED_TEAM_ID --test-tampering
```

The tagged release script creates an annotated `desktop-vX.Y.Z` tag and
dispatches the main-only unified workflow. Starting with 0.5.0, all six
Mac/Windows/Linux targets must pass verification before CI publishes the
complete verified draft. An accepted unified candidate can be promoted without
rebuilding its signed bytes. The website resolves the
latest desktop release separately from Windows component releases. See the
[release process](../release/desktop.md) and [changelog](CHANGELOG.md).

Current public downloads are available from
[the download page](https://machinecontrol.dev/downloads/), with Mac, Windows,
and Linux packages for both architectures. The [changelog](CHANGELOG.md) owns
versioned changes. Six-target 0.6.4 package and delivery verification is
recorded in
[Tactical 121](../docs/tactical/121-desktop-0.6.4-release.md); Linux
installed GUI acceptance retains its exact 0.5.0 evidence in
[Tactical 059](../docs/tactical/059-public-linux-desktop.md). Manual checks are
available in Settings and the tray. ARM64 Tart passes
public 0.3.5 to 0.4.8 replacement with automatic relaunch and retained permissions;
Windows x64 passes 0.4.7 to public 0.4.8 with Chrome open. Mac 0.3.3/0.3.4 clients
may need to reopen after their first update. Windows ARM64 packages are signed
and verified, with native installed CLI
smoke and focused signed 0.5.4 GUI acceptance; broader browser/lifecycle
coverage remains separate in the acceptance matrix. Exact evidence is in
[tactical 055](../docs/tactical/055-unified-desktop-publication.md), with earlier
Mac update history in [052](../docs/tactical/052-macos-production-updates.md).
No automatic update installation is enabled. Native code rechecks that no
access or approval is active immediately before bundle replacement and restarts
with access off.
Public 0.5.3 schedules silent discovery five seconds after startup and every
24 hours in the native Tauri process, including with the settings window closed.
Concurrent checks coalesce; manual callers joining silent checks get visible
feedback. Automatic errors are logged quietly and an available update survives
later empty responses or failures. Settings and the tray show the available
version without opening or focusing the window.

`bin/machine-control --target TARGET update check` queues metadata discovery;
`update status` reads its shared result. Responses contain `data.queued` and
`data.update`; acceptance means queued/coalesced discovery, not a completed
network check or installation. Read status until `data.queued` and
`data.update.checking` are false to observe completion. Existing target-use
claims apply. Only the desktop product supports these operations; components
and older packages may refuse them. The public transport exposes no update
installation or endpoint setting. Linux Debian retains package-manager
replacement. [Tactical 060](../docs/tactical/060-native-update-discovery.md)
owns validation; released clients retain their shipped behavior until updated.

Appliances with standing access use their administrator-managed deployment.
Adopt Desktop Release Kit's update contract when
publishing; the application owns its lifecycle and native acceptance rather
than treating a canary pass as Machine Control acceptance.

## Windows presentation and recovery

The Windows development candidate reuses the .NET resident and its existing
authorization. Personal opens Settings; Minimal starts with the tray;
Appliance hides its idle tray and starts quietly. Required native approvals,
activation notices and Stop remain available in all three modes. Appliance
presentation does not provision standing access or a protected provider.

Closing Settings destroys its WebView and leaves the runtime and owner
channels running. Open the same executable with `--settings` to recover
Settings in that runtime. `--gui` remains a compatibility spelling. A temporary
`--presentation personal|minimal|appliance` launch override expires on Restart;
Restart reloads the saved choice and revokes volatile control.

In an interactive Windows terminal, the packaged executable supports:

```powershell
machine-control presentation status
machine-control presentation set minimal
machine-control presentation reset
machine-control --settings
```

The local operator CLI uses a separate same-user pipe when the resident is
running, and an atomic preference file when it is absent. A busy endpoint
refuses an offline edit; uncertain delivery is never replayed. Changes defer
while approval is pending. Invalid preferences default to Personal and expose
a diagnostic. Settings also offers the presentation selector. These controls
do not change grants, permissions or administrator deployment policy.

`Ctrl+Alt+Shift+.` stops access independently of Settings and provider work.
Stop availability is reported explicitly; Quit terminates the operator's owned
resident job if its private transport is broken. Tests may use a separate
`--instance NAME`; browser registration remains the standard desktop route.
[Windows acceptance](../docs/tactical/110-windows-runtime-presentation.md)
distinguishes local development signing, native execution and remaining
publisher/architecture qualification.

## Linux presentation and recovery

The ordinary-user Linux candidate implements the same three profiles,
disposable Settings, restart-expiring overrides and local status/set/reset.
Independent GTK approval and safety processes keep Pause/Stop available with
Settings absent. Presentation preserves native portal consent and never grants
appliance privileges. The [Linux guide](LINUX.md#development-presentation-and-recovery)
owns command examples; [Linux acceptance](../docs/tactical/111-linux-runtime-presentation.md)
owns candidate authentication, effects, fault/restart evidence and limits.

## Native administrator commands on Mac

The Mac bundle includes the signed `mc-sudo` and `mc-sudo-askpass` executables
in `Contents/Resources`. [Native sudo](../platforms/macos/sudo/README.md) owns
their invocation, local password dialog, per-command authority and tests.
They are independent of desktop control arming and install no root service.

## Installed Python control CLI

Public 0.5.3 bundles the existing Python client and a pinned CPython runtime
in `mc-cli`. The terminal entry lives under `mc-cli/commands`, separate from
the Windows/Linux GUI executable. `agent identity` and `agent instructions`
provide offline discovery and workflow guidance. Released older packages do
not gain this interface until updated. Packaging, trust and acceptance limits
are owned by [Installed agent CLI](../topics/installed-agent-cli.md).

Local assembled-app signing can exercise the production nested-code and
Python inventory order with `python3 desktop/scripts/sign-macos-payload.py APP
--identity SIGNING_IDENTITY`. This signs and verifies the bundle; notarization,
stapling, updater signing and publication remain in `sign-macos.sh`.

### Replace an installed Mac app with a local build

Swap whole bundles by rename; never copy files into an installed bundle.
macOS App Management protection refuses writes inside an app bundle from a
process without that permission, such as an agent shell. A partly copied
bundle leaves the LaunchAgent unable to start the resident, and access stays
off until the bundle is repaired.

1. Build, then sign a complete copy outside the Applications folders with the
   same Developer ID as the installed app. Confirm the new `macui` satisfies
   the installed designated requirement
   (`codesign -v -R="$(codesign -dr - OLD/Contents/MacOS/macui | sed -n 's/^designated => //p')" NEW/Contents/MacOS/macui`);
   otherwise macOS privacy permissions do not carry over. Unsigned or ad hoc
   builds lose them.
2. Stage it on the same volume as the installed app so both moves are atomic
   renames, for example under `/tmp`.
3. `mv` the installed bundle to a backup name ending in `.app.bak` (so Launch
   Services does not register a second copy), `mv` the staged bundle into
   place, and run `launchctl kickstart -k gui/$(id -u)/org.machine-control.resident`.
   If the resident is not running a few seconds later, rename the backup
   back and kick the job again.
4. Check `target doctor`. Same-session until-stopped consent restores without
   a click once permissions pass; a reboot or logout does not restore it.

The root unlock helper pins the installed resident's code hash, so a new
build reports `callerEligibility: denied` until locked-use maintenance
re-registers it, exactly as after a production update.

Desktop Activity now reads durable history. See [history and diagnostics](../docs/desktop-audit.md) for privacy, retention, storage failure, and local export.

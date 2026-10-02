# Machine Control desktop

A shared Tauri operator application with the existing Mac resident embedded
as a Swift framework in its native process. Windows bundles the existing .NET
resident as a supervised companion with native grants. The signed Windows x64
preview passes installed VM acceptance; ARM64 native desktop execution remains
open. Linux uses a supervised Python/GI companion with native AT-SPI semantics
and visible GNOME Wayland portal consent for screen capture and input. It never
uses the dedicated appliance's root input broker. Source-native control and
browser tests pass; exact installed package acceptance is in progress.

See the [acceptance matrix](../docs/desktop-acceptance.md) for tested behavior
by package, architecture, and VM/physical environment.

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
Ctrl+Alt+Shift+Period is the native emergency Stop shortcut. Startup is an
explicit preference. See [Windows packages](../release/windows-desktop.md)
and [Tactical 053](../docs/tactical/053-windows-desktop.md) for current evidence.

The resident still loads the trusted deployment policy and checks every
operation. The operator WebView calls only closed in-process native methods;
the agent socket has no approval method. Pending decisions are matched to
request ID and may only narrow scope and lifetime. Native self-interface
screening, input pausing during prompts, expiry, lock revocation, and a native
Control–Option–Command–Period Stop shortcut remain in force.

Preview grants remain target-wide for same-user callers. This app is not a
sandbox for an agent with unrestricted same-user shell access. Closing the
operator window keeps the tray and resident running; Quit ends the process.
Permission changes may require Restart. Browser integration is optional and
currently uses the bundled unpacked extension, with explicit user setup.

Mac 0.4.9 offers **Until I turn it off** for manually enabled access.
It removes the timer for the selected scopes; Stop, screen lock/session loss,
Quit, and Restart still end access. Agent-requested approvals remain timed.
The exact signed ARM64 package passes targeted Tart acceptance; see
[Tactical 057](../docs/tactical/057-macos-until-stopped-release.md).

## Signed releases and candidates

[Mac desktop `0.3.3`](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.3.3)
is the first public preview for Apple silicon and Intel. Its exact signed source
passed ARM64 Tart approval, fixture effects, Stop, tray Quit, and a `0.3.2` to
`0.3.3` installed upgrade with permissions retained and grants revoked.
Candidate `0.3.2` supplied the earlier signing and native acceptance baseline.
[Tactical 051](../docs/tactical/051-tauri-macos-desktop.md) records the exact run
and omissions. The application remains a developer preview; physical-host and
Intel runtime acceptance are still open.

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

The latest public release is [0.4.9](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.4.9),
with Mac and Windows packages and production updates through the existing shared
service. Manual checks are available in Settings and the tray. ARM64 Tart passes
public 0.3.5 to 0.4.8 replacement with automatic relaunch and retained permissions;
Windows x64 passes 0.4.7 to public 0.4.8 with Chrome open. Mac 0.3.3/0.3.4 clients
may need to reopen after their first update. Windows ARM64 packages are signed
and verified; native ARM64 execution remains untested. Exact evidence is in
[tactical 055](../docs/tactical/055-unified-desktop-publication.md), with earlier
Mac update history in [052](../docs/tactical/052-macos-production-updates.md).
No automatic update installation is enabled. Native code rechecks that no
access or approval is active immediately before bundle replacement and restarts
with access off.
Appliances with standing access use their administrator-managed deployment.
Adopt Desktop Release Kit's update contract when
publishing; the application owns its lifecycle and native acceptance rather
than treating a canary pass as Machine Control acceptance.

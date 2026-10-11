# Linux desktop preview

The first supported profile is Ubuntu 24.04 with GNOME 46 on Wayland. x64 and
ARM64 packages are built natively. Installed x64 Debian/AppImage execution
and focused ARM64 Debian access,
semantic-effect, and Stop checks pass on GNOME Wayland VMs. Broader ARM64
portal/browser/lifecycle coverage, other desktops, and physical hardware remain
open.
See the [acceptance matrix](../docs/desktop-acceptance.md).

## Install

For Debian packages, download the package for your architecture and install it
with APT so its dependencies are installed:

```bash
sudo apt install ./MachineControl_VERSION_ARCH.deb
machine-control
```

For AppImage, install the ordinary-user runtime dependencies first:

```bash
sudo apt install libfuse2 libwebkit2gtk-4.1-0 libayatana-appindicator3-1 \
  python3 python3-gi gir1.2-gtk-3.0 gir1.2-atspi-2.0 \
  gir1.2-gst-plugins-base-1.0 gstreamer1.0-pipewire \
  gstreamer1.0-plugins-good wl-clipboard \
  xdg-desktop-portal xdg-desktop-portal-gnome
chmod +x MachineControl_VERSION_ARCH.AppImage
./MachineControl_VERSION_ARCH.AppImage
```

Keep the AppImage in a stable, user-writable location. Startup and the optional
Stop shortcut refer to that location. GNOME must expose AppIndicator/StatusNotifier
icons for the tray menu; Ubuntu's default desktop provides this integration.
The app does not install a Shell extension or a privileged input service.

## Installed agent CLI

From desktop 0.5.3, Debian installs provide the bundled Python control client at
`/usr/share/machine-control/mc-cli/commands/machine-control`. AppImage contains
the same path beneath its mounted or extracted root. This is separate from the
`machine-control` GUI executable. It supplies its own Python interpreter;
the native GTK/AT-SPI resident still uses the system dependencies above.

```bash
/usr/share/machine-control/mc-cli/commands/machine-control agent identity
/usr/share/machine-control/mc-cli/commands/machine-control agent instructions
```

## Access and sharing

Access starts Off. Enable selected scopes for a bounded duration, or approve a
request in the native dialog. Stop ends access immediately. Restart starts Off.
Screen capture and pointer/keyboard input require **Permissions → Share…** and
visible GNOME portal consent. Sharing alone does not grant agent access. Closing
sharing, leaving the unlocked session, or losing the operator ends access.

The app protects its operator and approval windows. Input refuses an ambiguous
foreground identity. Other users, lock/login, elevated/protected control, multiple
shared screens, file upload, and raw browser WebSockets are outside this preview.

Browser integration is optional. Use **Permissions → Set up**, then load the
copied extension in Chrome as an unpacked extension. Browser access and browser
scripts have separate scopes. See [browser control](../topics/browser-control.md).

## Development presentation and recovery

The development candidate supports Personal, Minimal and Appliance in the
existing app. Personal opens Settings; Minimal starts with the tray; Appliance
hides its idle tray. Pending or active access retains the tray and independent
native approval and safety UI in every profile. Safety offers Pause, Resume,
Stop and Settings; closing it stops access. Missing safety presentation refuses
access. Appliance presentation does not provision unattended authority or
select the root appliance input provider.

Closing Settings destroys the WebView while the resident continues. Open the
same executable with `--settings` to recover it. A launch override
`--presentation personal|minimal|appliance` lasts until Restart or an explicit
saved choice. Restart reloads the saved profile with access Off.

The GUI executable supports this local recovery CLI without opening a WebView:

```bash
machine-control presentation status
machine-control presentation set minimal
machine-control presentation reset
machine-control --settings
```

The bundled Python control client also routes local `presentation` commands.
These are operator commands; the public desktop action endpoint cannot mutate
presentation or arm access. A separate bounded same-user socket serves live
recovery. When the resident is absent, the CLI uses the same owner-only atomic
preferences. A busy or uncertain live channel refuses an offline replay.
Pending approval blocks preference mutation. Invalid contents default to
Personal with a diagnostic. Tests can isolate candidates with `--instance NAME`;
browser integration still uses its separately owned standard desktop route.

Stop changes authority without waiting for provider work. Already dispatched
native effects remain uncertain; cancellation attempts paired input release.
A late provider retains its single physical slot until it returns. Restart can
recover a missing companion; Quit reaps the owned companion. These are bounded
fault trials, not hard guarantees for every native call or kernel failure.
[Tactical 111](../docs/tactical/111-linux-runtime-presentation.md) records exact
x64 development-candidate evidence and open ARM64/package release gates. This
feature has not been published or installed as a replacement.

## Updates and removal

**Settings → Check for updates** checks the shared desktop release feed.
AppImage installs authenticate the signed incoming version and package, then
replace the app and restart with access Off. Stop active access before installing.
Debian installations show update availability; install their updates through APT.

Before removal, disable **Start at login** and **Stop shortcut**, then Quit.
Remove a Debian install with `sudo apt remove machine-control`; remove an
AppImage by deleting its file. Remove the unpacked extension from Chrome if it
was enabled. Explicit browser setup creates owned files under the user's
`machine-control` data directory and native host registration in Chrome's
configuration directory; ordinary package removal does not erase user data.

Linux participates in the [single desktop release](../release/desktop.md).
Download the public x64 or ARM64 packages from
[machinecontrol.dev/downloads](https://machinecontrol.dev/downloads/).
[Desktop 0.5.0](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.0)
is the first public Linux desktop preview.

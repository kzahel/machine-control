# Ubuntu Wayland UI Automation

LinuxVM Testbed combines semantic AT-SPI control with a provider-level visual
fallback. Neither path is sufficient alone.

## Preferred Order

1. Use `linuxvm exec` for system and file work.
2. Use `linuxvm user-exec` for non-UI work owned by the desktop account.
3. Use `linuxvm gui-launch` to start a graphical application through the
   active user's systemd manager.
4. Use `linuxvm control` for resident semantics and normalized results.
5. Use `linuxvm ui` for direct diagnostic AT-SPI commands.
6. Use resident capture and the in-guest virtual HID broker when semantics are
   missing.
7. Reserve normalized UTM screenshot/input for bootstrap and recovery.
8. Ask the user to enter passwords or other secrets directly in the guest.

## Launching GUI Applications

`user-exec` deliberately does not guess a Wayland socket. Launch graphical
programs through the desktop user's imported systemd environment instead:

```bash
unit="$(bin/linuxvm gui-launch -- gnome-text-editor)"
bin/linuxvm user-exec -- systemctl --user status "$unit"
```

The launch command fails closed if the user manager has neither
`WAYLAND_DISPLAY` nor `DISPLAY`. It prints the transient service name so a
caller can inspect logs or stop it without matching an unrelated process. The
unit remains active across a self-updating application's process replacement
and is collected after the final process exits.

## AT-SPI Commands

Inventory application roots before assuming a process name:

```bash
bin/linuxvm ui apps
bin/linuxvm ui windows --app gnome-terminal-server
```

Inspect a bounded flat tree:

```bash
bin/linuxvm ui tree --app gnome-terminal-server --depth 8 --limit 500
bin/linuxvm ui tree --app gnome-terminal-server --interactive --depth 8
```

Search and act:

```bash
bin/linuxvm ui find Close --app gnome-terminal-server
bin/linuxvm ui actions Close --app gnome-terminal-server
bin/linuxvm ui press 'New Tab' --app gnome-terminal-server
bin/linuxvm ui focus Search --app org.gnome.Nautilus
bin/linuxvm ui set-value Search 'release notes' --app org.gnome.Nautilus
```

Queries are case-insensitive substrings over name, role, and description.
Exact accessible-name matches win; otherwise the first tree-order match is
used. Inspect `find` before acting when a name is repeated.

## Resident Requests

Use `linuxvm control` for ordinary agent automation. An agent already inside
the guest invokes `/usr/local/bin/machine-control` with the identical JSON:

```bash
bin/linuxvm control '{"operation":"status"}'
bin/linuxvm control '{"operation":"applications"}'
bin/linuxvm control \
  '{"operation":"snapshot","target":"org.gnome.Nautilus","query":"Search","projection":"compact"}'
```

The active-user resident owns one generation and bounded snapshot cache.
Actions, focus, and values require an exact reference from that generation; do
not re-resolve a stale path silently. Results report the native AT-SPI route
and distinguish confirmed delivery from an independently unverifiable effect.

Qt and Chromium can publish native action slots with empty names. A requested
press may use the first unnamed slot, reported as `index:N`; require an
independent effect before accepting it. The deterministic profiles cover
these cases:

```bash
bin/linuxvm fixture qt reset
bin/linuxvm fixture qt state
bin/linuxvm fixture browser reset
bin/linuxvm fixture browser state
```

## Application Roots

AT-SPI reports accessibility providers, not a window-manager process list.
Launcher and server roots may coexist. The observed Terminal window and widget
tree live under `gnome-terminal-server`; `gnome-terminal` has no child window.
Electron and browser content may require the application's accessibility mode.
The accepted Qt fixture uses XWayland plus
`QT_LINUX_ACCESSIBILITY_ALWAYS_ON=1`; its pure Wayland launch did not publish
usable semantic children. Chromium is launched with
`--force-renderer-accessibility` for deterministic browser coverage.

## Wayland Boundary

Global X11 tools such as `xdotool` are not used. AT-SPI performs semantic
actions inside the user session. The dedicated-appliance broker creates a
persistent virtual HID device through `/dev/uinput`, which GNOME/Mutter
receives as target-local input. Its active-user socket is mode `0600`; the
service and its full-desktop authority remain root privileged.

The semantic helper does not edit GNOME permission stores or bypass a lock
screen. The virtual HID broker does run as root for the dedicated appliance.
XDG RemoteDesktop/ScreenCast could later provide a bounded-workstation profile,
but it retains the portal's explicit consent flow. The current appliance route
does not claim compositor-mediated authorization: it is root-authorized global
input for a disposable, dedicated test system.

GNOME 46 Settings on the accepted image publishes recognizable AT-SPI labels
with zero-sized widget bounds. Ground the fixed appliance window with resident
capture, use the resident virtual HID fallback, and verify the setting through
an independent OS read. Do not present those coordinates as semantic bounds.

## Normalized Coordinates

`linuxvm screenshot` captures the visible UTM window, removes its macOS title
bar, and scales the guest viewport to the configured display. UTM's native
scripting API accepts those pixels for `click`. UTM has no drag primitive, so
`drag` maps the same pixels back into the visible host window.

Always capture immediately before a coordinate action. Dynamic resolution,
window resizing, a different GNOME scale, or an unexpected dialog can make an
old coordinate unsafe.

Before SPICE integration exists, the pointer can be relative/captured and
absolute clicks may be unreliable. Use raw scan-code shortcuts such as
`key ctrl-alt-t` to establish the guest agent and install `spice-vdagent`.

## Authentication And Secure Surfaces

AT-SPI exposes enough of the tested Polkit dialog to detect it and cancel it
without a secret; it does not remove the authentication requirement. Routine
root administration instead uses the explicit root-equivalent QEMU
guest-agent command channel. The CLI has no password option, and screenshots
containing authentication context are generated artifacts rather than
repository content.

GDM, lock screens, and a logged-out desktop may use a different user and D-Bus
session. They are deferred protected planes, not accepted ordinary routes.
Treat `ui health` failure there as a session boundary and use the outer UTM
path only for explicit recovery.

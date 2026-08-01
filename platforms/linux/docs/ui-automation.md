# Ubuntu Wayland UI Automation

LinuxVM Testbed combines semantic AT-SPI control with a provider-level visual
fallback. Neither path is sufficient alone.

## Preferred Order

1. Use `linuxvm exec` for system and file work.
2. Use `linuxvm user-exec` for non-UI work owned by the desktop account.
3. Use `linuxvm ui` for named controls, actions, text, and values.
4. Use normalized screenshot and physical input when semantics are missing.
5. Ask the user to enter passwords or other secrets directly in the guest.

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

## Application Roots

AT-SPI reports accessibility providers, not a window-manager process list.
Launcher and server roots may coexist. The observed Terminal window and widget
tree live under `gnome-terminal-server`; `gnome-terminal` has no child window.
Electron and browser content may require the application's accessibility mode.

## Wayland Boundary

Global X11 tools such as `xdotool` are not used. AT-SPI performs semantic
actions inside the user session, while UTM injects virtual keyboard and mouse
input outside the compositor's application sandbox.

The helper does not edit GNOME permission stores, run as root, or bypass a
lock screen. XDG RemoteDesktop/ScreenCast portal support could later provide a
clean PipeWire stream, but it would retain the portal's explicit consent flow.

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

AT-SPI may expose a Polkit dialog's non-secret controls but does not remove its
authentication requirement. The user enters passwords in the guest. The CLI
has no password option, and screenshots containing authentication context are
generated artifacts rather than repository content.

GDM, lock screens, and a logged-out desktop may use a different user and D-Bus
session. Treat `ui health` failure there as a session boundary and use the
outer UTM path.

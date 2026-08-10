# Architecture

LinuxVM Testbed separates provider transport, guest identity, semantic UI, and
outer recovery. No healthy layer is allowed to hide failure in another.

## Host Provider

`providers/utm-macos/provider.sh` owns:

- UTM lifecycle, clone, disposable, and IP commands;
- QEMU guest-agent command and file transport;
- normalized UTM-window capture;
- UTM text and scan-code input; and
- UTM-native absolute coordinate clicks and host CoreGraphics drags.

The provider contains no GNOME widget knowledge. Display dimensions come from
configuration and must match the guest's current logical mode.

## Command Completion Contract

`utmctl exec` is a submission mechanism, not the observable completion
contract. Each `linuxvm exec` invocation creates a private directory beneath
`/var/tmp/linuxvm-testbed/run`, redirects stdout and stderr, and writes a
numeric `status` file last. The host polls the status file and returns only
after it exists.

The wrapper must:

- preserve argv boundaries using shell quoting;
- return the guest process's actual exit code;
- keep stdout and stderr on their respective host streams;
- time out rather than imply success; and
- garbage-collect only run directories older than one day, so a long command
  cannot be deleted by a concurrent invocation.

This contract was added after UTM 4.7 returned from a compound APT inspection
before its last output files existed.

## Guest Identity

QEMU guest-agent execution is root. This is appropriate for bootstrapping,
packages, services, and recovery, but it is the wrong identity for desktop
automation.

`linuxvm user-exec` discovers the active logind session (or uses an explicit
configured user), switches with `runuser`, and supplies:

```text
XDG_RUNTIME_DIR=/run/user/UID
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/UID/bus
```

It does not guess a Wayland socket or copy credentials.

Ignored local configuration can require a candidate/disposable role and bind
the selected UTM VM to both its exact name and UUID. Guest execution, file
push, startup, restart, shutdown, suspend, force-stop, clone, and disposable
operations then fail before mutation if any part of that identity is wrong.
This protects a prepared source from a stale friendly-name selection; it is
not an authorization boundary against someone who can edit local config.

`linuxvm gui-launch` crosses the additional application-lifetime boundary. It
verifies that the active user's systemd manager already has an imported
`WAYLAND_DISPLAY` or `DISPLAY`, then creates a collected transient user
service. The service uses `ExitType=cgroup`, so an application can replace its
main process during an updater relaunch without systemd killing the new
process. The graphical process inherits the real desktop environment from
that manager and is not killed when the guest-agent invocation completes.

## Semantic UI

`guests/ubuntu/ui/linuxui.py` is deployed to
`/usr/local/libexec/linuxvm-testbed/linuxui.py` and invoked on demand. It reads
the active desktop through AT-SPI and exposes applications, windows, flat tree
records, searches, actions, focus, editable text, and numeric values.

AT-SPI application roots do not always match launcher process names. GNOME
Terminal, for example, exposes the window under `gnome-terminal-server`, while
the launcher may separately appear as `gnome-terminal`. Callers must discover
with `ui apps` instead of assuming.

## Resident Facade

`linuxcontrol.py` runs as an active-user systemd service and owns one private
Unix socket beneath that user's runtime directory. The outside testbed wrapper
and `/usr/local/bin/machine-control` inside the guest use the same newline-
delimited request path. Local versus remote use therefore changes transport
placement, not the operation or result vocabulary.

The resident normalizes status, capabilities, applications, windows,
compact/full snapshots, actions, focus, and editable/numeric values over
native AT-SPI. Snapshot references bind to a random resident generation and
bounded snapshot cache. A restart or evicted snapshot refuses the reference as
stale. Delivery is reported separately from effect because AT-SPI
acknowledgement does not prove that an application changed. Some Qt and
Chromium providers publish unnamed native action slots; the facade may invoke
the first such slot for a requested press, but only an independent fixture or
OS effect can accept the result.

The same resident invokes Ubuntu's packaged `gnome-screenshot` from the active
GNOME session for full-display and current-active-window PNGs. Artifacts live
in a private cache namespace, carry dimensions and a digest in the result, and
can be fetched by UUID through the outside wrapper without admitting arbitrary
guest paths. This is target-native capture; it neither observes nor focuses the
UTM window.

The target-native visual-input fallback is a root system service with one
persistent `/dev/uinput` device. It accepts a bounded JSON vocabulary over a
mode-`0600` Unix socket owned by the active desktop account. The user resident
adds display geometry and normalized result metadata; the broker never accepts
commands, paths, or arbitrary device events. The route is still powerful: it
can drive the whole logged-in desktop and is honestly reported as privileged
dedicated-appliance control, not same-user isolation.

Unicode text uses `wl-copy --paste-once` in the active Wayland session and a
virtual Ctrl+V. This avoids keyboard-layout assumptions and reports the
clipboard side effect. A deterministic GTK fixture writes each semantic,
pointer, drag, scroll, key, and text effect to a separate JSON oracle.

Framework acceptance adds a PyQt5/XWayland fixture with the Qt accessibility
bridge explicitly enabled and a loopback browser fixture opened in Chromium
with renderer accessibility forced on. The latter yields rich document
semantics while retaining a canvas that requires the visual route. GNOME 46
Settings is the converse mixed case on the accepted image: its labels are
useful, but its GTK4 control extents are zero, so a fixed-display capture and
virtual HID action are paired with an independently read setting effect.

Application launch uses the active user's systemd manager with one owned
transient unit per argv array. The result can wait for an independently
observed AT-SPI application root. Termination is restricted to those owned
unit names or an AT-SPI-published process. Registered desktop activation uses
`gtk-launch`; generic AT-SPI top-level activation fails with a typed GNOME
Wayland limitation instead of silently substituting a global click.

## Outer Recovery

The UTM window remains the lowest common denominator for:

- the Ubuntu installer and first boot;
- a missing or stopped QEMU guest agent;
- GDM, lock screens, and session loss;
- incomplete or hung accessibility providers; and
- password or Polkit dialogs that remain user-authenticated.

Host capture removes the UTM title bar and scales the guest viewport to the
configured logical resolution. UTM's scripting API accepts those logical
coordinates for clicks and also supplies text and raw PC scan codes. Because
UTM exposes no drag command, CoreGraphics reverses the capture transform for
drag gestures.

`LINUXVM_FORBID_OUTER_UI=true` makes every UTM-window observation and input
command fail closed. Doctor and smoke runs in that mode require neither a
visible UTM console nor host Screen Recording/Accessibility permission. A
separate read-only host-state oracle can prove that accepted target-resident
operations left the host cursor and foreground application unchanged.

Routine `shutdown` is synchronous from the caller's perspective: the provider
requests a normal UTM guest power-down and polls until the state is `stopped`.
It times out with the last observed state and never escalates to force-stop.

## Optional Future Layers

- Cloud-init or Ubuntu autoinstall can produce a fresh image.
- The XDG RemoteDesktop and ScreenCast portals can supply direct PipeWire
  frames and compositor-approved EIS input after explicit user consent. They
  remain an important bounded-workstation profile, but the dedicated appliance
  route avoids a consent selector on each fresh automation setup.
- SSH can be an optional non-root transport, but must use public keys and may
  not replace the credential-free guest-agent recovery path.

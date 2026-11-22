# Linux locked use

Topic: `linux-locked-use`

Status: native GDM reauthentication exercised on Ubuntu 24.04 GNOME Wayland
appliances. Unlock, a native application effect and relock passed on the
x64 appliance with the upstream accessibility fix, and on stock Ubuntu
26.04.1 x64 with GNOME 50.1. The GNOME 50 VM prototype passes covered unlock,
GUI control, and relock. The installed Debian integration adds enrollment
and the prepared Desktop owner. Package and physical acceptance are in progress.

A private Debian installation on the matching Ubuntu 26.04.1 VM has
enrolled the account, accepted a prepared Desktop owner, and unlocked behind
the GNOME cover. The fixture verified offscreen capture and an AT-SPI
effect. The same console relocked after owner disconnect and task expiry.
The VM also recorded a pointer click during a delivery-reporting failure.
The follow-up checks compositor input reporting and simulated physical
takeover before workstation or release acceptance.

## Current

The GNOME provider opens GDM's reauthentication channel for the active,
already-signed-in local Wayland account. GDM runs the installed password
conversation. The provider waits for both the compositor and logind to confirm
that the original session unlocked. It also supports re-locking that same
session and verifying the result. [Tactical 166](../docs/tactical/166-linux-gnome-unlock.md)
owns the acceptance evidence and reproduction.

[Tactical 167](../docs/tactical/167-gnome-compositor-cover.md) qualifies
the GNOME 50 cover, underlying pixels, a typed pointer click, and relock on
simulated motion. The cover paints on the physical scene while the authorized
capture uses a private offscreen framebuffer. The root activity observer
supplies opaque input and motion facts independent of compositor routing.

The Debian integration uses a native setup dialog and a privileged GDM
helper. The helper releases the password only to its bound authentication
worker after verifying the locked session and the compositor cover. The
Desktop owner, helper and compositor each enforce a bounded task lifetime.
The [operator guide](../desktop/LINUX-LOCKED-USE.md) describes setup and
revocation. Approved Browser work uses its [separate setting](linux-desktop.md).

## Decision

Use the existing prepared Desktop owner and consent model for the workstation
integration. The provider takes an already-bound console, an authorization
check and a one-shot credential callback. Account selection, enrollment,
deadline, physical takeover and cover/relock ownership belong to the
workstation's guarded task lifecycle. The task must acquire coverage of
every physical display before credential delivery. Keep covers in place
until the exact console is independently observed locked, including after
Stop, owner or resident loss, expiry, input takeover and display changes.

Only the GNOME Wayland provider is in scope. Qualify Ubuntu 24.04 and 26.04
independently. Other compositors and greeter sessions need their own native
providers, threat model and effect oracles. Preserve the installed stock GDM
authentication policy and allow one recognized password prompt per operation.

## Open

- Qualify the packaged Desktop sequence. The native prototype passes on
  stock Ubuntu 26.04.1. Ubuntu 24.04 qualification needs the equivalent
  accessibility cache fix in the target distribution.
- Extend compositor-level coverage acceptance beyond the single-display VM.
  Verify hotplug, real displays and physical devices across the lock transitions.
- Qualify unavailable, changed, and expired credentials and interrupted PAM
  conversations through the packaged helper.
- Qualify keyboard, scrolling, and drag separately through the installed
  Desktop owner. Ordinary portal sharing still ends at lock.
- Qualify the covered route through the packaged app on GNOME 50, including
  physical takeover, displays and actual native effects.

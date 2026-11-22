# Linux locked use

Topic: `linux-locked-use`

Status: native GDM reauthentication exercised on Ubuntu 24.04 GNOME Wayland
appliances. Unlock, a native application effect and relock passed on the
x64 appliance with the upstream accessibility fix. Workstation
enrollment and covered Desktop access are open.

## Current

The GNOME provider opens GDM's reauthentication channel for the active,
already-signed-in local Wayland account. GDM runs the installed password
conversation. The provider waits for both the compositor and logind to confirm
that the original session unlocked. It also supports re-locking that same
session and verifying the result. [Tactical 166](../docs/tactical/166-linux-gnome-unlock.md)
owns the acceptance evidence and reproduction.

The Linux desktop package still refuses prepared locked Desktop owners.
Approved Browser work can still proceed while the console is locked under its
[separate setting](linux-desktop.md).

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

- Qualify the post-unlock application sequence on the stock target
  distributions. The x64 test isolated a known accessibility cache defect
  in Ubuntu 24.04 and passed with GNOME's fix. Ubuntu 26.04 ships a newer
  upstream version with that fix.
- Prove compositor-level coverage across lock transitions and monitor changes.
  A normal application window has no guarantee of staying over every physical
  display. Establish an independent relock mechanism and exercise process loss.
- Add operator-authorized enrollment and revocation with a secret transport
  separate from ordinary requests. Qualify unavailable, changed, and expired
  credentials and interrupted PAM conversations.
- Verify which AT-SPI, capture and input operations can safely work under a
  cover. The ordinary Linux resident closes its portal when the session locks;
  any restored capture/input needs compositor and portal acceptance.
- Qualify the covered route through the packaged app on GNOME 50, including
  physical takeover, displays and actual native effects.

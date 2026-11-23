# Linux locked use

Topic: `linux-locked-use`

Status: the installed Debian package passed covered Desktop tasks on stock
Ubuntu 26.04.1 x64 with GNOME Shell 50.1. Other Ubuntu releases and physical
workstations have separate acceptance gates.

The private package built from `c324588` displayed the native password dialog,
including its protected text field. The claimed VM's one-shot credential
transport exercised the packaged helper's enrollment. A prepared Desktop
owner unlocked behind the cover. The fixture verified offscreen capture,
AT-SPI, a pointer press and release, keyboard input, Unicode text, drag, and
scroll. The same console relocked after owner disconnect, expiry, simulated
physical movement, and Stop. Simulated movement also paused covered access.
Uninstall removed the privileged service and its enrollment.
The same package stayed locked on early cancellation, renewed the same
covered owner, and relocked after the resident was killed. In a separate
fault-injected VM run, the GDM worker flushed the password submission and
then died. The native observations found no uncovered unlock, and the
tested build erased the enrollment when it could not verify delivery.
Repeating the fault on the same VM with the updated helper kept the encrypted
enrollment. After the console relocked, a fresh covered task unlocked with
that enrollment, captured the fixture, and relocked on disconnect.

Mutter can deliver native virtual events without reporting them to the stage
filter. The response identifies submission or observed compositor adoption.
An application or OS observation is needed to verify the effect.

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

End interrupted or unconfirmed attempts and keep the encrypted enrollment.
There is no automatic retry. A fresh authorized task can use the saved
password after verified relock and cover teardown. A changed account password,
an explicit rejection or an invalid credential store still invalidates setup.

Only the GNOME Wayland provider is in scope. Qualify Ubuntu 24.04 and 26.04
independently. Other compositors and greeter sessions need their own native
providers, threat model and effect oracles. Preserve the installed stock GDM
authentication policy and allow one recognized password prompt per operation.

## Open

- The native GDM prototype also passed on Ubuntu 24.04 with an upstream
  accessibility fix. The packaged covered route still requires GNOME 50.
- Extend compositor-level coverage acceptance beyond the single-display VM.
  Verify hotplug, real displays and physical devices across the lock transitions.
- Qualify changed and expired credentials end to end and test slower PAM
  conversations beyond the stock VM configuration.
- Qualify installed setup and physical takeover on a workstation, including
  a display that has entered power saving. Ordinary portal sharing still
  ends at lock.

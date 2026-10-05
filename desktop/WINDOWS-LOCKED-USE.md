# Windows desktop bounded locked use

This is an unreleased development feature. Signed installed-package, ARM64
live and physical takeover acceptance remain separate gates. The current
source profile places an **opaque cover on one display** before possible
password submission. Windows 10 version 2004 or newer, active DWM composition
and exactly one display are required; unsupported preparation refuses before
credential use. Covered VM qualification is tracked in Tactical 102.

## Operator preparation

1. Stop access and install the optional helper in **Permissions → UAC and
   elevated apps → Install helper…**. Complete Windows administrator approval.
2. Prepare a controller key and public approval proposal using the existing
   [unlock controller guide](../release/windows-unlock.md#controller-preparation).
   Keep the private key and credential source on the controller. Only the
   public proposal belongs on the Windows target.
3. In **Access**, choose **Set up Machine Control helper**. Select the public
   proposal, elevate, then approve the displayed account, transport account,
   controller fingerprint and lifetime. Both accounts must match the desktop
   operator's current local console account for this profile.
4. Enable **Also while the screen is locked**, then enable observation and
   control access. Locked use starts off on each app run. Changing the option
   revokes access and requires fresh native consent.

Installing the helper alone neither arms unlock nor enables desktop access.
The desktop and its resident remain Medium integrity. The administrator-owned
`MachineControlDesktopUac` service hosts a separate `desktop` unlock grant and
an independently supervised SYSTEM relock worker. It inherits no appliance
authority. Removing the helper also removes this controller approval; replacing
its version requires explicit removal, installation and approval again.

## Agent task and credential transport

Retain a `ControlSession` with `prepared_console=True`, exactly `observe` and
`control` scopes, and a finite duration of at most 900 seconds. Ordinary
operations refuse while the console is locked. Call `session.unlock.prepare`
through that owner to obtain public task preparation. Unowned callers cannot
prepare an unlock, and ordinary JSON has no password transport.
The owner must have begun with the console locked. An unlocked-origin task
cannot gain unlock or relock authority from a later idle lock; close it and
acquire a fresh locked-origin task instead.

Supply the returned `data` as a controller-local JSON preparation file to
`unlock-controller.py unlock --instance desktop --desktop-preparation FILE`,
along with the approved proposal, controller key, canonical private credential
file, and an authenticated carrier command. The carrier runs the installed
protected executable with `unlock --relay --instance desktop`. The bundled
helper is under `mc-cli/release/`; it requires Python 3 and OpenSSL on the
controller. Outside machine-testbed callers must retain their exclusive target
claim on this transport.

The signed challenge binds the exact resident and task callback. The service
checks the live owner and native grants, and starts its relock guardian before
credential delivery is possible. The controller opens its credential source
only after native authorization and exact stock password-field readiness.
Passwords travel once through the dedicated bounded binary stream and are not
cached. Failed or unknown delivery is never automatically retried.

Wait for confirmed unlock, then use the same task owner for ordinary semantic
control and capture. Unlock rotates ordinary observation generations: discard
old window references. Close the owner when work finishes. Password unlock
confirms an existing session; it does not establish cold login or switch users.

## Relock, takeover and failure

Completion, owner disconnect, task or grant expiry, Pause, Stop, changed
controller approval, or resident/service heartbeat loss requests stock Windows
lock. The guardian is bound to the exact console account and logon session,
has its own finite deadline, and retries lock until independently observed.
It must not lock a replacement user's session. These cleanup requests apply
only to locked-origin tasks. Tasks that start unlocked finish without requesting
lock, and an OS/user lock during ordinary work is left intact. A relock barrier prevents new
work until trusted completion and locked-session evidence agree.

The native input monitor treats non-injected keyboard or pointer input as
physical takeover, swallows physical input until relock, pauses access and ends
temporary use. Covers stay alive until independent locked-session readback,
including resident/service failure. Native capture excludes the cover and
injected agent input passes through it. This distinction is
not an authentication boundary against other privileged software. Hook failure
and monitor stalls fail closed. After a service crash, restart the app and
enable access again; the old task cannot resume automatically. Manual Pause
and physical-takeover pauses require explicit Resume.

This profile supports the existing local-account, unique-display-name and
stock-password-field restrictions of the unlock broker. PIN, domain/cloud
accounts, account switching, RDP, cold login and multiple displays have no
acceptance claim. Presentation privacy does not hide work from other local
capture programs that deliberately exclude the cover. It does not weaken UAC, secure desktop, Windows Hello,
password or lockout policy. Same-user unrestricted shell access is not
contained by desktop consent or a same-user controller key.

Abrupt guardian-process death, display hotplug, other topmost overlays and
physical hardware have no privacy qualification. Covers are ordinary Windows
presentation windows; no zero-frame exposure guarantee is claimed.

## Validation

[Tactical 101](../docs/tactical/101-windows-desktop-locked-use.md) owns candidate
identity, live checks, cleanup and remaining gates. The command-driven actor
is `tests/windows/desktop-locked-use-live.py`; a separate claimed controller
supplies setup consent, dedicated credential delivery and independent OS lock
observations. Credentials never enter its phase mailbox or evidence.

Focused x64 VM evidence includes existing-session unlock, native semantic
effects/capture, task completion/disconnect/expiry and Pause relock, plus final
operator Stop, injected pointer/keyboard effects and independent relock after
service or resident termination. The tactical distinguishes candidate hashes,
partial runs and infrastructure recovery; these results are not signed release
qualification or physical takeover evidence.

[Tactical 102](../docs/tactical/102-windows-covered-control.md) owns the new
cover and task-origin qualification. Its development evidence does not expand
the signed-package, hardware or broader provider acceptance above.

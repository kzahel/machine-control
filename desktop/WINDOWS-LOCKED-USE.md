# Windows desktop bounded locked use

The advanced controller feature ships in public desktop 0.5.7. Native one-time
enrollment below is unreleased source. It stores a recoverable password and is
not the preferred final setup; the [password-free investigation](../topics/windows-protected-unlock.md#password-free-direction)
tracks the alternative authentication-extension route. Signed installed
feature, ARM64 live and physical takeover acceptance remain separate gates. The current
source profile places an **opaque cover on one display** before possible
password submission. Windows 10 version 2004 or newer, active DWM composition
and exactly one display are required; unsupported preparation refuses before
credential use. Covered VM qualification is tracked in Tactical 102.

## Native desktop setup (unreleased source)

1. Stop ordinary access. In **Access**, choose **Set up…** beside **Covered
   desktop access while locked**. Windows requests administrator approval and
   installs the helper if needed; no file or JSON proposal is required.
2. In the native Windows credential dialog, enter the displayed local account's
   Windows password once, rather than its PIN. The helper validates it once and
   saves a SYSTEM-user DPAPI encrypted copy with SYSTEM/admin-only file access.
   Cancellation leaves existing enrollment unchanged. A newly installed helper
   can remain installed and unarmed after cancellation.
3. Successful setup enables the covered-desktop option. It persists as a local
   preference, separate from ordinary access consent. Enable observation and
   control access for the work you authorize. Setup itself grants no agent access.

Use **Update saved password…** after changing the Windows password. Use
**Remove unlock setup…** to erase enrollment. Changing the covered-desktop
option revokes ordinary access; approve access again. Browser-only work uses
**Settings → Allow approved browser access while locked**, requires no unlock
password/helper/cover, and leaves Windows locked.

The resident remains Medium integrity. The administrator-owned
`MachineControlDesktopUac` service hosts the protected `desktop` policy and
credential store. It exposes no credential export or generic decryption API.
Removing the helper erases enrollment. Updating the protected helper preserves
existing enrollment if the new native prompt is cancelled. Cold login means
a new sign-in after boot or sign-out; other users and cold login remain outside
this desktop profile.

## Enrolled agent task

Retain a `ControlSession` with `prepared_console=True`, exactly `observe` and
`control` scopes and a finite duration of at most 900 seconds. The owner must
start with the console locked. Dispatch `session.unlock` through that owner;
no controller key, credential file or password is sent by the agent. Unowned
requests and ordinary JSON credentials are refused. An unlocked-origin task
cannot gain unlock/relock authority from a later idle lock; acquire a fresh
locked-origin task instead.

The service accepts this route only from the actual installed Medium resident,
with live owner and consent checks. It starts the independent cover/relock
guardian, prepares the stock lock screen, and discovers the exact account's
password field before decrypting the saved credential. It submits once and
erases transient credential buffers. Failed or unknown credential use
invalidates enrollment and requires explicit local setup; no new task can
silently replay the credential. Unknown delivery must never be retried.

Wait for confirmed unlock, then use the same owner for ordinary semantic
control and capture. Unlock rotates ordinary observation generations: discard
old window references. Close the owner when work finishes. This confirms an
existing session; it never establishes cold login or switches users.

## Advanced outside-controller protocol

The separate [controller-key protocol](../release/windows-unlock.md) remains
available. Install the optional helper in Permissions. Launch its installed
`machine-control-windows.exe unlock-desktop-advanced-setup` from the interactive
console to import and approve a public proposal; keep the private key and
credential source on the outside controller. Both target and transport account
must match the desktop operator's current local console account.

With this policy, a retained locked-origin owner dispatches
`session.unlock.prepare` and gives its public preparation to
`unlock-controller.py unlock --instance desktop --desktop-preparation FILE`,
alongside the approved proposal, controller key, canonical private credential
file and authenticated carrier. The carrier runs the protected executable with
`unlock --relay --instance desktop`. Keep the exclusive testbed claim on that
transport. This advanced mode reads a credential once after native field
readiness and does not cache it. It cannot use native enrollment metadata to
bypass controller proof. Native enrollment instead uses `session.unlock`.

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
requires explicit Resume. Covered physical takeover retains consent and
permits a fresh task after observed relock and 30 seconds of conservative
session quiet. If the owner unlocks to work, access stays paused until relock
plus quiet or explicit Resume. Ordinary human input also pauses admission;
agent-injected input does not count as takeover. No old action is replayed.

[Tactical 103](../docs/tactical/103-windows-activity-pause.md) owns this
activity behavior shipped in 0.5.7 and its separate qualification gates.

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

[Tactical 134](../docs/tactical/134-windows-native-unlock-enrollment.md) owns
native enrollment and `tests/windows/desktop-enrolled-live.py`. The separate
`WindowsUnlock.Contracts` prompt fixture accepts a one-shot binary credential
only after discovering the exact native setup password field. Its controller
resolves the canonical credential locator and retains the target claim.

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

# Existing-session unlock provider

This original MIT implementation adds an explicit alternate authorization path
for unlocking an already logged-in console session. It uses an Authorization
Services plug-in, a root LaunchDaemon, and the ordinary MacVM UI resident.
The accepted profile is an explicitly opted-in disposable appliance. The API
continues to identify the provider as experimental because its loginwindow
policy composition and IOKit session signals are version-sensitive.

The [runbook](../../../docs/session-unlock.md) describes setup and use.
[Tactical 034](../../../../../docs/tactical/034-macos-session-state-and-unlock.md)
owns implementation acceptance. The earlier experiment remains in
`platforms/macos/experiments/authorization-unlock` as historical evidence.

## Components and authority

- `Session.h` reads console lock/session evidence and validates one-use grants.
  `Probe.m` exposes the same observer without privileged installation or TCC.
  It is packaged inside MacVM UI, and doctor can call the app's read-only
  `session-state` command even while the resident is stopped.
- `Broker.m` runs as root through launchd. Its fixed local socket implements
  only status and an existing-session unlock transaction. Kernel peer UID/PID
  and dynamic code-signature validation must match the installed resident's
  exact CDHash and the opted-in UID. A claimed name, bundle identifier, or
  Machine Control target-use claim cannot authorize arming.
- `Plugin.m` grants only its fixed mechanism. A grant must match the current
  locked console session, boot, purpose, broker epoch, live broker and peer,
  monotonic expiry, and enabled root-owned policy. Atomic consumption allows
  at most one successful consumer.
- `Installer.swift` is an explicit administrator executable, never setuid or
  reachable through the broker. It owns fixed destinations, validates signed
  artifacts, records original/installed policy, and retains the password
  branch. Failed installation disables the alternate path and attempts
  conflict-aware restoration; the receipt remains for recovery.
- `build.sh OUTPUT` builds and signs only; it does not install or alter the
  controller. Signing defaults to ad-hoc for the tested local appliance.
  `MC_UNLOCK_SIGN_IDENTITY` can select an available signing identity, but
  notarized/downloaded distribution is a separate acceptance requirement.

The helper serializes unlock transactions. It creates a ten-second grant,
acknowledges arming on the authenticated connection, and waits for OS unlock.
The resident rechecks the console session and invokes the measured native
loginwindow trigger. Disconnect, timeout, disable, restart, or observed session
change revokes remaining authority. The resident returns delivery and observed
OS effect separately and never retries an uncertain attempt automatically.

The current callback cannot authenticate the initiating agent. The grant
permits the next matching mechanism evaluation for that console session; a
competing evaluation may consume it. This short session-wide window is an
explicit appliance authorization, not a per-agent bearer token or containment
against the same user with a shell or sudo. Session sampling and notifications
also do not make global input atomic with OS transitions. Ordinary input
refuses known locked/unknown state and failed activation; residual OS races
remain disclosed rather than promised away.

## Installation state and recovery

Root-owned private state is under `/var/db/machine-control-unlock`; the broker
socket is under `/var/run/machine-control-unlock`. A minimized, root-owned,
world-readable preferences plist exposes disabled/enabled configuration when
the daemon is absent. It contains no caller identity, grant, or credential.
Actual installation health still requires verification; disabled plus an
unreachable helper is reported with unknown health, not presumed healthy.

The installer pins the resident and protected artifact hashes. Rebuilding the
resident can preserve its TCC identity while changing its unlock authorization:
rerun explicit provider installation to authorize the new hash. Ordinary
bootstrap and maintenance repair never grant that authority implicitly.

Disable revokes authority and restores the original screensaver policy while
retaining components/receipt. Uninstall then removes the owned dedicated right,
plug-in, daemon, and state. Both refuse to overwrite unrelated policy changes.
If restoration conflicts, the grant path remains disabled and the retained
receipt permits administrator diagnosis. Reinstallation is convergent and may
restart the helper, invalidating its generation even when the payload matches.

No account credential enters the unlock API. Normal password fallback is
preserved but is not a newly implemented loginwindow credential-entry API.
Unlock exposes the desktop and leaves it unlocked. Display covering, local
input blocking, automatic relock, fresh login, and preboot are excluded.

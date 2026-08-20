# Windows Non-PTY Administration Readiness

Status: complete

Owning topics:

- [`target-lifecycle-and-readiness`](../../topics/target-lifecycle-and-readiness.md)
- [`windows-resident-control`](../../topics/windows-resident-control.md)

## Objective

Make the retained Windows appliance's key-only non-PTY SSH route suitable for
unattended administration and common readiness checks. Completion requires a
machine-readable command to finish without PTY allocation, `target doctor` to
have an explicit guest-command bound, and the repaired route to survive a
changed Windows boot epoch.

## Boundaries

- Keep public lifecycle and transport implementation in `machine-control` and
  concrete target selection in private inventory.
- Do not install a Win32-OpenSSH preview without evidence that its server code
  owns the observed delay.
- Do not treat `ssh -tt`, terminal escape filtering, or outer UTM input as an
  automation repair.
- Do not interrupt Windows during the documented ten-minute boot window or
  promote a clean reboot to force-stop.
- Keep key-only authentication, UAC, firewall, ACL, and resident privilege
  policy unchanged.

## Work

### 1 — localize the delay

Direct client traces showed TCP connection, key exchange, and public-key
authentication completing in less than one second. A non-PTY exec request was
accepted at about one second, but its first output and EOF arrived four to nine
seconds later. Equivalent PTY execution returned promptly.

Native Windows PowerShell 5 took 3.6–4.1 seconds to start even with
`-NoProfile`, while child `cmd.exe` and `where.exe` processes started in a few
hundred milliseconds. The testbed helper then launched a second Windows
PowerShell inside the already configured PowerShell SSH shell, and Windows
doctor repeated that cost across four SSH sessions. Adding remote sleep did not
remove the delay, so this was not the upstream short-command/no-output race.

### 2 — provide a stable native automation shell

Fresh bootstrap now selects the correct ARM64 or x64 PowerShell 7 ZIP archive,
verifies its pinned SHA-256, validates the extracted runtime, and configures
its stable Program Files path plus the OpenSSH `-c` command option. This avoids
Store/MSIX application-execution aliases and keeps bootstrap architecture
explicit.

Post-update audit reports the exact runtime and registry invariant. Candidate
repair can reinstall the verified archive, restore the registry values, and
restart `sshd` only when an OpenSSH invariant was unhealthy.

### 3 — remove repeated shell and transport startup

The common PowerShell helper now submits a UTF-16LE/base64 script to the
already configured shell as a script block instead of spawning a nested
`powershell.exe`. Windows doctor sends one minimized script that observes the
interactive desktop and invokes resident status and capabilities. A host-side
60-second bound terminates that one probe and reports a typed administration
failure rather than waiting forever.

Automatic persistent SSH multiplexing was tested and rejected: a persistent
master could retain redirected output descriptors and keep a piped diagnostic
caller open. The single-probe design supplies the useful latency reduction
without a background connection lifetime.

### 4 — prove live persistence

The retained ARM64 appliance installed PowerShell 7.6.5 from the verified
archive and selected it as the OpenSSH shell. Warm direct non-PTY tracing
placed authentication at about 0.5 seconds, exec acceptance at 0.6 seconds,
first output at 2.2 seconds, and EOF at 2.4 seconds.

Before repair, common Windows doctor took roughly 80–90 seconds. The single
bounded probe completed a warm ready observation in 13.3 seconds. Immediately
after the cold reboot it completed in 18.4 seconds. The official maintenance
repair-and-reboot path took 9 minutes 37 seconds including its intentionally
heavy pre/post audits, observed a changed boot epoch, and returned every
administration, desktop, resident, semantic, capture, and input dimension
ready.

## Validation

- Windows shell scripts parsed without errors under the installed native
  PowerShell parser.
- Windows smoke fixtures cover the one-shell request shape and forced
  one-second doctor timeout.
- The live post-update audit reported the native OpenSSH automation shell,
  key-only policy, restricted key material, firewall, services, toolchains,
  and pending-reboot state healthy.
- A non-PTY marker and a complete common doctor passed after the changed boot
  epoch.

## Result

Non-PTY SSH is again the ordinary machine-readable administration route. PTY
remains interactive-only, outer control remains recovery-only, and the
retained appliance satisfies the bounded reboot/readiness requirement for
unattended CI use.

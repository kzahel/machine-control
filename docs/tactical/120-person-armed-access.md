# 120 — Person-armed access retention

Status: active. Implemented on Mac, Windows and Linux. Installed retention is
verified on a personal Mac (local Developer ID build) and on Windows and
Linux ARM64 VMs (signed 0.6.4 candidates). Mac lock/unlock and Stop with the
person present, and x64 installed checks, remain.
Owning topic: [host control](../../topics/host-control.md#person-armed-access-is-the-persons-to-end).

## Objective and completion conditions

A comparison agent ran `grant revoke` at the end of its task, as the host
skill then instructed, and silently disarmed access the operator had turned
on until stopped. On Mac the saved consent was deleted, so the access did not
return. The operator asked that indefinitely armed access be hard to disable
accidentally: only an explicit, clearly intended action by the person should
end it.

Complete when, on Mac, Windows and Linux:

- a caller's revoke leaves person-armed access and its saved state intact and
  reports that it was retained;
- a caller's revoke still ends a timed grant from an approved agent request;
- ending a request grant never deletes the person's saved arming; and
- the person's own Stop still ends everything immediately.

## Boundaries

Grant scopes, approval prompts, durations, locking, pause and policy presets
are unchanged. This does not contain a deliberate same-user agent. Agent
request grants remain target-wide.

## Ordered work

### 1 — macOS resident

- Record `origin` (`person` or `request`) on every grant: app and menu
  arming and restored consent are `person`; approved requests are `request`.
  Report it in grant JSON.
- `grant.revoke` from the socket: for a `person` grant, journal
  `access.revoke_retained` and answer `revoked: false`,
  `retained: "person_armed"`; for a `request` grant, end it with
  `revoked_by_caller`. Never suspend trusted callers from a caller revoke.
- Saved consent is cleared only by the person's Stop reasons or by the end of
  a `person` grant for a reason that already cleared it. Caller revocation and
  the end of a `request` grant keep it, so the person's arming is restored
  on the next reconciliation.
- Swift tests at broker, consent and real-socket server level.

### 2 — Windows resident

Same contract in `DesktopGrants`/`UserHost`. Windows has no restart
persistence, so the in-memory grant is the state to protect: person access
that an approved agent request replaces is kept aside and returns when that
request grant expires or its caller revokes it. The person's Stop, desktop
loss and updates clear both.

### 3 — Linux companion

The GNOME companion (`desktop/native/linux`) had the same unconditional
revoke; apply the identical in-memory contract.

### 4 — visibility and resident stop

Notify the person when access ends for a non-person reason; refuse
`server.stop` from ordinary socket callers on personal hosts.

## Validation

Per platform: unit/contract tests, then an installed check in which the
person arms until stopped, a CLI `grant revoke` reports retained access,
capture still works, an approved request grant can be revoked, the person's
access returns, and Stop ends it. Mac also checks lock/unlock and restart.

## Final result

### Windows and Linux

**Current:** Both report `origin`, retain person-armed access on a caller
revoke (`revoked: false`, `retained: "person_armed"`, journal
`access.revoke_retained`), and restore it after a replacing request grant
ends. Windows desktop grant contracts pass, including retention, restoration
after revoke and expiry, Stop clearing, and no restoration of lapsed timed
person access; ARM64/x64 publishes succeed. Linux grant tests cover the same
cases; one earlier test that expected an approved request to permanently
replace indefinite access now expects restoration. The installed acceptance
scripts (`tests/windows/desktop-installed.ps1`,
`tests/desktop/linux-until-stopped.py`) assert the retained revoke through the
real product socket after native arming.

Installed evidence, signed 0.6.4 candidates from `9995fbb`, claimed ARM64
VMs started from off and shut down afterwards:

- **Linux GNOME Wayland:** the installed acceptance script passed end to end
  through the graphical user manager: native AT-SPI arming of **Until I turn
  it off**, null countdown, visible status, independent GTK fixture effect,
  caller revoke reported `retained: person_armed`, the grant kept `origin:
  person`, observation continued, and native Stop revoked access. Two
  script repairs were needed: wait for session readiness after the socket
  answers, and match the status wording case-insensitively.
- **Windows 11:** the signed installer, exact 2394-file inventory and
  publisher signatures verified. An independent UIA actor in session 1 armed
  until-stopped access through the native UI; a socket `grant.revoke`
  returned `revoked: false, retained: person_armed` with the same
  `until_stopped` person grant; the native Stop then ended it
  (`lastEnded: stopped_by_person`) and a later revoke was a no-op. The
  script now finds the duration option among the combo box's items even when
  the short popup reports it offscreen, then scrolls it into view.

**Open:**

- The Windows script's later until-stopped steps (fixture launch and
  observation through direct `call`) predate required live ownership
  (`54c72fe`) and fail with `control_session_required`; they need an owner
  session. The retention checks now run before them.
- A stale `runtime\browser-extension\README.md` dated before this run sat in
  the Windows install folder and broke the exact-inventory check; the current
  uninstaller removed the whole folder, so an older install/uninstall left it.
- x64 installed retention checks are not run. The public 0.6.4 release at
  `48b87b7` subsequently passes Windows `dotnet format`, all native contract
  suites and signed ARM64/x64 packaging; [121](121-desktop-0.6.4-release.md)
  records that source qualification separately from installed effects.
- The Linux VM keeps the 0.6.4 candidate installed (previously 0.5.4).

### macOS

**Current:** Implemented in `94de04f`; 178 resident tests pass, including
real-socket revoke retention and restoration after a request grant ends.

Installed check on a personal Mac with until-stopped access armed: a local
build of that commit, signed with the same Developer ID so it met the
installed app's designated requirement, replaced the installed 0.6.0 and the
resident restarted. Saved consent restored all four scopes with no click
(`origin: person`, `approver: local_consent`), so macOS permissions carried
over. A CLI `grant revoke` and a `desktop raw` revoke both returned
`revoked: false, retained: "person_armed"`; the same grant stayed active, a
display capture succeeded, the saved consent was byte-identical, and the
Activity journal recorded `access.revoke_retained`. Lock/unlock, Stop and
re-arm with the person present remain to be checked.

Deployment notes from that check:

- Writing files into an app bundle under `~/Applications` from an agent shell
  was refused with "Operation not permitted" (App Management protection);
  renaming whole bundles on the same volume worked. A partial copy left the
  LaunchAgent unable to spawn the resident until the original was renamed
  back, after which 0.6.0 also restored the until-stopped consent unaided.
  Swap complete, separately staged bundles by rename only.
- The installed 0.6.0 bundle failed strict deep verification because the
  bundled CLI had written `__pycache__` files inside it. The packaged
  `mc-cli/bin/machine-control` is a copy of the repository entry point with a
  `/usr/bin/env python3` shebang, so another Python could run it and write
  bytecode; the `commands/` launcher already used `-B`. The entry point now
  disables bytecode whenever it runs from an installed payload.
- The rename-only swap is documented in the
  [desktop README](../../desktop/README.md#replace-an-installed-mac-app-with-a-local-build).

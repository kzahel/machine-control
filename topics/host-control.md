# Host Control

Topic: `host-control`

Status: developer preview implemented and accepted on a disposable Tart
guest; not yet installed or accepted on a physical Mac, and not a supported
personal-machine profile. [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md)
owns the first slice.

## Scope

Run Machine Control on a physical computer the controller user owns, rather
than only on disposable VMs, and make it safe enough to install on a main
workstation. This covers the shared grant broker, deployment presets, the
menu bar application, local host targeting, and attended-away operation.
Browser control has its own topic, [`browser-control`](browser-control.md).

The product aim is a less limited alternative to agent-coupled Computer Use
tools: the whole desktop, including the Dock, menu bar, and system UI, gated
by explicit, visible, revocable grants rather than by a fixed list of
permitted applications.

## Current

**Current:** a shared [Tauri operator app](../desktop/README.md) embeds the
existing Swift resident. Local Developer ID packaging and a first native Tart
UI pass are complete; exact signed CI artifacts and upgrade acceptance are
tracked by [tactical 051](../docs/tactical/051-tauri-macos-desktop.md).
The earlier AppKit operator remains available for appliance bootstrap.

**Current (2026-09-30):** One ad-hoc-signed `Machine Control.app`
(`org.machine-control.app`), built from the
[resident package](../platforms/macos/resident), serves Tart guests and
physical hosts. It runs as a per-user Aqua LaunchAgent on a mode-`0600`
socket and shows a menu bar item. A root-owned policy file selects the preset;
guests receive `appliance`, and a Mac without the file is a `workstation`.
Tart guests were migrated to it without outer input and pass resident
conformance apart from the Cua-dependent text cell, which the guest cannot run.

**Current:** Every operation passes the grant broker before any provider runs.
In a workstation instance inside the guest, capture, input, and browser calls
were refused with `approval_required` until a prompt was approved. Approval,
denial, timeout, manual arming from the menu, the Stop hotkey, revocation,
narrowing to view-only, and refusal of input aimed at the app's own status
item were observed live. Expiry, desktop-lock revocation, and prompt-time
pausing are covered by unit and socket-level tests.

**Current:** A setup checklist replaces the permissions submenu. It opens
while macOS consent is missing, shows each grant's live state in plain terms,
and opens the exact settings pane. A short-lived child process detects a new
Screen Recording grant that the running app cannot see yet, and the app then
restarts itself under its LaunchAgent. On the development Mac this flow
granted both permissions; System Settings' own "Quit & Reopen" dialog still
appears afterwards and is out of date, so the checklist tells the person to
choose Later. Opening the bundle directly starts the LaunchAgent.

**Current:** The common client has a default `host` target
(`macos-host-resident`) with a local-socket adapter and `grant
request|status|revoke`. It has not yet been run against a resident on a
physical Mac.

**Current:** The optional root unlock broker still authenticates the resident,
not the original caller; workstation policy does not register protected
operations, and host installation installs no root helper.

**Current:** The Windows ordinary-user workstation host
([Tactical 036](../docs/tactical/036-windows-workstation-distribution.md))
refuses protected operations but does not gate ordinary control behind an
approval.

## Decisions

**Decision:** One program serves VM guests and physical hosts. Both install the
same application bundle, with the same code identity, resident, and menu bar;
only the deployment policy differs. On a VM the policy grants standing access
and the menu bar shows that; on a personal host it requires approval. Existing
Tart guests move from the testbed identity to the shared one once, which needs
a single renewal of macOS consent through the existing guest consent bootstrap.

**Decision:** Policy has two independent axes:

- **Operation set.** `ordinary` covers capture, semantic observation, actions,
  input, and application lifecycle. `protected` adds unlock, administrator
  sheets, and credential entry. Operations outside the set are not registered.
- **Grant mode.** `standing` means the policy itself is the grant. `approval`
  means each grant comes from an approver. Approvers are pluggable: local click
  first, then Touch ID, then out-of-band approval such as a phone or
  authenticator.

The named presets are combinations of these:

| Preset | Operation set | Grant mode | Intended installation |
| --- | --- | --- | --- |
| `appliance` | ordinary, plus protected when separately installed | standing | disposable VM guests; today's behavior |
| `unattended` | ordinary, plus protected when separately installed | standing, later out-of-band approval | dedicated physical machines, such as a headless mini desktop |
| `workstation` | ordinary | approval | a personal or shared computer |

**Decision:** Trusted installation policy selects the preset. The resident
reads a root-owned policy file and treats a missing, unreadable,
non-root-owned, or group/other-writable file as `workstation`. Request fields,
environment variables, arguments, and user-writable preferences cannot widen
it. On a personal machine this means that switching to a standing preset
requires an administrator password. That is not containment against an agent
that already has passwordless `sudo`.

**Decision:** Grants and target-use claims stay separate. A claim coordinates
which agent uses a target; it is not authority and must not become a bearer
credential. The resident may record the caller's claim ID with the grant in its
audit log.

**Decision:** The grant check runs in the resident's operation dispatch, in the
process that owns the macOS consent. A menu bar front end in front of an
ungated socket would be bypassable by any same-user process. For the same
reason, the macOS host application bundles the resident and its UI in one
signed process.

**Decision:** The initial host application was native Swift/AppKit. It reused the
menu bar, login item, setup/repair/uninstall, and release patterns of
[lid-awake](https://github.com/kzahel/lid-awake), a sibling macOS utility with
a signed privileged helper. The grant and approval protocol lives in the
resident and `contracts/`, so a later cross-platform shell, for example Tauri
with the existing updater infrastructure, can replace the menu without moving
enforcement.

**Decision:** The desktop product moves to a shared Tauri operator UX and the
existing desktop release infrastructure. The first Mac slice embeds the Swift
resident in the Tauri native process as a framework, preserving grant
checks, the permission owner, and same-process approval authority. It does not
rewrite providers. Windows and a named Linux workstation profile follow their
own acceptance gates. [Tactical 051](../docs/tactical/051-tauri-macos-desktop.md)
owns packaging and exact signed-artifact validation.

## Workstation grant model

**Current:** In the MVP, the workstation preset is off by default.

- An agent requests a scope (`observe`, `control`, or `browser`), a duration,
  and a free-text reason with `grant request`. The request blocks until approval, denial, or a
  bounded timeout.
- The prompt shows the reason and the caller's kernel peer process and parent
  chain, labelled unverified. The approver may grant a narrower scope or a
  shorter duration.
- Ordinary operations without a live grant fail fast with `approval_required`
  instead of opening a prompt on every call.
- An active grant changes the menu bar indicator and records operations in a
  bounded recent-actions list. Stop in the menu or a global hotkey revokes it
  immediately. Expiry, revocation, resident restart, and session or desktop
  transitions invalidate it along with outstanding element references.
- While a prompt is visible, the resident refuses all synthetic input, and it
  always refuses actions targeting its own windows, so a controlled session
  cannot approve itself.

**Open:** An MVP grant arms the whole target, not only the requester. While it
is active, any same-user process can use it. The CLI opens a new connection
per request, so the caller shown in the prompt informs the approver and the
audit log but does not bind the grant. The intended fix is a durable
connection: the agent's client (for example an MCP or YepAnywhere adapter)
holds one socket open, the grant attaches to that connection, and it ends when
the connection closes.

**Open:** Other same-user programs with Accessibility permission can still
click a click-approval prompt. Touch ID approval (LocalAuthentication) removes
that path and is the planned second approver.

**Decision:** The limit remains the one stated in
[`architecture`](architecture.md#deployment-safety-profiles): gating Machine
Control does not sandbox an agent that already has an unrestricted shell as
the same user.

## Attended-away operation

The goal is for an agent to use a physical machine while the person is away
and the screen is locked, while keeping it physically protected against
casual local access, including with the laptop lid closed.

**Upstream-claimed:** OpenAI documents a comparable opt-in Codex “Locked use”
mode on macOS. An authorization plug-in lets an active turn temporarily unlock
the session while all displays are covered and local use is blocked. Local
keyboard or pointer activity relocks the screen and pauses automatic unlock
until the person unlocks manually. The
[screen-lock investigation](../platforms/macos/docs/lock-screen-investigation.md#codex-computer-use-comparison)
records the source review; it was not exercised.

**Proposal:** Add an away mode that the person arms explicitly, with a bounded
duration, before locking the screen.

- An agent request while locked uses the existing authorization-plug-in broker
  to unlock. The broker issues a grant only while away mode is armed, so the
  host never needs a stored login password.
- While unlocked, a curtain window covers every display. It ignores mouse
  events and is excluded from the resident's own ScreenCaptureKit capture, so
  the agent sees the desktop and people nearby do not.
- A presence guard watches for hardware-originated keyboard and pointer events,
  lid opening, display reconfiguration, and the power button. Any of these locks
  the screen immediately, revokes the grant, reports an
  `interrupted_by_physical_presence` result, and disarms automatic unlock
  until the person unlocks manually.
- Closed-lid operation combines this with lid-awake's sleep-disable
  mechanism. Opening the lid is then a strong presence signal.

**Open:** Whether a closed built-in display without an external display
leaves a WindowServer display that can be captured and targeted. A virtual
display (`CGVirtualDisplay`, private API) is a candidate if not.

**Open:** Whether the authorization plug-in's persistent policy change is
acceptable on a personal machine, or whether disarming away mode must also
restore the original policy. Storing the login password for typed unlock is
the rejected alternative unless the plug-in route proves unworkable.

**Open:** Whether Machine Control should absorb lid-awake's sleep control or
coordinate with it as a separately installed utility. Coordinating first
avoids two tools owning `pmset disablesleep`.

## Next direction

1. Finish [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md):
   install on the development Mac with the person granting macOS consent,
   approving prompts, and loading the unpacked extension.
2. The `unattended` preset on a dedicated physical machine.
3. Away mode: curtain, presence guard, relock, then closed lid.
4. Touch ID and out-of-band approvers; connection-bound grants.
5. Remote callers of a physical host over SSH or YepAnywhere, with prompts that
   identify remote callers.
6. Shared Tauri desktop UX, Developer ID signing, notarization, and the
   Desktop Release Kit update contract; the
   personal-machine support statement in [`SECURITY.md`](../SECURITY.md).
7. The same model on Windows, reusing the ordinary workstation host.

# Host Control

Topic: `host-control`

Status: proposed. The macOS resident is accepted only on disposable Tart
appliances; no physical-host or personal-machine profile is implemented or
supported yet. [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md)
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

**Current:** The macOS resident is one Swift source compiled inside a Tart
guest, ad-hoc signed under a testbed bundle identity, and started by a
per-user LaunchAgent on a mode-`0600` socket. Any process running as that user
can call any registered operation. The optional root unlock broker
authenticates the resident, not the original caller, and its installation
persistently enables the alternate unlock policy. Both are appropriate only for
the disposable-appliance profile described in
[`macos-resident-control`](macos-resident-control.md).

**Current:** The common CLI reaches the macOS resident only through `tart exec`
or SSH. There is no local host transport and no grant or approval concept.

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

**Decision:** The first host application is native Swift/AppKit. It reuses the
menu bar, login item, setup/repair/uninstall, and release patterns of
[lid-awake](https://github.com/kzahel/lid-awake), a sibling macOS utility with
a signed privileged helper. The grant and approval protocol lives in the
resident and `contracts/`, so a later cross-platform shell, for example Tauri
with the existing updater infrastructure, can replace the menu without moving
enforcement.

## Workstation grant model

**Proposal:** In the MVP, the workstation preset is off by default.

- An agent requests a scope (`observe`, `control`, or `browser`), a duration,
  and a free-text reason. The request blocks until approval, denial, or a
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

1. [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md): shared
   resident package, policy and grant broker, menu bar application,
   click approval, local host target, and the unpacked browser extension.
2. The `unattended` preset on a dedicated physical machine.
3. Away mode: curtain, presence guard, relock, then closed lid.
4. Touch ID and out-of-band approvers; connection-bound grants.
5. Remote callers of a physical host over SSH or YepAnywhere, with prompts that
   identify remote callers.
6. Developer ID signing, notarization, and Sparkle updates in CI; the
   personal-machine support statement in [`SECURITY.md`](../SECURITY.md).
7. The same model on Windows, reusing the ordinary workstation host.

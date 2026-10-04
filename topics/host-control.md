# Host Control

Topic: `host-control`

Status: signed Tauri preview accepted in ARM64 Tart. Earlier source-native
setup/browser behavior has physical Mac evidence; full signed Tauri physical
desktop acceptance remains open. [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md)
owns the first slice.

## Scope

Run Machine Control on a physical computer the controller user owns, rather
than only on disposable VMs, and make it safe enough to install on a main
workstation. This covers the shared grant broker, deployment presets, the
menu bar application, local host targeting, and attended-away operation.
Browser control has its own topic, [`browser-control`](browser-control.md).

**Decision — planned evolution:** temporary pauses should preserve otherwise
valid authorization, with explicit Resume distinct from Stop. Polite
activation, live waiting requests and their physical/VM resource semantics
belong to [access admission and pause](access-admission-and-pause.md).
That proposed plan does not change the current grant/restart behavior below.

The product aim is a less limited alternative to agent-coupled Computer Use
tools: the whole desktop, including the Dock, menu bar, and system UI, gated
by explicit, visible, revocable grants rather than by a fixed list of
permitted applications.

## Current

**Current:** a shared [Tauri operator app](../desktop/README.md) embeds the
existing Swift resident. Signed/notarized Apple silicon and Intel CI candidates
are verified; the exact ARM64 CI app and signed installed upgrade pass native
Tart operator checks. [Tactical 051](../docs/tactical/051-tauri-macos-desktop.md)
owns initial candidate evidence. [Tactical 052](../docs/tactical/052-macos-production-updates.md)
owns accepted production updates. The [desktop matrix](../docs/desktop-acceptance.md)
separates package, architecture, VM, and physical-host evidence.
The earlier AppKit operator remains available for appliance bootstrap.

**Current (2026-09-30):** The source-native ad-hoc-signed `Machine Control.app`
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
request|status|revoke`. CLI/doctor work with the signed Tauri resident in Tart.
A full signed-product desktop task through this adapter on a physical Mac
has not been established by the current acceptance records.

**Current (2026-10-02):** Public signed/notarized ARM64 `0.4.8` now has a
bounded physical-Mac smoke test through the common host adapter: visible
macOS consent, off-state refusal, local Tauri approval, native AX button
action with an independent counter effect, exact-window Quartz capture,
and keyboard delivery to the fixture text field. Access was revoked and the
fixture and target-use claim were cleaned up. Concurrent human input means
exact text equality was not established. This is partial physical evidence;
browser, restart/update, lock, emergency Stop, and full product acceptance
remain open.

**Current:** The optional root unlock broker still authenticates the resident,
not the original caller. Workstation policy refuses standalone protected
operations; ordinary host installation installs no root helper. The separate
[locked-use opt-in](macos-locked-use.md) installs a covered-session profile
through native System Settings approval in Permissions and binds it to
approved bounded control. The Settings checkbox only changes the preference.

**Current:** The Windows ordinary-user workstation host
([Tactical 036](../docs/tactical/036-windows-workstation-distribution.md))
refuses protected operations but does not gate ordinary control behind an
approval.

**Decision:** The standalone Windows app adds resident-enforced approvals in a
distinct desktop instance while retaining the component profile. Its current
workstream is [Windows desktop](windows-desktop.md), executed by
[Tactical 053](../docs/tactical/053-windows-desktop.md).

**Current:** The Windows desktop profile now passes exact signed x64 VM
grant/UI/lifecycle and local/outside CLI acceptance. The existing YA component
retains its distinct authorization boundary. [Windows desktop](windows-desktop.md)
owns current status; [Tactical 053](../docs/tactical/053-windows-desktop.md) owns
the execution record.

## Decisions

**Decision:** The desktop operator is a compact settings dialog. Use short
labels, status rows, and direct controls; omit marketing copy, page subtitles,
hero banners, and repeated explanations. Keep grant scope and same-user reach
visible beside approval controls. The shared Tauri UI follows this direction.

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

**Decision:** Every packaged desktop local operator can choose **Until I turn it off** when
manually enabling selected scopes. That in-memory grant has no timer and
reports `lifetime: until_stopped` with null expiry and remaining seconds.
Stop, caller revocation, leaving an unlocked desktop, and resident exit still
end access. Restart starts with access off. Agent approval requests retain
bounded durations; they cannot create this lifetime through the public socket.
The shared UI exposes this choice only when the native operator advertises
support. Windows and Linux implementation and release acceptance are owned by
[Tactical 091](../docs/tactical/091-desktop-until-stopped.md). Existing platform
pause/session behavior remains; that slice does not add restart persistence. Public `0.4.9` passes signed ARM64 Tart checks for visible selection,
null expiry/countdown, selected scopes, independent fixture effect, Stop,
Restart with access off and retained permissions, and bounded agent approval.
[Tactical 057](../docs/tactical/057-macos-until-stopped-release.md) owns this
targeted acceptance. Signed lock/recovery and full physical acceptance remain open.

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
audit log but does not bind the grant. [Caller authorization](caller-authorization.md)
owns the Desktop-first plan for automatically granting bounded access to a
trusted integration. Native executable identity has a bounded validation
result; the real broker, authenticated session channel and revocation remain
pending. No target-wide grant becomes session-bound through advertisement.

**Open:** Other same-user programs with Accessibility permission can still
click a click-approval prompt. Touch ID approval (LocalAuthentication) removes
that path and is the planned second approver.

**Decision:** The limit remains the one stated in
[`architecture`](architecture.md#deployment-safety-profiles): gating Machine
Control does not sandbox an agent that already has an unrestricted shell as
the same user.

## Attended-away operation

**Decision:** the first Mac version uses a persistent, default-off locked-use
setting, native helper approval in Permissions, ordinary access approval,
and a bounded active
control session. The person locks normally; temporary unlock occurs behind
covers. Physical input relocks, revokes access, and pauses automatic unlock
until manual unlock. Keep the Mac awake with its lid open.

The sibling [macOS locked-use topic](macos-locked-use.md) owns current scope,
implementation, and acceptance. [Tactical 064](../docs/tactical/064-macos-locked-use.md)
records execution. This follows OpenAI's documented locked-use experience;
Machine Control owns its explicit task connection and completion semantics.
No stored login password is used.

**Open:** closed-lid operation remains deferred. Determine whether a closed
built-in display without an external display retains a capturable WindowServer
display, and whether to coordinate with lid-awake rather than take ownership
of its sleep policy. Neither sleep prevention nor virtual displays belongs to
this first implementation.

## Next direction

**High priority:** investigate [caller authorization](caller-authorization.md)
before treating target-wide arming as suitable for isolating agent sessions.
This promotes the previously deferred connection-bound grant concern; the
linked topic owns the investigation and acceptance requirements.

1. Finish [Tactical 050](../docs/tactical/050-macos-host-control-mvp.md):
   install on the development Mac with the person granting macOS consent,
   approving prompts, and loading the unpacked extension.
2. The `unattended` preset on a dedicated physical machine.
3. Away mode: curtain, presence guard, relock, then closed lid.
4. Touch ID and out-of-band approvers.
5. Remote callers of a physical host over SSH or YepAnywhere, with prompts that
   identify remote callers.
6. Shared Tauri desktop UX, Developer ID signing, notarization, and the
   Desktop Release Kit update contract; the
   personal-machine support statement in [`SECURITY.md`](../SECURITY.md).
7. The same model on Windows, reusing the ordinary workstation host.

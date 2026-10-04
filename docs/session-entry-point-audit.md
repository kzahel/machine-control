# Session migration: entry points and authority

Status: **Current, source-reviewed** inventory; migration changes below are
**Proposal**. Reviewed against `3b23fd9863f6b1e19a53360569f3747e0db9c2ff`.
Owning topic: [unified desktop client](../topics/unified-desktop-client.md).
Execution record: [Tactical 093](tactical/093-session-entry-point-audit.md).

## Scope and evidence

The first migration step inventories public command families and independently
reachable provider paths. It asks where exact-resource claims, caller authority,
active ownership and effect serialization are actually enforced. It does not
equate a signed executable, supplied claim ID, same-user socket, or persistent
connection with an authenticated agent session.

This is a bounded source audit, not penetration testing, installed-build
acceptance, a complete opcode-by-opcode security review, or a reproduction of
an OS resource leak. Sources below are the evidence anchors. Existing fixtures
were rerun without connecting to targets; platform-native execution and races
at real provider dispatch remain acceptance work. Direct privileged or
unrestricted shell access remains outside cooperative claim containment.

## Common client and claim boundary

| Entry point | Current gate and authority | Concurrency/lifetime | Migration implication |
| --- | --- | --- | --- |
| Common CLI `desktop`, `control`, `browser`, `grant`, `update`, `os`, `testbed`, `ios` | `require_selected_claim` checks the selected adapter only when its `claimPolicy` is `required`; default desktop VMs and physical desktop hosts require it | Adapter subprocess per call; a claim reserves an exact target, not a command sequence | Keep command grammar; make applicable operations use the shared session boundary |
| Readiness, inventory and bootstrap | Target status/doctor/capabilities and selected precreation/pinning commands are exempt; workspace handlers own their own claim composition | No ordinary desktop ownership implied | Preserve diagnosis and exact-identity bootstrap; audit create/release separately rather than blanket-requiring an existing target claim |
| `run` / `ClaimSession` | Common claim authority, optional queued admission; inherited selection and explicit renewal | Scoped runner owns task/claim cleanup; queued channel has its own liveness | Retain claim ownership separate from a control connection borrowing it |
| `ControlSession` / `control call` | Checks claim when required, then opens adapter `channel`; session carries resource generations | Long-lived transport; keepalive; one-shot CLI composition closes after its call | Reuse as the migration foundation; its Python client is not the final authority |
| Claim store and channel guardian | Exact provider/resource binding under the claim store lock; guardian checks before launch, each frame and periodically | Expiry/replacement closes transport; checks do not renew the claim | Keep one authority. Record lock and pre-forward check are not an atomic lease check across every eventual provider effect |
| Raw same-user shell / direct third-party CLI | OS, SSH, ADB or provider-specific authority | Outside common arbitration | Report this boundary honestly; frontend migration cannot contain an unrestricted same-user shell |

Sources: [common client](../client/machine_control.py)
(`default_host_target`, `DEFAULT_TARGETS`, `operation_requires_claim`,
`require_selected_claim`), [scoped runner](../client/scoped_run.py),
[claim SDK](../client/claim_session.py), [control SDK](../client/control_session.py),
[claim authority](../providers/claims/claims.py),
[transport guardian](../providers/claims/channel.py).

**Current:** ChromeOS, iOS, Android, Quest and Steam Deck default common target
definitions advertise unsupported common claims. That says nothing about
their separate platform leases. Optional-policy adapters and direct resident
calls must not be counted as required-claim routes.

## Desktop ingress matrix

| Entry point/profile | Caller and authorization | Claim / active ownership | Gap or compatibility boundary |
| --- | --- | --- | --- |
| Mac host wrapper | Common claim check; native resident owns grants | `machost` rechecks exact host identity; `channel` uses guardian | Direct Python/socket use skips wrapper claim validation |
| Mac resident one-shot IPC | Private Unix socket, kernel caller attribution; standing appliance policy or same-user workstation grant | Request `claimId` is attribution, not resident validation of ordinary exact-target claims; scoped calls refuse while admission reserves desktop | Unreserved legacy calls retain target-wide access. Main-queue handlers do not reserve focus-then-type across separate callers |
| Mac native admission | Connection-derived owner, scopes, session/resource generations; optional separately verified Desktop delegation | One active desktop owner; one effect in flight per channel; disconnect/heartbeat/Stop cleanup | Ordinary native channel alone does not validate a controller's exact VM claim; supported adapter guardian provides that check |
| Windows host wrapper | Same-user installed desktop route plus exact host claim | Recheck before ordinary calls; live channel uses guardian | Independently callable native client/pipe does not traverse wrapper |
| Windows desktop companion | Pipe ACL for current user; caller PID/name is attribution; desktop grants and generation checks | Owner channel when desktop grants exist; provider semaphore serializes native effects; legacy requests refused during reservation | Outside reservation, approved one-shot requests remain. Browser uses its own asynchronous path with grant/owner checks |
| Windows user/appliance profiles | Headless user host can have no desktop grant broker; dedicated appliance service has its own privileged deployment and pipe policy | Workstation admission is not automatically available in appliance service; controller claims stay at adapters | Preserve explicit deployment profiles. A grant-free appliance route is not equivalent to workstation authorization |
| Linux host wrapper | Exact host claim before control/artifact operations | One-shot only; no `channel` or queued claim-channel branch in this adapter | A desktop owner channel is an implementation gap, not parity implied by CLI syntax |
| Linux desktop companion | Same-UID `SO_PEERCRED`, native grant/generation checks, portal consent | Requests dispatched through GLib; no Mac/Windows owner-session protocol | Existing grant and provider checks must survive owner-channel adoption |
| Linux appliance resident/input daemon | Mode-0600 user-accessible sockets under explicitly provisioned appliance policy; privileged input is a separate daemon | No common claim or workstation grant check inside these resident handlers | Direct sockets bypass adapter claim coordination; do not silently reuse this route for personal desktop grants |
| VM wrappers and platform-native UI commands | Exact VM pin and claim checks; outer operations require disruptive class plus route policy | Mac/Windows `channel` use guardian; Linux VM lacks that common live channel | Calls below the public wrapper retain their own varying guards. Explicit platform escape hatches need coverage, not assumptions from common CLI |

Source anchors:

- Mac: [wrapper](../platforms/macos/bin/machost),
  [Python transport](../platforms/macos/host/machost.py),
  [server](../platforms/macos/resident/Sources/macui/Server.swift),
  [grant classification](../platforms/macos/resident/Sources/macui/Grants.swift),
  [admission channel](../platforms/macos/resident/Sources/macui/AdmissionChannel.swift),
  [caller trust](../platforms/macos/resident/Sources/macui/DesktopCallerTrust.swift).
- Windows: [host adapter](../platforms/windows/host/winhost.py),
  [user host](../src/MachineControl.Windows/UserHost.cs),
  [desktop grants](../src/MachineControl.Windows/DesktopGrants.cs),
  [channel](../src/MachineControl.Windows/AdmissionChannel.cs),
  [appliance broker](../src/MachineControl.Windows/BrokerHost.cs),
  [pipe ACLs](../src/MachineControl.Windows/PipeTransport.cs).
- Linux: [host adapter](../platforms/linux/host/linuxhost.py),
  [desktop companion](../desktop/native/linux/desktop.py),
  [grants](../desktop/native/linux/grants.py),
  [appliance resident](../platforms/linux/guests/ubuntu/ui/linuxcontrol.py),
  [input daemon](../platforms/linux/guests/ubuntu/input/linuxinputd.py).
- VM wrappers: [Mac](../platforms/macos/bin/macvm),
  [Windows](../platforms/windows/bin/winvm),
  [Linux](../platforms/linux/bin/linuxvm),
  [Mac legacy UI entry](../platforms/macos/bin/macui).

## Alternate desktop and privileged paths

| Path | Current enforcement | Migration requirement |
| --- | --- | --- |
| Typed browser operations | Mac/Windows/Linux grant-scoped browser relay; raw evaluation has a broader devtools scope; native provider registration is separate from agent permission | Include browser calls, asynchronous completion and provider disconnect in ownership tests; registering an extension must not grant an agent access |
| Mac raw DevTools WebSocket | Per-grant endpoint token; endpoint and token revoked while desktop admission reserves the resource; independent of common CLI claim validation | Treat as a separately reachable legacy route; preserve revocation and prove it cannot race a newly admitted owner |
| Desktop operator channel | Mac embedded native operator; Windows/Linux inherited operator transport owns grant/Stop/setup lifecycle | Keep operator authority separate; unify target operations without making approval or Resume ordinary agent methods |
| Mac protected operations / covered use | `protected` operations require standing policy and separate credential/generation checks; they are not ordinary `control.dispatch` scoped actions. Covered ownership adds a guardian and relock behavior | Explicitly classify these routes; do not infer coverage from the ordinary scoped-request reservation check |
| Windows protected appliance / workstation unlock | Dedicated appliance broker and session workers differ from optional workstation unlock service; latter checks transport SID, controller proof, policy and session state | Preserve typed secret transport and privilege boundaries; port ordinary ownership only with separate protected acceptance |
| Mac native outer recovery | Borrows an exact disruptive VM claim; reserves host desktop; native effects use claim-store operation lock and owner fencing | Reuse this composition. Ordinary input and outer recovery contend on the host resource; target-native guest work does not |
| Native sudo / unrestricted administration | Independent command authentication or OS transport; desktop grants are not arbitrary shell authority | Keep separately authorized; inventory exact-resource lifecycle conflicts without converting it into a privileged generic UI dispatch method |

Sources: [Mac DevTools](../platforms/macos/resident/Sources/macui/BrowserDevTools.swift),
[Mac relay](../platforms/macos/resident/Sources/macui/BrowserRelay.swift),
[Windows relay](../src/MachineControl.Windows/BrowserRelay.cs),
[Linux relay](../desktop/native/linux/browser.py),
[desktop host](../desktop/src-tauri/src/main.rs),
[Windows operator](../desktop/src-tauri/src/windows.rs),
[Linux operator](../desktop/src-tauri/src/linux.rs),
[Mac outer binding](../platforms/macos/resident/Sources/macui/OuterRecovery.swift),
[Windows unlock](../src/MachineControl.Windows/UnlockService.cs),
[native sudo ownership](../topics/native-sudo.md).

## Device and ChromeOS coverage

| Target/entry | Current authority and contention | Required fit in shared sessions |
| --- | --- | --- |
| ChromeOS CLI and target client | Authenticated SSH carries per-command Python requests; SSH connection reuse already exists. Inspected dispatch has no common claim/desktop-owner enforcement | Add target-local arbitration around existing automation/CDP/capture/input; SSH authentication does not by itself assign an agent owner |
| ChromeOS stream daemon | Persistent framed stdio loop directly invokes capture/input helpers; persistence alone supplies no common claim/owner protocol | Include this second ingress in the same target authority; do not secure only the Bash CLI |
| iOS typed control, forwarding and raw Agent Device wrapper | Exact configured device and Mac host policy; command lease around control/forwarding; task sessions can inherit a matching local lease token | Preserve CoreDevice/XCTest and one device-host authority. Nested token sharing is cooperative reuse, not per-action serialization or authenticated agent identity |
| Android commands | Authorized exact-device ADB; local mutation lease explicitly wraps PIN unlock and reboot. Wake, keyguard dismissal, install, launch, stop and shell dispatch do not all use it | Establish device-operation conflict coverage before promising uniform ownership; retain secret preflight and one-shot delivery |
| Quest commands and transactional session | Local lock plus recoverable device lease/journal for task setup/cleanup; standalone wake/sleep/dialog commands have separate paths; wireless changes check active lease | Compose existing lease and ordinary actions without an independent second owner; preserve cleanup of wake/proximity/reverse state |
| Steam Deck | Common target definition is claim-unsupported; platform-native administration remains separate | Detailed dispatch/lease audit is deferred and must precede a support claim; do not assume Linux desktop admission applies |

Sources: [ChromeOS CLI](../platforms/chromeos/bin/chromeos),
[target client](../platforms/chromeos/client.py),
[stream daemon](../platforms/chromeos/daemon.py),
[iOS adapter](../platforms/ios/ios_device.py) (`active_nested_lease`,
`with_command_lease`, `control`, `forward`, `raw_agent`),
[Android adapter](../platforms/android/android_device.py) (`mutation_lease`,
`unlock_pin`, `main`), [Quest adapter](../platforms/quest/quest.py)
(`LocalLock`, `begin_lease`, `main`).

**Open:** controller-local claim/lease stores are not distributed arbitration.
For a resource reachable from two controllers, qualify one target/device-host
authority or state an explicit single-controller constraint. The audit has
not tested cross-controller exclusion or every direct vendor-tool path.

## Operation and conflict classification for migration

The following is **Proposal**, not a new allowlist or permission grant.

| Operation family | Authority/resource to preserve | Ownership rule to qualify |
| --- | --- | --- |
| Discovery/doctor/capabilities | Minimal non-sensitive readiness | Remain available without ordinary interaction ownership; bounded polling |
| UI tree, windows, capture and artifacts | Observation grant and target/session generation; artifacts remain scoped | Authorized observation must not inherit another caller's grant; start coarse and explicitly qualify concurrent observation |
| Focus, text, pointer, semantic action, clipboard, app/window mutation | Control grant plus interactive resource | Retain owner across related calls; fence stale handles and release held input on interruption |
| Browser tabs, navigation, evaluation/CDP | Browser/devtools scopes plus affected browser/desktop resource | No raw endpoint bypass of ownership; finer tab concurrency needs independent-resource evidence |
| Install, reboot, runner restart, workspace release and lifecycle | Exact target/device and existing lifecycle authority | Conflict with ongoing work; invalidate relevant generations; cleanup uses the correct original owner |
| Protected login/unlock/credential operations | Dedicated policy, identity, generation and secret transport | Explicit integration gate; no authority inherited merely from ordinary control |
| Outer VM focus/input | Exact disruptive VM claim plus shared host desktop | Compose resources, honor absolute route prohibitions, retain independent recovery |
| Operator Stop/revoke and cleanup | Operator or narrowly defined stop-only authority | Must not wait behind effect ownership or become an agent self-approval route |
| Shell/admin and factory bootstrap | Declared OS/device-host authority, destination identity and conflict policy | Preserve their plane; creating a new target cannot require its nonexistent claim |

## Findings and first implementation boundary

**Current — gaps established by source review:**

1. Claims are enforced mainly by cooperative controller adapters; raw resident
   ingress does not universally enforce them. Carrying `claimId` in JSON is
   not the missing validation.
2. Owner channels coexist with ambient one-shot grants. Scope checks are
   stronger than no authorization, but they do not reserve a multi-call task.
3. Linux desktop, appliance profiles and device leases have different channel
   and security semantics. API spelling cannot erase those differences.
4. Browser endpoints, protected methods and operator/recovery channels are
   separate ingress classes. A blanket wrapper around ordinary mutations
   would omit relevant paths or accidentally confer operator authority.
5. The shared claim store lock protects claim state, not every operation under
   a claim. Multiple children using one valid claim can still contend.
6. Controller CLI history and resident/provider journals have distinct coverage.
   A migration must preserve correlation without claiming retroactive or
   complete history; see [target audit](../topics/target-operation-audit.md).

**Proposal — next bounded slice:** ordinary Mac and Windows workstation
observation/input/application operations through existing owner channels, with
one-shot and retained-session CLI compatibility. Keep current typed provider
operations. Add no MCP interpreter or new WebSocket endpoint in this slice.

Before coding, specify how the authoritative endpoint binds a validated exact
target claim to its live owner, including local/remote placement and claim
replacement between forwarding and effect dispatch. Do not solve this with an
agent-supplied `already_checked` flag. Separate cooperative from authenticated
profiles and negotiate missing support with a typed refusal, never downgrade.

Completion requires the same outcome and refusal through CLI, SDK and direct
native ingress; two independent callers; concurrent children sharing a claim;
expiry/reacquisition; Pause/Stop; dropped transport; and uncertain delivery
without replay. Fixture-level ChromeOS target placement and iOS device-host
placement must fit the contract before freezing it. Linux/device/protected
live adoption remains a separate per-profile gate. Legacy routes may remain
explicit during migration but cannot be advertised as session-enforced.

**Current — validation:** 9 control SDK tests, 5 transport guardian tests and
14 claim-store tests pass locally. They cover bounded framing/order, stale
claim refusal, claim release/replacement, no implicit renewal, keepalive,
disconnect cleanup and uncertain result handling. They do not prove native
cross-platform enforcement or the proposed migration's completion conditions.

# Unified Desktop Client

Topic: `unified-desktop-client`

Status: accepted first three-desktop client over the current resident
implementations.

## Goal

An agent should use the same ordinary desktop workflow on Windows, macOS, or
Linux by changing target selection rather than changing skills or command
vocabulary. The common client is a facade over the existing residents and
transports, not a fourth UI implementation.

```text
machine-control --target <logical-target> desktop status
machine-control --target <logical-target> desktop applications
machine-control --target <logical-target> desktop snapshot ...
machine-control --target <logical-target> desktop action ...
machine-control --target <logical-target> desktop capture ...
machine-control --target <logical-target> desktop input ...
```

Linux `target reboot` uses the declared platform reboot operation, including
its boot-ID observation. Like suspend, it checks doctor capabilities before
calling the adapter; readiness after restart remains `target ensure-ready`.
A claimed Linux guest passes the common reboot followed by readiness on
2026-09-28; 100 client tests and the Linux static suite also pass.

## Common surface

**Current:** The first portable desktop subset covers:

- `status`, `capabilities`, application and window inventory;
- compact/full semantic snapshots with generation-bound references;
- semantic press/focus/value actions;
- display/window capture and bounded artifact retrieval;
- pointer, click, drag, scroll, key, and Unicode text input where declared;
- application launch, activation, termination, and window close where
  declared; and
- a raw request escape hatch for an operation already defined by a resident.

The client accepts the common request vocabulary and translates only known
historical naming differences, such as Windows `app.launch`, `screenshot`,
`invoke`, `set.value`, `click`, `key`, and `type`. It returns the resident's
actual operation and route alongside the requested common operation. It does
not fabricate capability parity.

## Transports and placement

**Decision:** `desktop call` reaches the resident through the selected
testbed's outside adapter. `desktop call-local` reaches the same resident
through its installed guest-local CLI when the testbed supports that proof.
Both use the same request and result vocabulary and should report one resident
generation.

The common client does not treat the transport as the contract. Windows SSH,
Tart guest execution, QEMU guest-agent execution, a future authenticated
tunnel, and direct local IPC may all carry the same request.

**Current:** the selected Windows adapter now hands ordinary administration
and resident calls directly to OpenSSH after one claim check and one exact UTM
target resolution. The connection uses the resolved guest address internally
while retaining the logical alias as its host-key identity. The generated
standalone alias still uses its self-guarding proxy for independent callers.
A live initially-off acceptance pass measured a 3.07-second median common OS
call and 3.60-second resident status call, down from the earlier 8.3–10.4
second common administration path. A fresh already-resolved SSH call was about
0.40 seconds and a shared connection about 0.23 seconds, so persistent SSH
reuse is deferred: it would not materially reduce the remaining adapter and
claim cost.

## Proposed connection-oriented agent interface

**Proposal:** make a claimed logical session the ordinary interface for
multi-step agent workflows. Keep the CLI supported for discovery, doctor,
claim/lifecycle management, scripts and occasional operations. CLI statelessness
does not require stateless enforcement: a one-shot client can request a short
session, while a task runner, SDK or MCP integration holds one across a workflow.
Low expected concurrency is a convenience assumption, not a reason to bypass
the same admission and authorization checks.

The motivation is reliable ownership across observations and effects, explicit
caller lifetime and reduced repeated setup. Process-launch reduction must be
measured separately; changing the front-end transport does not eliminate
subprocesses inside adapters, claim checks or resident observation.

**Current:** `ControlSession` already provides a live owner channel on supported
profiles. The [admission guide](../docs/access-admission.md) owns its wire and
cleanup behavior. One-shot calls and this channel still coexist; this proposal
does not claim uniform session enforcement across all platforms or operations.

**Proposal:** unify clients around these rules:

- Bind the exact target, existing claim and its generation, permitted scopes,
  verified caller assurance, and active control ownership to a server-side
  session. These remain distinct facts with distinct expiration/revocation
  rules. A claim ID in command arguments selects cooperative ownership; it
  does not authenticate the process presenting it. Connection possession alone
  is likewise not proof of an approved caller.
- Authenticate or explicitly classify the caller when opening the channel.
  A broker multiplexing agents retains separate logical owners and scopes;
  one persistent process must not silently share one claim or grant among them.
  An eligible CLI may use an inherited session channel, or explicitly establish
  its own bounded session, without inventing an agent identity from ancestry.
- Revalidate claim expiry/replacement, authority, pause and resource generations
  at authoritative dispatch. Serialize effects for the contended resource and
  preserve ownership across sequences such as focus-then-type. A claim-store
  record lock or serialized individual handlers does not reserve that sequence.
- End active ownership promptly on caller/channel loss, with finite watchdogs
  as the backstop. A connection borrowing an existing claim does not acquire
  authority to release or renew that claim; the explicit claim owner manages
  its lifetime. Reconnect requires fresh admission, and uncertain effects are
  never automatically replayed.
- Keep CLI, SDK and MCP projections on the same operation/result contract.
  Retain Unix sockets or platform-native IPC locally and authenticated carriers
  remotely. A new WebSocket endpoint is not required to obtain these semantics.
  Audit legacy, browser, protected and recovery routes before claiming uniform
  enforcement; preserve explicit emergency-stop behavior.

**Comparison:** the [Sky dossier](../research/providers/sky-computer-use.md)
provides evidence for a persistent model-facing runtime, app bindings and a
native supervisor owning the service connection. It does not establish the
same claim model or agent-session authentication. Reuse that ergonomic pattern
through an owned implementation, while
[caller authorization](caller-authorization.md) owns identity and grants,
[admission](access-admission-and-pause.md) owns active desktop arbitration, and
[target-use claims](target-use-claims.md) owns exact-resource coordination.
The [provider comparison](provider-landscape.md#optional-sky-provider-and-agent-facing-compatibility)
keeps facade similarity separate from adopting Sky as an optional provider.

### Versioning and implementation boundary

**Proposal:** migrate incrementally to one authoritative session contract,
not two independently implemented old/new operation APIs. Negotiate the session
protocol and advertised capabilities explicitly. Extend existing admission v1
where compatible; introduce a successor only for incompatible lifecycle or
authority semantics. Preserve existing typed operations and result envelopes
where their meaning is unchanged. A product label such as "API v2" must not
substitute for enumerating those compatibility changes.

CLI, desktop integration and agent runtimes should call the same authoritative
dispatch path for target operations. The desktop's native approval, trust,
Pause and Stop controls remain a separately authenticated operator channel;
agents cannot obtain operator authority by calling the same control methods.
Headless deployment must remain usable without the desktop app. Share policy
and contract behavior, rather than requiring identical implementation languages
or process placement across all platforms.

Keep arbitrary model-written Python/JavaScript outside the native resident and
protected broker. A persistent interpreter is a client with bounded resources,
its own cancellation/reset lifecycle, and an explicit execution security
profile. Interpreter persistence does not imply sandboxing or permission to
forward arbitrary code into privileged providers. Its app/device handles call
typed operations and still reject stale references and revoked authority.

**Proposal:** initially reuse the existing Python session client to prove the
contract and compatibility CLI. Prototype one thin persistent model-facing
runtime, comparing Python and JavaScript on identical fixture workflows before
selecting a supported default. Evaluate task success, tool/output ergonomics,
tokens, latency, packaging, process/resource counts and cancellation. A language
choice should not require rewriting native providers or create another policy
implementation. Sky-like handles, compact state/diffs and images are facade
choices, not the universal device or security model.

### Platform fit

**Proposal:** use the same logical session vocabulary with platform-specific
authority placement and capability namespaces:

| Target | Enforcement placement to qualify | Existing implementation to preserve |
| --- | --- | --- |
| Windows, macOS, Linux | Target-resident session boundary, with separately authorized protected providers | Native desktop companions, application APIs and existing provider adapters |
| ChromeOS | Target-local controller reached through authenticated SSH or an equivalent carrier | `chrome.automation`, page CDP, DRM/EGL capture and evdev/uinput; no controller-desktop manipulation |
| iOS | Authoritative Mac device host bound to the exact device and runner generation | CoreDevice/XCTest, signing, pairing and existing device lease; no general resident daemon or shell assumed on the phone |
| Android/Quest | Authoritative device host or qualified resident route, bound to exact device/boot identity | ADB and device-native facilities, current lease and protected-operation policies |

This is a migration map, not a claim that these session endpoints all exist.
Keep device-shaped operations explicit; unsupported windows, shells, protected
input or lifecycle operations must not be fabricated for vocabulary symmetry.
Existing device leases must be adapted or deliberately cut over to the common
authority, never supplemented with an independent competing claim store.
If multiple controllers can reach one resource, identify the single arbitration
authority or an explicit single-controller constraint. Independent local claim
files cannot guarantee cross-controller exclusivity.

Begin with coarse exclusive interaction ownership; add finer app/tab sharing
only after proving resource independence. Observations require their applicable
authorization, while claim-free readiness diagnostics stay available. Capture,
global focus/input, runner restart, installation, administration, protected
control and outer recovery need explicit scope/conflict classifications rather
than one undifferentiated desktop-mutation flag. Shared host input used for VM
recovery must still contend with physical host use.

### Ordered migration and acceptance

**Current:** the first-step [entry-point and authority audit](../docs/session-entry-point-audit.md)
is complete for a bounded source review and existing claim/channel fixtures.
It records direct ingress, profile differences, device leases, conflict
classification and the next implementation gate.
[Tactical 093](../docs/tactical/093-session-entry-point-audit.md) owns the
execution record; the audit owns the detailed coverage matrix.

**Current, source and fixture evidence:** the first migration slice requires
live owner context for ordinary operations in the Windows desktop product.
The common CLI negotiates short ownership on an explicit undispatched refusal;
`control stream` and the existing Python SDK retain one connection across a
workflow. These paths reuse native dispatch, grants and generation checks.
Appliance/headless profiles and existing exact-claim adapter checks remain
separate. This does not yet bind the resident to an authenticated claim issuer
or contain arbitrary same-user shell access. Installed Windows acceptance and
other platform cutovers remain open. See
[Tactical 095](../docs/tactical/095-windows-required-owner-session.md) and the
[CLI lifecycle contract](../docs/access-admission.md#standalone-use).

**Proposal:** preserve the mature provider implementations through a bounded
migration:

1. **Inventory dispatch and authority.** Produce an operation/entry-point matrix
   covering common CLI, platform wrappers, direct resident IPC, browser routes,
   desktop integration, administration and protected/outer paths. Record exact
   authority, resource conflicts, current bypasses, compatibility behavior and
   evidence level. Classify existing profiles honestly; a new session cannot
   turn cooperative same-user access into hostile-process containment.
2. **Prove one shared session boundary.** Reuse the existing Windows vertical
   slice and Mac owner channels for ordinary observation/input/app operations.
   Prove CLI one-shot, CLI retained-task and direct SDK requests reach the same
   checks, generations, provider and outcomes. Use portable fixtures to cover
   ChromeOS/iOS placement before expanding live implementation across platforms.
   This slice has no persistent code interpreter requirement.
3. **Move consumers onto that boundary.** Route desktop target operations and
   existing CLI commands through the session client. One-shot compatibility
   can acquire short ownership or join an explicitly inherited session; scripts
   retain ownership across related calls. Do not silently fall back to legacy
   ambient access when a new endpoint denies or lacks required semantics.
   Retain clearly declared legacy profiles until their parity gate passes.
4. **Add the model-facing runtime.** Hold logical sessions per caller and target,
   expose bounded code execution with reusable handles and rich outputs, and
   keep MCP a projection of the same contract. Multiplexing does not merge
   caller grants. Reset/crash closes owned control; borrowed claims retain
   their separately defined lifetime.
5. **Qualify and cut over each remaining provider.** Exercise ChromeOS and iOS
   early as distinct placement proofs, then Android/Quest and remaining desktop
   cells. Turn down legacy mutation routes per profile only after equivalent
   functionality and negative tests pass. Keep diagnostic/recovery access
   explicit and independently usable.

**Open — release gates:** prove two independent callers, parallel calls sharing
a claim, generation replacement, claim expiry, pause/Stop, reset, dropped
connections, provider crashes and unknown delivery without replay. Test both
local and remote callers and direct-route bypasses. Attribute audit intent,
dispatch and results across clients without recording secrets; preserve the
[audit coverage distinctions](target-operation-audit.md) rather than claiming
that a client log proves provider effects. Measure idle and active subprocess
churn and retained resources separately from UI correctness. No CLI deprecation,
new security guarantee or runtime behavior is established by this proposal.

## Escape hatches

**Decision:** Unification stops where platform semantics become misleading.
The client therefore exposes explicit namespaces rather than arbitrary
pass-through hidden behind a generic operation:

```text
machine-control --target <logical-target> testbed -- <native arguments>
machine-control --target <logical-target> os -- <native arguments>
```

`testbed` invokes the authoritative platform/testbed CLI for lifecycle, image,
device, or recovery operations outside the portable subset. `os` invokes the
platform-owned guest administration route and reports its platform and
privilege. Before repository-consolidation cutover that implementation may be
in an external testbed; afterward it lives under the platform directory here.
PowerShell is not presented as Bash; UAC, TCC, Polkit, GDM, loginwindow, and
provider-specific operations remain explicit capabilities.

Outer screenshot or input commands are not reachable through ordinary
`desktop` fallback. They remain named testbed recovery operations and retain
the authoritative testbed's guard and authorization policy.

## Results and artifacts

**Decision:** The client validates the resident envelope before returning it
and adds a separate transport projection rather than rewriting provider truth.
Every result preserves operation, acceptance, route, generation, delivery,
effect, uncertainty, host interference, and typed error information.

The retained Windows seal predates the mandatory `hostInterference` result
field. Its adapter may add `none` only for that known target-native runtime and
must disclose `compatibilityProjection: ["hostInterference"]`. Newly published
Windows runtimes emit the field themselves. No other missing field or platform
receives this compatibility treatment.

Artifact retrieval is normalized around an opaque handle returned by the
adapter. A handle may project a Windows artifact identifier, a bounded macOS
guest path, or a Linux UUID, but callers do not receive a generic arbitrary
file-read primitive. The result reports the actual fetch route and local
output path.

## Conformance

The shared workflow runs through the same client on all three accepted
desktops:

1. inspect doctor and resident capabilities;
2. launch or reset a deterministic application fixture;
3. obtain a compact semantic snapshot and reference;
4. focus or enter Unicode text and press a semantic control;
5. confirm an independent application effect;
6. capture the relevant window and retrieve its artifact;
7. compare guest-local and outside status generations;
8. clean up the application and artifact; and
9. report request bytes, result bytes, latency, retries, and round trips.

Platform-specific setup and independent-effect readers remain testbed-owned
hooks. A provider acknowledgement is never the correctness oracle.

**Current:** The guarded live corpus passed on Windows, macOS, and Linux.
Every target reported outer UI prohibited, local and outside status agreed on
one resident generation, semantic presses produced independently observed
effects, and target-native captures were retrieved as valid PNG artifacts.
macOS and Linux also confirmed Unicode fixture effects. The Windows fixture
does not contain an editable field, so that shared cell reports the omission;
the deeper Windows corpus already covers Unicode input. See the
[minimized evidence](../docs/evidence/desktop-common-entry.md) and executable
[`live-desktop-conformance.sh`](../tests/client/live-desktop-conformance.sh).

## Remaining direction

**Current:** Windows adapters accept explicit private configuration
`WINVM_RESIDENT_PROFILE=user`, `WINVM_USER_INSTANCE`, and
`WINVM_USER_SESSION_ID` to select an installed workstation runtime. The same
selection governs control, local-control parity, and artifact retrieval.
Default selection remains the existing appliance. There is no fallback between
profiles when an endpoint is absent. See
[Tactical 036](../docs/tactical/036-windows-workstation-distribution.md) for
acceptance status.

- Add an authenticated remote carrier, SDK, or MCP projection only after the
  local contract stays stable under real application campaigns.
- Expand friendly normalization when repeated workflows demonstrate a common
  field or selector; retain `desktop raw` for honest provider-specific calls.
- Extend ChromeOS beyond its common readiness/maintenance projection only when
  measured desktop operations support honest shared capability and result
  semantics. Its complete native vocabulary remains available explicitly.
- Profile the remaining Windows provider/claim setup and the Linux
  administrative route when iteration latency justifies another bounded
  transport slice. Do not add persistent sessions merely to save the measured
  approximately 0.17-second Windows SSH handshake delta.

## Non-goals

- Do not collapse platform-specific VM/device bootstrap or lifecycle into one
  misleading generic implementation. Canonical source may live here while
  platform semantics remain separate. Never centralize private inventory here.
- Do not replace native resident providers or their security boundaries.
- Do not make a generic shell or arbitrary privileged command part of the
  desktop contract.
- Do not force unsupported operations to appear successful.
- Do not make the common client a prerequisite for direct testbed debugging.

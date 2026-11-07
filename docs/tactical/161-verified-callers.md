# 161 — Verified callers replace native delegation

Owning topics: [caller-authorization](../../topics/caller-authorization.md),
[access-admission-and-pause](../../topics/access-admission-and-pause.md).
Retires: [Tactical 086](086-native-desktop-delegation.md) and
[Tactical 087](087-prepared-console-delegation.md). Their last source
revisions are tagged `delegation-v1-final` here and `mc-delegation-v1-final` in
YepAnywhere.

Status: **active.**

## Objective

The operator never used the trusted YepAnywhere delegation path and asked to
remove it. It is a second, half-built transport that only restricted YA's own
agents: no renewal, no Browser, a lockstep 30-second relay. Any other
same-user process kept the full plain path.

Replace it with what the operator actually wants: an opt-in **Only verified
callers** mode on the ordinary resident socket. This is a picket fence against
drive-by use, comparable to Sky's peer-signing check. It must apply to every
caller, including the plain CLI, so there is no bypass.

## Operator decisions (2026-11-07)

- The mode is opt-in and off by default; current behavior is unchanged until
  it is enabled.
- An unapproved signed host app triggers a native "Allow callers from APP?"
  prompt on first use. Approvals are listed in Settings and can be removed.
- macOS first, with a common status and refusal contract. Windows
  (Authenticode plus parent chain) follows. Linux reports `unsupported`.

## Threat model and honest claim

The mode keeps MC from lending its Accessibility and Screen Recording access
to processes that were not launched from an approved app. Examples are a
stray background job, a script started by another app, or malware with no
approved ancestor.

It is **not** containment. Code that an approved agent or the operator runs,
and same-user code that tampers with an approved app's environment (shell
startup files, tools on `PATH`), still passes. Status and docs must state
this.

## Design (macOS)

1. **Peer:** read the kernel audit token of the socket peer. The peer must be
   one of Machine Control's own signed client executables, the bundled
   `macui` or the bundled Python. Check it against MC's designated
   requirement.
2. **Host:** walk the peer's ancestry for at most 12 hops, binding each
   process by PID and start time to prevent PID reuse. The nearest
   code-signed, non-platform app ancestor is the host. Admit only if that host
   matches an approved designated requirement (Team ID plus signing
   identifier). Intermediate processes such as shells or interpreters are not
   restricted.
3. **Detached processes:** reaching launchd without an approved host is
   `caller_not_verified`. Unsigned or ad-hoc hosts cannot be approved by
   signature, and the refusal says so.
4. **Scope:**
   - These stay open, so an agent can diagnose a refusal: `status`,
     `capabilities`, doctor projections, `browser.profiles` discovery.
   - Every other one-shot operation, and the `control.open` channel, is
     verified per connection.
5. **Prompt:** when an unapproved signed host connects, MC shows a native
   prompt naming the app and publisher, unless one is already pending for
   it. Choosing Allow stores its requirement. The refused request is never
   replayed; the agent retries.
6. **Status:** add `data.callerVerification`:
   - `mode`: `off` or `verified_only`;
   - `supported`;
   - `approvedHosts`: display name and publisher, never full requirements;
   - `limits`: `"same_user_not_contained"`.

   Refusals use `caller_not_verified` with
   `data.callerHost: {name, publisher, approvable}`.

## Ordered work

### 1 — remove native delegation

- **Machine Control:**
  - drop the `desktop.delegation.v1` feature advertisement first;
  - remove `DesktopCallerTrust.swift`, the delegation branches in
    `AdmissionChannel.swift`, `delegated-channel` and the trusted-proxy flag,
    and the `machost.py` proxy branch;
  - remove the trust status, Settings UI, and
    `contracts/desktop-delegation-v1.schema.json`;
  - remove the native-delegation tests and the instruction text.
- An open frame that still carries `desktopDelegation` refuses with
  `desktop_delegation_retired`, never as a plain owner. Leftover trust files
  are ignored.
- **YepAnywhere:** remove the Rust proxy, the provider delegation wiring and
  their tests. Released YA builds already fall back to the plain path when the
  feature is not advertised.

### 2 — verified callers on macOS

Implement the design with deterministic tests: requirement matching, ancestry
walk bounds, PID reuse, detached processes, unsigned hosts, the
discovery-only allowance and prompt debounce. Add the Settings toggle and
approved-host list, plus the status projection.

### 3 — document and verify

- Update `topics/caller-authorization.md`: retire the delegation decision,
  record verified callers and its limits, and keep the lessons below.
- Update the agent instructions so an agent explains `caller_not_verified` and
  asks the operator to approve the named app.
- Live on a macOS VM workspace:
  - with the mode off, behavior is unchanged;
  - with it on, a CLI under an approved host passes;
  - a detached `launchd` process is refused;
  - an unapproved signed host prompts, then passes after approval;
  - discovery still works when refused;
  - the conformance runner passes.

## Lessons kept from the delegation attempt

- Kernel audit-token plus code-signature checks soundly identify the
  immediate peer, and hardened runtime protects a signed host app.
- Ancestry proves only that the caller is in an app's process tree, not the
  intent behind the call. Agents run arbitrary children.
- A verification channel parallel to the plain path protects nothing.
  Verification belongs on the main path.
- A separate lockstep relay caused contract drift: no renewal, no Browser and
  a 30-second ceiling. Do not add a second transport for identity.

## Result

Pending.

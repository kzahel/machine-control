# Windows Desktop

Topic: `windows-desktop`

Status: public 0.5.4 preview published for x64 and ARM64. Signed ARM64 VM
indefinite-access, Pause/Resume, Stop and production-update acceptance passes.
Earlier x64 coverage remains; full ARM64 and physical acceptance remain open.

## Product and boundaries

**Decision:** Package the existing ordinary-user .NET resident with the shared
Tauri settings and tray application. Preserve the providers and named-pipe
contract. Supervise a self-contained companion; require neither a separately
installed .NET runtime nor the privileged appliance service.

**Decision:** The desktop resident starts with access off. Enforce scope,
timed or operator-selected until-stopped access, approval narrowing,
prompt-time input pause, Stop, expiry,
session/desktop transitions, and stale-reference invalidation in resident
dispatch. Approval uses a private operator channel, never the agent endpoint.
Preview grants apply to callers of the same user; this does not contain an
agent with an unrestricted same-user shell.

**Decision:** Preserve the headless workstation and protected appliance
profiles. YA now consumes the installed desktop CLI and has retired its
separately supervised component. The desktop app owns a distinct instance and
endpoint. It never installs or arms the protected service. Elevated apps, UAC,
lock/login, and other users remain outside its ordinary profile.

**Decision:** Reuse the concise Access, Permissions, Activity, and Settings UX.
Windows permissions report session/integrity availability rather than macOS
consent controls. Expose independently accepted desktop and browser scopes.

**Decision:** Signed ARM64/x64 candidates use the existing publisher signing
infrastructure and desktop updater key. Every publication requires meaningful
checked-in versioned notes. Exact signed installed acceptance precedes any
Windows support claim.

## Execution and remaining gates

**Current, unreleased source and fixtures:** ordinary desktop-product native
and browser dispatch requires a live owner session, even with an idle standing
grant. The common CLI negotiates short ownership or retains it with
`control stream`. [Tactical 095](../docs/tactical/095-windows-required-owner-session.md)
owns validation and the remaining installed-build acceptance gate.

**Current, public 0.5.4:** the native operator supports **Until I turn it
off**, with explicit `until_stopped` lifetime and null remaining seconds.
Dispatch and admission skip only the absent expiry; scopes, Stop, pause,
availability and update exclusion remain enforced. Public agent approvals
remain timed. Signed ARM64 installed acceptance proves visible selection, an
independent fixture effect, Pause/Resume, Stop and bounded agent approval.
Production 0.5.3 to 0.5.4 replacement also passes. [Tactical 091](../docs/tactical/091-desktop-until-stopped.md)
owns this focused acceptance and unified release. No new restart/reboot
persistence semantics are added.

**Current:** Public 0.5.3 x64 passes the installed Python CLI's ordinary-user
native approval, refusal, independent Cua counter effect, capture/artifact hash,
stale-reference and Stop slice, together with actual YA installation verification.
[Installed agent CLI](installed-agent-cli.md) owns that evidence, actual YA
native/browser model turns, exact live/reloaded media and close/restart/crash
isolation. Remaining provider/platform cells are listed there; the ARM64 desktop slice
in 091 does not establish those broader YA consumer cells.

**Current:** The exact signed 0.4.7 x64 candidate passes installed payload,
native grant, self-interface protection, tray, expiry, emergency Stop, startup,
restart, failure cleanup, and independent Cua fixture action/capture checks.
The signed browser-open 0.4.4 to 0.4.6 and 0.4.6 to 0.4.7 updates relaunch off,
invalidates the old generation, and preserves user applications.

**Current:** Local and explicitly selected outside common CLI callers reach the
same desktop runtime generation and native grant. Both pass independently
confirmed fixture effects, artifact hashes, and capture-superseded reference
refusal without replay. The existing ordinary-user component also passes
conformance using the final bundled runtime.

**Current:** Lock revokes access. The accepted appliance lacks the optional
existing-session unlock broker; recovery uses native logoff and canonical
stored-credential sign-in. This does not establish in-place unlock acceptance.
Interactive session selection must follow observed identity after re-logon.

[Tactical 053](../docs/tactical/053-windows-desktop.md) owns implementation and
acceptance. [Tactical 054](../docs/tactical/054-windows-browser-and-arm64.md)
extends that evidence to signed browser control and replacement. Earlier
engine/package evidence is in
[Tactical 036](../docs/tactical/036-windows-workstation-distribution.md);
[native distribution](native-distribution.md) owns shared release decisions.

**Open:** Broader ARM64 browser/lifecycle acceptance, physical hardware, and
in-place unlock integration. Focused ARM64 execution in 091 does not establish
those separate capabilities.

**Current:** Windows browser setup and browser/devtools scopes are implemented.
Source-native fixture effects and enforcement pass on x64. Upload and raw CDP
WebSockets are explicitly unavailable; the [browser dossier](../research/providers/chrome-extension.md)
owns route details.

[Tactical 054](../docs/tactical/054-windows-browser-and-arm64.md) owns browser
integration and the conditional ARM64 execution slice. Target availability and
architecture execution are observed separately.

**Current:** Exact signed 0.4.7 x64 browser fixture tasks and local/outside parity
pass. Signed 0.4.4 to 0.4.6 replacement passes with Chrome open, retaining
registration and startup while revoking access. The incoming installer pauses
only the owning manifest during replacement and restores its exact bytes;
startup also recovers interrupted maintenance. Actual sign-in starts 0.4.7 in
background with a fresh generation and access off. This repairs the earlier
0.4.4 to 0.4.5 native-host file-lock failure.

**Current:** Ordinary signed 0.4.7 uninstall removes payload, owned browser
registration and startup with Chrome connected, while Chrome and an independent
app survive. A held image causes bounded refusal with exact payload and startup
preserved; uninstall succeeds after release. The actor waits for the relocated
uninstaller's effects rather than treating its bootstrap exit as completion.

**Current:** Unified public `0.4.8` includes Mac and Windows packages under one
version, tag, required changelog and release script. Exact x64 installed UI,
browser, held-image refusal and ordinary uninstall pass. Production `0.4.7`
to `0.4.8` replacement passes with Chrome open, retaining startup/registration,
reconnecting, relaunching off and rejecting old references. ARM64 public packages
pass signing, provenance, payload and updater authentication; native execution
was not part of that earlier release record. [Tactical 055](../docs/tactical/055-unified-desktop-publication.md)
owns publication and its final available-VM evidence.

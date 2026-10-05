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
endpoint. Its ordinary profile excludes elevated apps, UAC, lock/login, and
other users. **Decision:** [Tactical 097](../docs/tactical/097-windows-desktop-uac.md)
adds an optional separately installed/armed desktop UAC helper. It must retain
native grants and live ownership and never inherit appliance authority.
The separately approved [bounded locked-use profile](../desktop/WINDOWS-LOCKED-USE.md)
adds existing-session password unlock and relock with a temporarily visible
console in its historical candidate. The current source uses a single-display
opaque cover; [Tactical 102](../docs/tactical/102-windows-covered-control.md)
owns that successor's qualification. Cold login and other users remain outside
this desktop integration.

**Decision:** Reuse the concise Access, Permissions, Activity, and Settings UX.
Windows permissions report session/integrity availability rather than macOS
consent controls. Expose independently accepted desktop and browser scopes.

**Decision:** Signed ARM64/x64 candidates use the existing publisher signing
infrastructure and desktop updater key. Every publication requires meaningful
checked-in versioned notes. Exact signed installed acceptance precedes any
Windows support claim.

## Execution and remaining gates

**Current, unreleased source and staged x64 evidence:** [Tactical 101](../docs/tactical/101-windows-desktop-locked-use.md)
binds the existing unlock broker to explicit native preparation and a finite
desktop task. A SYSTEM guardian owns relock independently of the resident and
service. Exact signed installed qualification for the accumulated Windows
changes remains pending authenticated release tooling. The successor in
[Tactical 102](../docs/tactical/102-windows-covered-control.md) proves opaque
one-display VM presentation with underlying native capture and injected
pointer/keyboard effects. It also fences unlock to locked-origin tasks and
proves that ordinary completion does not newly lock the console. Physical
takeover, broader Cua and signed-package qualification remain separate gates.

**Current, unreleased x64 development candidate:** per-tab CDP WebSockets use
the shared Chrome extension and a retained DevTools owner. Typed commands,
streamed events, payload-free audit, bounded transport and authority/provider
fences pass 28 focused VM checks with independent HTTP effects.
[Tactical 099](../docs/tactical/099-windows-streaming-cdp.md)
owns focused VM evidence; [the streaming guide](../desktop/WINDOWS-STREAMING-CDP.md)
owns usage, connection limits and outside forwarding. The candidate also
supports browser-root target discovery, tab lifecycle and flattened native
child sessions. [Tactical 100](../docs/tactical/100-browser-level-cdp.md) owns
real Playwright/Puppeteer qualification and the supported default-profile
subset. Signed/ARM64/physical qualification remains separate.

**Current, unreleased x64 development candidate:** browser-scoped file upload
passes 23 live checks through the real operator UI and Chrome for Testing in a
Windows-hosted VM. Both direct inputs and intercepted choosers have independent
server byte/hash effects. Typed target-local file validation, live ownership,
scope, stale-reference, Pause and Stop checks pass. [Tactical 098](../docs/tactical/098-windows-browser-upload.md)
owns the evidence and [the upload guide](../desktop/WINDOWS-BROWSER-UPLOAD.md)
owns usage and path restrictions. Signed release, ARM64 live, physical and other
browser qualification remain separate.

**Current, unreleased x64 development candidate:** the optional desktop UAC
helper passes 21 live checks in a Windows-hosted VirtualBox VM. The actual
operator UI installs/cancels/removes it; the desktop owner channel captures
secure consent, cancels/approves it, and controls an independently observed
elevated fixture counter. Untrusted caller, observe-only, credential, generic
secure-input, stale-reference, disconnect, Pause and Stop refusals pass, and
UAC policy is unchanged. The helper/service and test processes are removed
afterward. [Tactical 097](../docs/tactical/097-windows-desktop-uac.md) owns the
execution record; the [operator guide](../desktop/WINDOWS-UAC.md) owns setup,
per-run opt-in and version replacement. This is unsigned candidate evidence,
with x64/ARM64 builds; signed release, ARM64 live, physical and localized
prompt acceptance remain open. Existing-session unlock has its separate
qualification in Tactical 101; cold login is outside the desktop integration.

**Current, unreleased candidate acceptance:** ordinary desktop-product native
and browser dispatch requires a live owner session, even with an idle standing
grant. The common CLI negotiates short ownership or retains it with
`control stream`. [Tactical 095](../docs/tactical/095-windows-required-owner-session.md)
owns the implementation. [Tactical 096](../docs/tactical/096-windows-owner-session-acceptance.md)
proves the focused ARM64 native/browser workflow and owner lifecycle with a
staged runtime and the real operator UI. Full signed-package release and broader
lifecycle acceptance remain separate gates.

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
signed installed locked-use qualification. Focused ARM64 execution in 091 does
not establish those separate capabilities.

**Current:** Windows browser setup and browser/devtools scopes are implemented.
Source-native fixture effects and enforcement pass on x64. File uploads have
focused unreleased acceptance above; owner-bound CDP WebSockets are also
implemented in the unreleased candidate.
The [browser dossier](../research/providers/chrome-extension.md)
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

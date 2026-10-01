# Windows Desktop

Topic: `windows-desktop`

Status: signed x64 preview accepted on a dedicated VM. ARM64 native desktop
execution, physical hardware, and production publication remain open.

## Product and boundaries

**Decision:** Package the existing ordinary-user .NET resident with the shared
Tauri settings and tray application. Preserve the providers and named-pipe
contract. Supervise a self-contained companion; require neither a separately
installed .NET runtime nor the privileged appliance service.

**Decision:** The desktop resident starts with access off. Enforce scope,
bounded duration, approval narrowing, prompt-time input pause, Stop, expiry,
session/desktop transitions, and stale-reference invalidation in resident
dispatch. Approval uses a private operator channel, never the agent endpoint.
Preview grants apply to callers of the same user; this does not contain an
agent with an unrestricted same-user shell.

**Decision:** Preserve the explicitly selected YA workstation component and
protected appliance profiles. The desktop app owns a distinct instance and
endpoint. It never installs or arms the protected service. Elevated apps, UAC,
lock/login, and other users remain outside its ordinary profile.

**Decision:** Reuse the concise Access, Permissions, Activity, and Settings UX.
Windows permissions report session/integrity availability rather than macOS
consent controls. Initially expose supported desktop scopes; browser integration
has a separate acceptance gate.

**Decision:** Signed ARM64/x64 candidates use the existing publisher signing
infrastructure and desktop updater key. Every publication requires meaningful
checked-in versioned notes. Exact signed installed acceptance precedes any
Windows support claim.

## Execution and remaining gates

**Current:** The exact signed 0.4.3 x64 candidate passes installed payload,
native grant, self-interface protection, tray, expiry, emergency Stop, startup,
restart, failure cleanup, and independent Cua fixture action/capture checks.
The signed 0.4.2 to 0.4.3 update automatically relaunches with access off,
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
acceptance. Existing engine/package evidence is in
[Tactical 036](../docs/tactical/036-windows-workstation-distribution.md);
[native distribution](native-distribution.md) owns shared release decisions.

**Open:** ARM64 native UI/runtime execution, physical hardware, browser
integration, in-place unlock recovery, and production Windows feed publication.
ARM64 signing, installation, payload bytes, and updater authentication pass CI;
they do not establish ARM64 desktop execution.

[Tactical 054](../docs/tactical/054-windows-browser-and-arm64.md) owns the next
browser integration and ARM64 execution slice. Target availability and
architecture execution are observed separately.

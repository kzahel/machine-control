# Windows unattended unlock with explicit administrator arming

Status: in progress.

Owning topics: [Windows protected unlock](../../topics/windows-protected-unlock.md),
[native distribution](../../topics/native-distribution.md), and
[Windows resident control](../../topics/windows-resident-control.md).

## Objective

Add an optional signed privileged component for unlocking an existing Windows
console session. A human approves elevation and a concrete grant identifying
the Windows account, controller public key, and lifetime. Preserve the ordinary
workstation package and the existing dedicated-appliance service.

## Boundaries

The workstation user host never grants itself protected authority. The new
service has separate installation, pipe, state, and service identities and no
ordinary desktop, arbitrary SYSTEM command, registry, filesystem, or general
provider-dispatch API. The existing appliance broker is a test harness and
regression target, never the production authorization fallback.

An administrator-owned grant authorizes a controller key, not a public label,
transport name, agent session, or claim ID. Possession of a controller key by an
unrestricted same-user agent is outside the containment boundary. YepAnywhere
owns controller key/credential custody, user-facing integration, and supervision;
Machine Control owns the grant enforcement, installation, protocol, and Windows
provider. Windows credentials use a dedicated one-shot transport and are not
persisted in the target service, command arguments, JSON, logs, or captures.

This slice covers stock password/PIN providers for an already logged-in, locked
local console account with a unique local display-name mapping. Domain/cloud
account binding needs separate evidence. Cold login, account switching, biometric credentials, general
UAC approval delegation, and disabling Windows security policy are excluded.

## Ordered implementation

### 1 — define the grant and failure contract

Define administrator-owned grants bound to a Windows account SID and a P-256
controller public key. Support explicit expiry and revocation. Bind each unlock
attempt to a fresh service challenge, grant revision, service generation, and
console session/account. Reject malformed, missing, revoked, expired, replayed,
or mismatched authorization before reading a credential. Never retry an action
with failed or unknown effect.

### 2 — add the isolated unlock service and client

Use an independent service/pipe namespace and protected install/state ACLs.
Reuse native Credential Provider discovery and input behind a typed unlock
boundary. Preflight the exact locked console account and credential field before
requesting the secret. Recheck identity and grant before delivery; report input
delivery separately from independently observed WTS/desktop unlock. Clear secret
buffers and stop privileged helpers on cancellation or service shutdown.

Provide local and remote client carriers over the same challenge/response and
one-shot secret exchange. Controller signatures must be generated where the
private key is held; the remote target must not receive that key.

### 3 — implement elevation, consent and lifecycle

Ship a signed setup entry point that requests Windows elevation, verifies the
package, and installs into administrator-owned storage. Installation starts
unarmed. An elevated confirmation presents the exact account, controller key
fingerprint, and lifetime before creating a grant. UAC cancellation and consent
cancellation leave authority unchanged. Provide status, revoke, uninstall and
reviewable upgrade behavior; ordinary callers cannot modify grants or payloads.

### 4 — exercise the native Windows appliance

Use the common CLI, read-only doctor and an exclusive workspace claim. Run the
new service only in a disposable Windows workspace. The pre-existing appliance
may drive consent as an independent, already-authorized test harness; the new
service cannot approve its own arming. Prove cancellation, unarmed refusal,
approved arming, a real lock/unlock with independent OS evidence, wrong-key,
replay, expiry, revocation, and clean removal. Use declared credential locators,
submit once, and stop on unknown authentication outcomes.

Regression-test ordinary user control and the existing appliance broker.
Return the workspace to the appropriate power state and release it and its claim.
Keep concrete identities, credentials, grants, keys and evidence out of Git.

### 5 — sign and accept final artifacts

Extend the existing Windows CI package/sign/catalog/manifest pipeline. Run
portable checks, native checks, formatting and both architecture publishes.
Verify exact final signed artifacts and native execution, recording architectural
coverage honestly. Publish no release incidentally. Update the owning topics and
this execution record with observed results and remaining integration work.

## Completion conditions

- Ordinary installation remains unprivileged and cannot arm unlock.
- UAC and explicit elevated consent gate grant creation; cancellation is safe.
- Only the approved controller can request unlock of the selected locked account.
- Expiry, revocation, replay and stale-session checks refuse before credential use.
- Credentials never enter ordinary JSON/arguments or persistent service storage.
- A real native unlock has independently verified effect with no automatic retry.
- Signed installation, removal and existing runtime regressions pass in isolation.

## Execution record

Planning and implementation started after approval of the UAC-based arming flow.
The implementation has native setup, authorization and password-unlock evidence;
final distribution acceptance and cleanup are in progress.

Initial implementation adds a separate service, P-256 challenge proof,
SCM-authenticated local carrier, controller-side signing helper, and a native
bootstrap with an embedded setup script. Package copying occurs into protected
storage before catalog verification or managed execution. Explicit elevated
consent writes the exact displayed public grant; install remains unarmed.

The first read-only native inspection found a display-name account label. The
initial scope is therefore local accounts with a unique SAM mapping, with
field/process/focus and WTS SID/logon-session checks before credential delivery.
Credential replacement and submission use one native input batch; authority is
checked before that delivery boundary. Revocation does not undo an input batch
already submitted to Windows.

Validation so far: portable checks, x64/ARM64 runtime publishes, formatting,
Windows-native authorization/transport contracts and signed CI packaging passed.
[CI run 34691709993](https://github.com/kzahel/machine-control/actions/runs/34691709993)
also exercised signed x64 install, unarmed service status and uninstall. Its
packages and signed build identity were verified before VM execution.

Native testing found and corrected the bootstrap's elevation manifest, required
Windows environment values, and missing-grant status handling. Both disposable
architectures have passed UAC cancellation, signed installation and cancellation
of the elevated grant dialog. The x64 unarmed protocol refusal and ordinary
workstation conformance also passed. Both architectures subsequently passed
arming, ordinary DACL/write/service-stop denial, wrong transport identity,
wrong controller key and proof replay rejection without credential reads.

Credential-free readiness probes then exposed the existing-session LockApp
curtain on Default with WTS locked. The first Winlogon-only worker refused
before asking for a credential. A separate, bounded preparation worker and
unlock-only UIAccess token are being validated. No password has been submitted
through the new component yet; real unlock, expiry and revocation remain pending.

The consent fixture is independent test-appliance administration: it observes
the exact elevated dialog and uses a temporary, bounded elevated Win32 task to
activate its observed button. It verifies dialog closure and the resulting grant
or absence. This fixture is never shipped as part of the unlock authority API.
An earlier ARM64 fixture left a dialog open during removal; the interrupted
preview installation was cleaned up before reinstalling the verified package.

Signed build 932c565 (CI run 34693197736) passed native credential-free
readiness and one real password unlock on both ARM64 and x64. Each result
confirmed delivery, return to Default, and the same WTS account/logon session.
The x64 controller initially rejected a two-hour guest clock skew before
signing or opening the credential source; a credential-free probe reproduced
that exact validation failure. Correcting only the disposable guest clock and
renewing the service generation restored valid challenge deadlines. The first
actual x64 password submission then succeeded.

The locked workspaces received an explicit administrator development replacement
with the verified signed package and their previously approved public grants.
Final installer acceptance will repeat the normal uninstall/install/re-arm flow.
ARM64 ordinary workstation conformance and revoke/refusal passed after unlock.

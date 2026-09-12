# Windows unattended unlock with explicit administrator arming

Status: complete.

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

The accepted slice covers stock password unlock for an already logged-in,
locked local console account with a unique local display-name mapping. The
protocol includes PIN selection; native PIN acceptance and domain/cloud account
binding need separate evidence. Cold login, account switching, biometric
credentials, general UAC approval delegation, and disabling Windows security
policy are excluded.

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

The implementation adds a separate service, P-256 challenge proof,
SCM-authenticated carrier, controller-side signing helper, and signed native
setup with an embedded installation script. Payload verification happens in
administrator-owned storage before managed execution. Installation starts
unarmed; elevated consent approves the exact public grant.

Native inspection found that the credential provider exposes an account display
name rather than a SID. The accepted scope is therefore a unique local SAM
mapping, with field/process/focus checks and the same WTS SID and authentication
LUID verified around delivery. Credential replacement and submission use one
native input batch. Revocation cannot undo a batch already submitted to Windows.

Native testing corrected the bootstrap elevation manifest, required Windows
environment values, missing-grant status, and retryable removal. The independent
appliance consent fixture observes UAC and the elevated grant dialog, activates
its exact button, verifies the resulting grant or absence, and removes its
bounded scheduled task. That fixture is never part of the product authority API.

Two stock lock-screen states needed explicit preparation: a foreground LockApp
curtain on Default, and an idle locked Default desktop with no foreground window.
An unlock-only UIAccess worker dismisses the verified stock curtain. The idle
case first receives one zero-delta mouse activity event, without a click,
keystroke or pointer movement. A fresh Winlogon worker then discovers the
credential field. Empty discovery refuses without the appliance's legacy Enter
fallback. Ordinary host and appliance privilege defaults are unchanged.

Credential-free probes reproduced preparation refusals; an isolated x64
diagnostic build located them before any credential read or forwarding. The
signed wake fix subsequently passed fresh lock/unlock after normal installation
on both architectures. One ARM64 field-focus refusal also occurred before the
credential request; fresh discovery succeeded. These are fail-closed preflight
outcomes, not permission to replay a failed or uncertain authentication.

An x64 challenge initially failed because the disposable guest clock was two
hours ahead. The controller refused before signing or opening the credential
source; a credential-free probe reproduced the deadline mismatch. Correcting
the guest clock restored valid challenges. Controller errors and service faults
now report bounded phases and credential custody without exception messages,
credential contents or deployment paths.

## Acceptance

Final signed source
`046a79804676f6d4dfa8441106f9911a96756a0a`, workflow attempt
[`34696329747.1`](https://github.com/kzahel/machine-control/actions/runs/34696329747),
passed the normal revoke/uninstall/install/re-arm flow, ordinary workstation
conformance, and a fresh password unlock on native ARM64 and x64. Every accepted
unlock confirmed delivery, return to Default and the same WTS account/logon
session. Outside controllers used the authenticated target carrier; private
controller keys remained outside Windows.

| Surface | Evidence |
| --- | --- |
| UAC cancellation, unarmed install, elevated consent cancellation and approval | Native ARM64 and x64 |
| Ordinary DACL changes, payload/grant writes and service stop | Denied on both native architectures |
| Wrong transport SID, wrong controller key and proof replay | Refused before credential reads on both native architectures |
| Expiry and revocation | Expiry refused on ARM64; revoke/refusal passed on both |
| Challenge binding and one-shot framing | Native Windows contracts, including stale deadlines, revisions, account/provider/instance mismatch and no read-ahead |
| Forged payload plus forged plain hash inventory | Both signed native installers refused and removed partial state |
| Ordinary user desktop alongside armed unlock | Both native architectures, final signed bytes |
| Existing appliance shell, providers and protected UAC | Native x64, signed 0640c46 |

The appliance shell test first missed the Start-menu effect; after resetting
that menu state, the complete shell, provider and UAC suites passed. As in
tactical 036, fixed-delay shell assertions remain timing-sensitive.

Native Windows contracts, formatting, both architecture
publishes and portable checks passed. The manifest signature, exact source/run
identity and both archive hashes were verified before execution. One earlier
dispatch selected the preceding branch head; exact build-identity verification
rejected those archives before VM use.

Both final installers passed UAC revoke and removal, with instance services,
grants and test tasks absent. ARM64 returned to its original off state and its
workspace/claim were released. The x64 guest needed its restored appliance
service stopped and a fresh target-native immediate shutdown after a stalled
pending shutdown; the guest then reported off. Both disposable workspaces were discarded, both source targets were verified
off, and both claims were available again. Temporary controller keys and
inventory copies were removed; declared credential sources were retained.

No release has been published; CI artifacts remain temporary preview packages
rather than a consumer update feed.

## Remaining product work

YepAnywhere's download/enable UI, supervision and controller key/credential
custody remain a consumer integration slice. Native password acceptance covers
the tested Windows local-console profiles. PIN submission, domain/cloud account
binding, other Windows builds, physical hardware and broader session-transition
stress need separate evidence. Cold login, account switching, biometric login
and general UAC delegation are outside this component's contract.

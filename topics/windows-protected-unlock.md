# Windows protected unlock

Topic: `windows-protected-unlock`

Status: existing controller/password protocol has bounded native evidence;
password-free authorization is the preferred research direction. No owned
Windows password-free unlock has been built or live-tested.

## Password-free direction

**Decision (2026-10-18):** Prefer an explicitly authorized unlock mechanism
that does not ask for, retain or recover the user's Windows password. The
unreleased encrypted-password enrollment remains an implemented experiment,
not the selected final solution to Mac-like password-free setup. Do not promote
it as satisfying this requirement. Browser-only locked access stays independent.

The [platform comparison](../research/platforms/windows.md#password-free-authentication-extensions)
finds a documented candidate: a custom credential provider paired with an LSA
authentication package. The provider submits a bounded proof; the package
authorizes it without validating/replaying the account password. A
[source-reviewed sample](../research/providers/reverse-password.md) illustrates
that separation, but has an insecure authorization check and no acceptable
protected-LSA deployment evidence. Earlier session-reconnect failures do not
rule this route out. Hello, trusted signals, smart cards and commercial local
authentication products have different presence/account/secret requirements.

**Proposal:** Bind setup to the independently discovered current local account
after administrator consent, without reading its password. The broker issues
an authenticated, one-use, short-lived grant for the existing console's exact
SID, session/logon, runtime/helper generation and finite approved task. The
authentication package verifies that grant; the existing guardian owns cover
and failure relock. No password, password hash or PIN is retained or transported.
Any new authorization key serves only this scoped grant protocol and is
independent of Windows account credentials. Key custody and the minimal LSASS
protocol still need design; never infer authority from a public owner
label, PID, file marker or credential-provider UI alone.

This introduces an alternate unlock authority. Removing password custody does
not contain an administrator or compromised broker that can exercise that
authority. The improvement is avoiding disclosure/reuse of the account's
password, not making privileged compromise harmless.

**Open, next gates:** Confirm Microsoft LSA signing eligibility without disabling
PPL, then prove a minimal existing-session unlock on a disposable, recoverable
appliance. Preserve stock providers and qualify PPL, Credential Guard, Secure
Boot, account restrictions and ARM64/x64 separately. Verify same-session effect,
application/DPAPI continuity, owner/Stop relock, replay/expiry/revocation and
removal/reboot. Refuse cold login, account switching, UAC/CredUI and other users
even where Windows supplies the combined `CPUS_LOGON` scenario. A successful
token creation or fresh sign-in does not complete that gate. This research
installs no extension and changes no runtime behavior.

## Simple desktop setup

**Decision:** The desktop experience should install/approve its helper through
native setup and show ready/enabled state without asking people to generate or
browse for controller JSON. Keep the advanced outside-controller protocol as a
separate workflow. Browser-only access remains independent and leaves Windows
locked, without a helper or cover. Cold login means a new sign-in after boot or
sign-out; it is outside existing-session desktop unlock.

**Current, unreleased source (2026-10-17):** Desktop setup installs/updates the
helper and uses native Windows CredUI to enroll the exact current local console
account's password once. Successful setup enables covered desktop use; that
preference persists independently of ordinary access consent. Native update and
removal actions replace/erase enrollment. [Tactical 134](../docs/tactical/134-windows-native-unlock-enrollment.md)
owns implementation and native qualification; [Tactical 133](../docs/tactical/133-windows-unlock-usability-investigation.md)
retains the earlier reconnect investigation and installed 0.6.8 timeout.

The service authenticates the installed elevated setup peer and unlocked console
before accepting a dedicated binary frame, validates the password once and
protects it using SYSTEM-user DPAPI plus a SYSTEM/admin-only file. Public policy
binds the exact local account and a fresh revision; it contains no credential.
There is no credential export or generic decryption operation. Cancellation does
not change existing enrollment. Standard users elevating with another admin
still enroll the independently discovered console account.

`session.unlock` requires the actual installed Medium resident, ordinary access
approval and a finite locked-origin owner. It reuses stock credential-provider
discovery, the independent cover/relock guardian and fresh session/logon checks.
It decrypts only after exact field readiness, submits once, erases transient
buffers and never retries failed/unknown delivery. Such credential use
invalidates enrollment; a fresh task cannot replay it. Password changes require
explicit native repair. Removal erases enrollment and fences pending work.
Ordinary JSON, arguments, environment, logs and agent requests carry no password.
The separate external controller mode retains its signature and one-shot secret
requirements. Neither mode implements PIN, cloud/domain accounts, other users
or cold login in this desktop profile.

The [platform report](../research/platforms/windows.md#password-free-session-reconnect-investigation)
rejects only the tested reconnect shortcuts on one Windows build; this is not
proof that all password-free Windows authentication extensions are impossible.

## Existing controller protocol

Add unattended unlock as a separately installed and explicitly armed component.
The ordinary workstation host remains Medium integrity. The dedicated appliance
broker retains its existing contract; its broad appliance authority is not the
personal-workstation grant boundary.

The setup flow requests UAC elevation and then confirms a concrete Windows
account, controller public key and grant lifetime. Installation alone leaves
the new service unarmed. The service protects grant state from ordinary callers,
requires fresh proof of controller-key possession, and checks the exact locked
console session before accepting a one-shot Windows credential. It does not
persist that credential or weaken UAC, lockout, password or Windows Hello policy.

Controller key custody is distinct from target account selection. Same-user
shell access to a controller key defeats separation from that controller; use
an outside controller or a separate OS identity when stronger separation is
required. YepAnywhere owns its integration and credential/key custody, while
Machine Control owns the native protocol and enforcement.

## Current

**Current, unreleased:** the desktop's optional UAC payload
also hosts an independently armed `desktop` unlock instance. Native opt-in,
observation/control consent and a prepared owner session are all required.
The advanced controller supplies a password once after exact field readiness;
the native enrolled mode uses its protected service copy. A separately launched SYSTEM guardian binds relock to the
same account/logon session and fences owner loss, authority changes, deadlines
and failure. The current single-display profile places an opaque cover before
possible credential submission; only a locked-origin task can prepare unlock
and acquire relock authority. Ordinary completion never newly locks the
console. See [Tactical 102](../docs/tactical/102-windows-covered-control.md),
[Tactical 101](../docs/tactical/101-windows-desktop-locked-use.md) and the
[operator guide](../desktop/WINDOWS-LOCKED-USE.md) for qualification and limits.

**Current, focused x64 VM evidence:** activity admission now composes guardian
takeover with consent retention and fresh ownership after locked quiet.
[Tactical 103](../docs/tactical/103-windows-activity-pause.md) distinguishes
virtual-keyboard diagnostics from physical hardware, owner-unlocked local-use
and signed installed qualification. Credential delivery remains a separate
one-shot operation; becoming eligible never replays an unlock request.

The existing appliance provides protected desktop control and guarded no-user
login. Its login command refuses a locked session with an already logged-in
user. The signed workstation preview provides ordinary unlocked desktop control
and explicitly refuses protected operations.

The initial optional implementation targets existing local console accounts
with a uniquely resolved local display name and stock credential fields. Domain
and cloud account binding, ambiguous names and account switching need separate
evidence. The default proposal remains armed until revoked; explicit expiry is
supported. [The distribution guide](../release/windows-unlock.md) describes the
setup and protocol. Both architectures have passed native setup/arming,
ordinary access denial, caller/key/replay refusal, revocation and a real password
unlock with the same WTS account/logon session independently confirmed. Grant
expiry has also refused before credential use on ARM64. The authorized unlock
helpers use UIAccess to prepare the stock LockApp curtain and reach Winlogon;
ordinary host privileges remain unchanged. PIN submission has not been accepted
on a native target.

[Tactical 037](../docs/tactical/037-windows-unlock-arming.md) owns implementation
and acceptance of the new grant, installation and existing-session unlock flow.

# Windows protected unlock

Topic: `windows-protected-unlock`

Status: implementation in progress; no personal-workstation arming flow accepted.

## Decision

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
ordinary access denial and caller/key/replay refusal. Full unlock acceptance is
pending the LockApp-to-Winlogon transition. Only the authorized unlock helpers
receive the proposed UIAccess token; ordinary host privileges remain unchanged.

[Tactical 037](../docs/tactical/037-windows-unlock-arming.md) owns implementation
and acceptance of the new grant, installation and existing-session unlock flow.

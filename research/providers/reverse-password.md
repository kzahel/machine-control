# ReversePassword authentication samples

**Current (2026-10-18), `source-reviewed`:**
[ReversePassword](https://github.com/forderud/ReversePassword) includes a Windows
credential provider, a `NoPasswordAuthPkg` LSA authentication package and test
clients. Its relevant source illustrates authentication without validating or
retrieving the Windows password. It is not a qualified unlock provider.
The [spike audit](../../../machine-control-spike/docs/windows-passwordless-authentication.md)
owns the exact revision, source paths and investigation limits.

## License and architecture

The repository declares [MIT](https://github.com/forderud/ReversePassword/blob/master/LICENSE).
The authentication-package README acknowledges EIDAuthentication ancestry;
complete lineage and narrower inherited obligations have not been audited.
No code has been adopted or redistributed. Any reuse requires that audit and
a fresh review at the intended revision.

The credential provider selects the installed custom package and serializes
credentials to it. Inside LSA, the sample checks for a removable-media marker
file instead of checking the account password. It constructs token/profile
information and a new LSA logon session. This separates a sign-in UI extension
from the component that actually authorizes authentication.

## Reach and limits

| Capability | Evidence and limit |
| --- | --- |
| Non-password local authentication logic | `source-reviewed`; marker-file authorization, not a cryptographic grant |
| Credential-provider submission to custom package | `source-reviewed`; selected package is carried in serialization |
| Existing-session unlock | Unverified; the package allows Interactive/RemoteInteractive, rejects other logon types and creates a new LSA logon LUID |
| Same session, account, DPAPI and application continuity | Unverified; a successful standalone token/logon would not establish this |
| Current Windows x64 | Project configurations found; not built or live-tested here |
| ARM64 | No reviewed build configuration or acceptance |
| Protected LSASS | README requires LSA protection off; no acceptable product deployment evidence |
| Semantic control, capture and input | Not implemented; would compose with the resident and independent cover/relock guardian |

The marker file authorizes too broadly, input handling is not a hostile-buffer
reference, and profile/account-policy behavior is incomplete. Do not install
the sample or inherit its authorization model. Microsoft-signed LSA loading,
Credential Guard compatibility and safe rollback are separate gaps.

## Fit and next evidence

**Decision:** retain the source as an architecture reference for the deferred
Windows password-free investigation, with no adoption decision. An owned package
would need to consume a cryptographically authenticated, one-use grant for one already
logged-in account/session and refuse every other context. It must preserve stock
sign-in options, account restrictions, ordinary consent, finite ownership and
independent relock.

**Open:** Does a minimal, correctly signed package actually unlock the existing
password-created console session, without account-secret material, and retain
its original WTS identity/logon plus DPAPI functionality? That native effect
and Microsoft signing eligibility are the first gates. The
[Windows platform comparison](../platforms/windows.md#password-free-authentication-extensions)
owns alternatives; the [protected-unlock topic](../../topics/windows-protected-unlock.md)
owns the resulting direction.

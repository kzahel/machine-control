# 134 — Native Windows unlock enrollment

Owning topics: [Windows protected unlock](../../topics/windows-protected-unlock.md),
[Windows desktop](../../topics/windows-desktop.md).

Status: source implementation complete; end-to-end native acceptance incomplete.

## Objective and completion conditions

Replace the desktop setup file picker with one native setup action that installs
its helper, confirms the current local console account and enrolls that account's
password once. Approved, finite tasks that start locked can then request
`session.unlock` without sending a password or controller key. Preserve the
existing cover, independent relock guardian and owner/consent boundary.
Keep browser-only access independent with Windows left locked.

Completion requires cancellation and account binding, protected storage and
ordinary access refusal, no secret before field readiness, one-shot delivery,
revocation/repair, real same-logon unlock and owner-loss relock. Run native
contracts, format verification and ARM64/x64 publishes. Qualify installed UI
separately; source-native evidence does not establish signed package behavior.

## Boundaries and ordered work

### 1 — native account enrollment

Elevate the installed setup component, discover the exact unlocked local console
account in the service and prompt through native Windows CredUI. Use a bounded
binary credential frame only after peer and account discovery. Validate the
password once with Windows; never retry automatically. Bind SYSTEM-user DPAPI
ciphertext to the account and a fresh protected grant revision. Give only
SYSTEM/admin file access and expose no export/decryption operation.

### 2 — task-owned automatic unlock

Accept enrolled unlock only from the actual installed Medium resident with its
live finite locked-origin owner. Retain fresh stock provider/field discovery
before decrypting, exact account/logon/session checks and the independent
cover/relock guardian. Failed or unknown credential use invalidates enrollment;
rotation/removal fences pending work. Preserve the separate advanced controller
protocol without permitting enrollment metadata to bypass its proof boundary.

### 3 — setup and lifecycle acceptance

Use the Windows appliance through common CLI doctor, exclusive claim, journal
and supported credential transport. Verify native cancellation, enrollment,
unowned/relay refusals, real effect and relock. Keep credentials and raw evidence
private. Restore task-owned helper/setup state and original power state.

## Validation and final result

**Current, native ARM64 source evidence:** Native CredUI cancellation returned
1223 without creating a policy or vault; enrollment returned zero with both
protected files present. Upgrading the helper and cancelling the new prompt
preserved both file hashes. A Medium actor could not read the ciphertext.
Setup created no ordinary access grant. Unowned unlock, ordinary JSON credential
transport and unlocked-origin automatic unlock were refused; ordinary owner
completion left the console unlocked.

Full lifecycle acceptance is still pending. Earlier attempts failed before
credential dispatch: an initial control handshake timed out, and a separate
attempt lost desktop-only consent because the independent browser preference
was enabled. The latter coupling now has a focused regression and is fixed
without relaxing browser identity checks. Another native stack showed repeated
.NET process-info lookup of the resident's own session under the activity and
admission lock. The source now caches Windows' direct current-process session
ID, independently compared with OS process metadata in native contracts. This
is not a claim that all transport timing failures are resolved.

**Current, build/contract evidence:** Portable checks, frontend type checking
and build, Rust formatting, native Windows desktop/unlock contracts and full
runtime formatting pass. ARM64 and x64 runtime publishes pass. A native ARM64
Tauri development build also passes; it declares dirty source and is not a
signed release package. The focused WebView actor is
`tests/windows/desktop-enrollment-ui.ps1`; it delegates password entry to the
separate native credential fixture and never grants agent access itself.

The appliance's separate no-user login route intermittently failed helper
readiness after sign-out. Unknown attempts were not replayed. A clean reboot
restored a canonical login once. After a later clean reboot, neither SSH nor
the guest-agent file channel returned within the full boot window. Bounded
maintenance repair produced no attested report, and normal shutdown timed out
with the provider still independently reporting Running. Recovery is awaiting
explicit power-cut authorization; no outer UI was used and no unknown credential
submission was replayed. The original appliance runtime has a hash-verified
protected backup for restoration after temporary source diagnostics. The
remaining acceptance work is
actual UI setup/automatic enablement, same-logon enrolled unlock and owner/Stop
relock, native removal, restoration and original-off power cleanup.

Signed installed qualification, physical takeover, other users, cold login,
PIN/cloud/domain accounts and multiple displays have no new acceptance claim.
The independent browser-only behavior remains covered by Tactical 131 and the
source-native results retained in Tactical 133.

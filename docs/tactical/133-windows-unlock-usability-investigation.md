# 133 — Windows unlock usability and installed browser investigation

Owning topics: [Windows protected unlock](../../topics/windows-protected-unlock.md),
[browser control](../../topics/browser-control.md),
[Windows desktop](../../topics/windows-desktop.md).

Status: bounded investigation complete; simplified automatic unlock and signed
installed locked-browser acceptance remain unfinished.

## Objective and completion conditions

The operator found the Windows locked-use setup misleading: a generic setup
button opened a public JSON approval picker, while the feature still required a
controller to supply a password per task. Investigate a Mac-like setup and
independent browser access with Windows left locked. Record native route/effect
evidence, clarify the existing UI, and identify the next implementation gate.
Do not present controller-key setup as password-free unlock.

## Boundaries and ordered work

### 1 — investigate existing-session reconnect

Run a narrowly bounded [native probe](../../tests/windows/session-reconnect-probe.ps1)
on an exclusively claimed Windows 11 ARM64 appliance. Require an already locked
active console; use the same source/destination session, no password, and an
independent WTS lock observation plus authentication LUID before/after. Do not
install an authentication package or change Windows authentication policy.

### 2 — exercise the installed browser option

Authenticate the public desktop 0.6.8 ARM64 package and its installed payload.
Extend [the actor](../../tests/windows/browser-locked-live.py) to use actual
Settings and native approval, retain source-native operation, and expose Stop,
disable and expiry end scenarios. Keep browser profiles, target identity,
raw evidence and journals private. Preserve registrations/preferences and reap
owned application/browser descendants.

### 3 — clarify setup and choose the next direction

Name the existing Windows setup **Import controller approval…**, explain its
public JSON and per-task credential requirement, distinguish covered desktop
use from browser-only access, and explain the unavailable cold-login scope.
Record a concrete native enrollment proposal in the owning topic. Do not claim
that changing a label implements automatic unlock.

## Validation and result

**Current, native negative evidence:** LocalSystem and the same interactive
user both received error 7045 from empty-password `WTSConnectSessionW` on the
same locked console. Stock LocalSystem `tscon SESSION /dest:console` exited 1.
Independent observations retained the same session/logon and stayed locked.
These bounded results reject those routes on this build, not every possible
Windows password-free authentication extension. The platform report owns the
API documentation and comparison.

**Current, authenticated package but incomplete installed acceptance:** public
0.6.8 signatures, receipt/version/provenance and all 2,397 installed payload
files verified. Actual Settings preference and browser setup were exercised,
but the companion supervisor timed out before a browser grant or OS lock.
A separate startup trial failed before resident readiness. Managed stack
captures did not establish a deadlock. A direct process-to-session lookup
experiment did not resolve the failure and was reverted; it is not a product
fix. Signed installed lock/unlock, Stop, expiry and browser-root streaming
remain unqualified.

**Current, source-native regression only:** a local ARM64 candidate with that
lookup experiment passed 20 actor checks using x64-emulated Chrome for Testing
155 with software rendering. Independent HTTP click/Unicode effects, tab PNG,
per-tab streamed DevTools, real native approval, mixed scopes, desktop/new
approval refusals, Pause/Resume and disable passed with WTS still locked.
Desktop unlock remained disabled and its approval readiness unchanged. This
candidate is distinct from both the public signed payload and final source;
[Tactical 131](131-windows-linux-browser-while-locked.md) retains final-source
baseline evidence.

Shared TypeScript, Python syntax, portable checks and Windows platform smoke
checks pass. Native static checking encountered pre-existing formatting in
`BrowserInstaller.cs`; no unrelated formatting or speculative runtime change
is included. Disposable workspace acquisition refused its storage reserve,
so tests used the claimed persistent appliance without installing an
authentication extension. Exact failures and direct-script coverage remain
in private usage/provisioning journals.

The next slice is native one-time credential enrollment and automatic bounded
existing-session unlock. The installed companion timeout remains a separate
required qualification gate; neither is completed by this investigation.

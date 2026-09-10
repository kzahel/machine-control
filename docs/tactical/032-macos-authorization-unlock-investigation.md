# macOS authorization unlock investigation

Status: complete (bounded investigation; production integration remains open).

Follow-up: [Tactical 033](033-macos-sip-authorization-unlock.md) subsequently
proved the same plug-in on a SIP-enabled guest. The limits below describe
this initial SIP-disabled run.

Owning topic: [macos-resident-control](../../topics/macos-resident-control.md).

## Objective and completion conditions

Investigate an owned authorization plug-in that lets an explicitly armed
resident request unlock of an already logged-in, screen-locked disposable
macOS VM. Prove the actual desktop transition and subsequent fixture effect,
not merely a successful authorization API call. Record refusal, expiry,
single-use, ordinary password fallback, removal, and environment limitations.

The user explicitly deferred screen covering and protection of local use while
unlocked. A successful operation exposes the normal desktop. Preboot, fresh
login, physical-host installation, and a production personal-Mac deployment
are outside this investigation.

## Ordered work

### 1 — isolate the guest

Prove the configured source ready, shut it down, and acquire an isolated
copy-on-write workspace and its claim. Retain the dummy account credential in
private manifest storage. Keep outer UI prohibited. Record inherited SIP
posture without changing it or entering recovery.

### 2 — prove the authorization mechanism

Build an original minimal Apple authorization plug-in in the guest. First test
it behind a dedicated experimental right, then integrate an explicit branch
into screen-unlock authorization while preserving the saved stock rule.
Use an expiring, single-use, root-owned grant bound to the current console
session; do not claim containment against the appliance's sudo-capable user.
A protected broker for less-trusted profiles is future work.

### 3 — prove desktop unlock and refusal

Observe OS lock state independently. Exercise absent/expired/consumed grants,
explicit arming, actual unlock, and subsequent resident UI effects. Determine
how the normal loginwindow flow invokes the custom mechanism. Keep API
acceptance, authorization outcome, lock transition, and app effect separate.

### 4 — remove and restore

Restore the saved authorization rule, remove the experimental right, plug-in,
and grant state, and prove ordinary password unlock still works. Discard the
workspace using its matching claim. Restore the source's parked state.

## Validation

Use the guest compiler and plugin callback probes, stock `security` APIs,
independent OS session observation, and the existing AppKit fixture oracle.
Keep raw captures, authentication policy exports, and concrete VM identity
outside Git. Promote no SIP-enabled or physical-Mac claim from a SIP-disabled
appliance result.

## Result

**Current (2026-09-10):** Feasibility proved on a disposable copy-on-write Tart
workspace running macOS 26.6.2 (25G83). The inherited guest had SIP disabled.
An original Objective-C plug-in built against Apple SDK interfaces and loaded
in the privileged authorization host using an ad-hoc signature. No Codex
implementation was copied, installed, or invoked in the guest.

The [retained source and reproduction notes](../../platforms/macos/experiments/authorization-unlock/README.md)
describe the fixed experimental right, root-owned grant, and stock-policy
composition. A short-lived grant records console user, session UUID, boot
epoch, purpose, and monotonic issue/expiry times. The plug-in checks the
currently locked session and consumes the grant before approving. No account
password is read or typed by that path.

| Check | Result |
| --- | --- |
| Unprivileged arming | Refused with no grant created |
| Missing grant | Authorization denied (`-60005`) |
| Expired grant | Authorization denied and grant consumed |
| Wrong console-session UUID | Authorization denied and grant consumed |
| Valid grant, direct experimental-right evaluation | Authorized (`0`), but the desktop stayed locked |
| Reuse after successful evaluation | Denied |
| Integrated grant plus empty Return at loginwindow | Desktop unlocked without password entry; repeated successfully |
| UI effect after first unlock | Outside native AX call incremented the independent fixture counter to 1 |
| UI effect after repeated unlock | Guest-local AX call incremented the same fixture counter to 2 |
| Unarmed integrated attempt | Stayed locked; normal password fallback succeeded |
| Expired integrated attempt | Stayed locked; normal password fallback succeeded |
| Removal | Original authorization policy restored and verified, experimental right and bundle removed |
| Stock behavior after removal | Empty Return stayed locked; normal password unlock succeeded and fixture semantics returned |

The integrated screen-unlock rule used an explicit one-of-two branch:
the experimental right first, then the original `use-login-window-ui` rule.
The mechanism's `allow` decision enabled the actual loginwindow flow to
complete, unlike an isolated `AuthorizationCopyRights` success. The OS lock
signal, visible desktop capture, and fixture file oracle provided independent
effect evidence. The resident process/generation survived the cycles. Outer
UI remained prohibited throughout.

The first removal probe exposed an important helper issue: evaluating a
deleted right can reach generic administrator authorization. That probe was
terminated without supplying a credential. The retained helper now checks the
right's exact class/mechanism before evaluation and returns
`experiment_right_unavailable` after removal. The final sources built in the
guest with warnings treated as errors; that refusal and unprivileged arming
were rechecked with the final helper.

The original source VM's authorization policy was never changed. The
disposable workspace was normally shut down and discarded through its claim,
and the source was returned to suspension. Private manifest storage retains
the dummy credential and marks the clone disposed; concrete identities,
grants, policy exports, and captures are excluded from this record.

Returning the source to its parked state exposed a lifecycle observation gap:
startup readiness timed out, and the suspend response initially still reported
`running`. A subsequent independent power observation confirmed `suspended`.
No source authorization or resident changes were made to address that startup
delay; guest readiness after its next resume remains to be checked.

### Limits and next direction

This result is `live-tested`, not full protected-provider conformance.
SIP-enabled loading/signing and physical-Mac behavior were not established.
The grant authorizes the next eligible evaluation for the current locked
session; it is not bound to an authenticated named agent and can be consumed
by another eligible request first. The root-armed appliance prototype makes
no containment claim against a sudo-capable agent. A typed protected broker
and common-facade integration remain future implementation work.

There is deliberately no screen covering, local-input protection, or automatic
relock. Grant expiry limits authorization eligibility, not unlocked-session
duration. The independent resident lock-state and global-input-targeting
defects from the earlier investigation also remain to be fixed. No fresh-login
or preboot experiment was performed.

Apple's [authorization plug-in documentation](https://developer.apple.com/documentation/security/extending-authorization-services-with-plug-ins)
and the installed SDK's `AuthorizationPlugin.h` supplied the interface
contract. The original callback implementation and grant logic live in this
repository under its MIT terms.

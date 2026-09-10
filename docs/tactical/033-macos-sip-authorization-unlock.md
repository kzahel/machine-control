# SIP-enabled macOS authorization unlock

Status: complete (bounded SIP-enabled guest investigation).

Owning topic: [macos-resident-control](../../topics/macos-resident-control.md).

## Objective

Repeat the [owned authorization experiment](032-macos-authorization-unlock-investigation.md)
on a disposable guest with independently verified SIP enabled. The user
requested this test and prohibited outer desktop control without further
authorization. Screen covering and preboot/fresh-login testing remain out of
scope.

## Completion conditions and boundaries

Record protection state, OS build, signature, plug-in installation, mechanism
loading, authorization outcome, and actual unlock separately. Repeat grant
refusals, independent post-unlock app effects, password fallback, and removal
where the native route permits. Report an unavailable input or consent route
as its own boundary rather than a SIP failure. Never disable SIP or edit TCC
to obtain a passing result. Keep concrete identity and dummy credentials in
private manifest storage.

## Ordered work

### 1 — prepare a separate guest

Import a published vanilla image into a new task-owned disposable target.
Run doctor, acquire an exact target-use claim, and use the authoritative
adapter with a task-local Tart wrapper forcing no graphics, audio, or clipboard
sharing. Reach the guest through its existing SSH service; do not open a host
VM or Screen Sharing window. Verify SIP and record Gatekeeper independently.

### 2 — isolate the loading boundary

Build the retained sources and record their signature. Back up the stock
screen-unlock rule, install the experimental bundle and dedicated right, and
observe mechanism callbacks before integrating the screen-unlock branch.

### 3 — exercise locked-session authorization

Repeat the prior negative and positive matrix with independent OS lock-state
observation. Prove actual unlock and a subsequent application effect when
guest-native input is available. Preserve normal password fallback.

### 4 — restore and dispose

Restore and verify the original rule, remove experimental policy and files,
and recheck SIP and stock behavior. Shut down the disposable target, release
its claim, and remove only the task-created local clone. Record any retained
state or unfinished validation honestly.

## Validation and result

**Current (2026-09-10), `built` and `live-tested`:** The unchanged owned
authorization plug-in unlocked a disposable Tart guest running macOS 26.6.2
(25G83) with SIP, authenticated-root protection, and Gatekeeper enabled.
Two root-armed, password-free unlock cycles passed through the ordinary
guest-native resident. The plug-in used an ad-hoc signature with no Team ID.
Its sources and the resident/fixture were compiled on the controller and
copied into the guest; the vanilla image had no Command Line Tools installed.

### Protection state and bootstrap route

The imported vanilla image reported SIP enabled and Gatekeeper disabled.
`sudo spctl --global-enable` succeeded, and `spctl --status` reported
assessments enabled before installing or evaluating the plug-in.
`csrutil status` and `csrutil authenticated-root status` reported enabled.
All three remained enabled after the integrated tests and after removal.
No Recovery boot, SIP modification, TCC database edit, or account-password
change was performed.

Native input and capture initially lacked consent, including when the probe
ran as root. The guest's already-enabled macOS Screen Sharing service supplied
temporary native capture/input through a headless
[AsyncVNC client](../../research/providers/asyncvnc.md). This was a connection
to the target OS's resident service, not Tart's hypervisor VNC server or a
host Screen Sharing window. Normal guest System Settings consent enabled
Accessibility and Screen Recording for MacVM UI; the resident was restarted
to observe that consent. No consent was granted to the SSH wrapper.

The client disconnected before all integrated unlock tests. Independent
guest socket inspection found no established Screen Sharing connection before
those tests and after removal. Thus neither remote-login authentication nor
reconnecting Screen Sharing supplied the password-free unlock. The VM ran
with no graphics window, audio, or clipboard sharing, and outer UI remained
prohibited. Native doctor reached ready after consent.

### Test matrix

| Check | Independently observed result |
| --- | --- |
| Ad-hoc plug-in install and dedicated-right registration | Succeeded with protections enabled |
| No grant | Callback ran, logged denial, authorization returned `-60005` |
| Unprivileged arming | Refused without creating a grant |
| Expired or wrong-session grant | Denied and consumed |
| Valid direct-right evaluation while locked | Authorization returned `0`; OS remained locked |
| Reuse after direct evaluation | Denied |
| Native stock unlock before integration | Empty Return stayed locked; normal password succeeded |
| Integrated grant plus native empty Return | OS unlocked without password entry; repeated successfully |
| AX app effect after each password-free unlock | Fixture file counter changed from baseline 1 to 2, then to 3 |
| Native full-display capture after unlock | Showed the ordinary desktop and fixture |
| Unarmed integrated attempt | Stayed locked; normal password fallback succeeded |
| Expired integrated attempt | Stayed locked; normal password fallback succeeded |
| Removal | Saved stock rule restored and compared ignoring bookkeeping timestamps; experimental right, bundle, and root grant state removed |
| Evaluation after removal | Helper refused with `experiment_right_unavailable`, without generic authentication UI |
| Stock behavior after removal | Empty Return stayed locked; normal password succeeded; AX fixture counter advanced to 4 |

The integrated branch and grant mechanism were unchanged from Tactical 032.
The same resident generation survived the integrated lock/unlock cycles.
API acknowledgements alone were not treated as effects: OS lock state,
authorization callback decisions, visible guest captures, and fixture files
provided separate evidence.

### Cleanup and operational observations

After restoration and stock-behavior checks, the disposable guest was shut
down normally and removed using the authoritative exact-target mutation and
claim guards. The claim was released and the private dummy-credential manifest
marked disposed. The pre-existing source VM remained suspended. Raw evidence,
package pins, target identity, and credentials remain outside Git.

A private registry pin initially took precedence over task-local configuration.
That attempt was stopped, its claim released, and an explicit task registry
selected the imported guest. The pre-existing VM remained suspended and no
guest test commands ran there. Future reproduction should inspect effective
registry environment as well as `MACVM_CONFIG_FILE` before claiming a new
target. A temporary Screen Sharing capture timed out after a session
transition; reconnecting while unlocked restored it before consent work.
Neither issue changed the plug-in or was counted as a SIP failure.

### What this establishes

Disabling SIP was not necessary for this plug-in's locally built, ad-hoc-signed
loading or password-free screen unlock on the tested macOS guest. The next
implementation work is the typed resident operation and arming boundary,
alongside the known lock-reporting and input-targeting defects. Physical-Mac
behavior remains untested, but SIP-enabled VM feasibility is no longer open.

This is not notarized-distribution validation: locally compiled/copied code
does not exercise every quarantine or download-assessment path merely because
Gatekeeper reports enabled. Other macOS releases, hardware-specific behavior,
transition/race conformance, and a caller-authenticated protected broker still
need evidence. Screen covering, automatic relock, fresh login, and preboot
remain outside this test.

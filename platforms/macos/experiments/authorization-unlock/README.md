# Authorization unlock experiment

**Experimental, live-tested on disposable SIP-disabled and SIP-enabled Tart guests.**
These original sources prove a password-free unlock of an already logged-in,
screen-locked console session. They are not part of the installed resident or
its public capability contract. Repository MIT terms apply; no Codex binary,
source, or third-party authorization implementation is incorporated.

The [initial execution record](../../../../docs/tactical/032-macos-authorization-unlock-investigation.md)
and [SIP-enabled follow-up](../../../../docs/tactical/033-macos-sip-authorization-unlock.md)
own the test results and cleanup. The latter proved two password-free unlocks
with SIP, authenticated-root protection, and Gatekeeper enabled using the same
ad-hoc-signed plug-in. The
[macOS topic](../../../../topics/macos-resident-control.md) owns current direction.

## Components

- `Plugin.m`: Apple Authorization Services callback implementation for the
  `MCUnlockExperiment:unlock,privileged` mechanism. It grants or denies only
  that mechanism; it exposes no command dispatch or shell execution.
- `Session.h`: reads the current locked console session from IOKit; checks
  a root-owned, expiring grant against the user, console-session UUID, and
  boot epoch; atomically consumes the grant before returning a decision.
- `Control.m`: bounded experimental commands: `state`, `arm [seconds]`,
  `revoke`, and `evaluate`. Arming requires root and a locked, logged-in
  session, and accepts a lifetime from 1 to 30 seconds. Evaluation requests
  the fixed experimental right and reports its authorization status.
- `build.sh OUTPUT_DIRECTORY`: compiles and ad-hoc signs the bundle and
  helper. It never installs either or changes system policy.

Grant state lives in a root-owned mode-0700 experiment directory under
`/var/db`, with mode-0600 files. Files are bounded, regular, singly linked,
and opened without following symlinks. The root-installed helper should have
mode 0700; the local build's `evaluate` command can run as the guest user.
An armed grant authorizes one upcoming evaluation for the matching locked
console session; it is not a bearer credential presented by a named agent.
A different eligible request could consume it first. The prototype has no
caller-authenticated broker, and provides no separation from the test
administrator's unrestricted sudo access.

## Reproducing the policy experiment

Use only an explicitly selected, exclusively claimed **disposable VM**.
Carry the claim on every target operation through `machine-control`, and the
workspace handle when using a derived workspace. A fresh image import may be
bootstrapped as a task-owned disposable target before it becomes a ready base;
see the platform operating guide. This directory
has no unattended installer. Do not install it on a physical controller host.

1. Build for the guest's architecture, either in the guest or on a compatible
   Mac controller, and save the existing
   `security authorizationdb read system.login.screensaver` result in a
   root-owned backup. Refuse an unexpected existing policy rather than
   overwriting another authentication integration.
2. Install the root-owned bundle into
   `/Library/Security/SecurityAgentPlugins/MCUnlockExperiment.bundle`.
3. Register `org.machine-control.experiment.screen-unlock` using the
   supported `security authorizationdb write` interface with this definition:

   ```json
   {
     "class": "evaluate-mechanisms",
     "mechanisms": ["MCUnlockExperiment:unlock,privileged"],
     "shared": false,
     "tries": 1
   }
   ```

4. Prove absent, expired, mismatched-session, and consumed grants are denied.
   A valid grant allows this experimental right, but **evaluating the right
   alone does not unlock the desktop**.
5. On the tested stock policy, retain the original `use-login-window-ui`
   branch, prepend the experimental right to its `rule` array, and set
   `k-of-n` to 1. Save the installed definition for conflict-aware restoration.
   This intentionally adds an alternate authorization path for screen unlock;
   it does not change the account password or replace the password UI.
6. Lock the guest normally. With no grant, an empty Return leaves it locked.
   Arm a fresh short-lived grant through the root helper and submit an empty
   Return to the independently observed loginwindow. In the tested guest,
   loginwindow invokes the plug-in and unlocks without password entry.
7. Observe OS lock state and an independent app effect afterward. A successful
   key call or `AuthorizationCopyRights` alone is insufficient evidence.
8. In finally-style cleanup, revoke the grant, restore and verify the original
   authorization policy, remove the experimental right, then remove the
   plug-in and its state. Compare the current policy with the installed
   definition before restoration so unrelated changes are not overwritten.
   Prove normal password unlock again, then discard the workspace using its
   claim.

Retain any disposable account credential only in the declared private machine
manifest/store. No credential is needed for the armed plug-in path. The
normal-password fallback tests require the existing account credential.

## Deliberately limited behavior

Unlock exposes the ordinary desktop and does not automatically relock.
There is no display cover or local-input protection; the user explicitly
deferred those features. Grant expiry limits when authorization may occur,
not how long the desktop remains unlocked afterward.

The prototype relies on observed IOKit session keys and screen-unlock policy
behavior. SIP-enabled loading and unlock are live-tested on macOS 26.6.2;
notarized distribution, physical hardware, a broker outside the agent's
authority, transition/race handling, and common-facade integration remain
unproved. The standard resident's lock-reporting and input-targeting
bugs are not fixed by this separate experiment.

## SIP-enabled guest test

**Current:** This procedure passed in a disposable SIP-enabled Tart guest;
the follow-up execution record above contains the actual matrix. Disabled SIP
was not required for this plug-in on the tested guest. Physical-Mac evaluation
remains separate, as does testing downloaded/notarized distribution artifacts.
The [bootstrap guide's image security posture](../../docs/bootstrap.md#image-security-posture)
explains published vanilla versus base images and the fresh Apple IPSW route.

1. Select and claim a new isolated target. Record the image provenance and
   actual OS build privately. Verify `csrutil status` reports enabled before
   installing the experiment and again after the test. Record Gatekeeper
   status separately; a published vanilla image has automation modifications.
2. Establish guest administration and native capture/input with normal consent.
   Confirm stock password lock/unlock and save the original authorization
   policy before adding the experimental branch.
3. Start with these same sources and record the exact signature and loading
   result. Do not assume ad-hoc signing fails or succeeds with SIP enabled.
   The retained ad-hoc build passed on the tested guest. If another build fails,
   retain the relevant authorization-host/code-signing error
   and distinguish bundle installation, policy registration, mechanism load,
   callback invocation, and authorization denial. A separately signed build
   is another test condition, not a reason to weaken SIP or Gatekeeper.
4. Repeat the existing grant-refusal, real unlock, independent UI effect,
   normal-password fallback, and removal matrix. A direct experimental-right
   authorization remains insufficient proof of screen unlock.
5. Restore policy, verify stock unlock, and discard the test workspace.
   Promote only the capabilities actually observed. A SIP-enabled VM result
   would still leave physical display/input and hardware-specific behavior
   untested.

The source, policy composition, failure matrix, and restoration procedure are
retained for that follow-up and eventual physical-device evaluation. This is
not yet a validated physical-Mac installation procedure. Screen covering and
preboot/fresh-login behavior remain outside this investigation.

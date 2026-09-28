# Mac Tart Bootstrap Stages

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[macos-resident-control](../../topics/macos-resident-control.md)

Status: partial; fresh prepared and IPSW paths were inspected, but their
human consent and setup handoffs have not yet reached ready doctor.

## Objective and completion conditions

Expose read-only precreation and claimed-candidate stages for prepared and
vanilla Tart guests. An agent should choose each suggested action, recheck
actual host and guest state, and hand Setup Assistant, administrator
authorization, and TCC consent to a human. Completion requires both fresh
paths reaching a ready doctor through their stage reports.

## Boundaries

The inspector does not clone/create, submit a password, change TCC, or use
outer input. Exact candidate identity and a claim guard candidate inspection.
The caller declares the image kind; the report does not claim to prove it.
Private VM names, paths, and credentials remain outside Git.

## Ordered work and validation

1. Expose host screen/input permission and make `up` report power separately
   from guest-agent IP discovery.
2. Add precreation and candidate reports for host, guest transport, private
   credential file, tools, resident, Accessibility, and Aqua state.
3. Test missing/unknown/consent paths, then inspect an existing claimed VM.
4. Advance fresh prepared and IPSW candidates by stage output through ready
   doctor state.

## Result

Steps 1–3 are implemented, including typed administrator handoffs for Setup
Assistant and Command Line Tools. The live precreation report saw a registered VM
and granted host permissions. A claimed candidate report found a running VM,
guest administration, credential, tools, resident, and Accessibility, while
correctly leaving an unknown Aqua state unverified. A direct guest probe then
observed an unlocked session while the resident still reported unknown. A
guarded resident restart gave doctor a fully ready result; the stage inspector
now suggests that action for the same observed mismatch. A repair attempt exposed
that restarting Tart's own guest transport can interrupt its repair report;
the host now bounds that call and returns an explicit unavailable result.
The existing VM was left running after that earlier run.

On 2026-09-28, a fresh prepared image passed precreation, exact candidate,
host permission, guest transport, credential-file, build-tool, resident, and
unlocked Aqua stages. Its doctor was not ready because the new guest lacked
Accessibility consent for MacVM UI. `authorize-ui` surfaced the expected
human-required handoff; no TCC setting or password was submitted by the agent.

A separate fresh Apple IPSW candidate passed precreation and exact candidate
checks. `up` reported a running VM without requiring a guest agent, and an
outer recovery screenshot independently confirmed Setup Assistant's language
screen. The stage report identified Setup Assistant, administrator account,
credential recording, and guest-agent installation as human-required or
blocked dependencies. No login account was created. Both temporary VMs and
their caches were deleted after the checks; the IPSW guest needed an explicit
recovery stop when its agentless Setup Assistant did not shut down normally.
Step 4 remains open until both fresh paths pass their human handoffs and reach
ready doctor.

# Mac Tart Bootstrap Stages

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[macos-resident-control](../../topics/macos-resident-control.md)

Status: complete; fresh prepared and Apple IPSW Tart paths both reached ready
doctor through the stage reports.

## Objective and completion conditions

Expose read-only precreation and claimed-candidate stages for prepared and
vanilla Tart guests. An agent should choose each suggested action, recheck
actual host and guest state, and preserve Setup Assistant, administrator
authorization, and TCC consent boundaries. Completion requires both fresh
paths reaching a ready doctor through their stage reports.

## Boundaries

The inspector does not clone/create, submit a password, change TCC, or use
outer input. A separately chosen one-shot action may submit the recorded
prepared-image credential through physical Tart input after observing the
macOS sheet. Exact candidate identity and a claim guard candidate inspection.
The caller declares the image kind; the report does not claim to prove it.
Private VM names, paths, and credentials remain outside Git.

## Ordered work and validation

1. Expose host screen/input permission and make `up` report power separately
   from guest-agent IP discovery.
2. Add precreation and candidate reports for host, guest transport, private
credential file, tools, resident, Accessibility, Screen Recording, and Aqua
state.
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

A later fresh prepared run again reached an unlocked desktop, ready guest
administration, and a ready resident before stopping at the normal
Accessibility authorization sheet. Its default 1024×768 display clipped the
System Settings list; resizing the running Tart display to 1280×900 exposed
the MacVM UI switch and password sheet without changing TCC directly. The
inspector now keeps the outer bootstrap route in view until Accessibility is
actually trusted and checks the host policy and disruptive claim before
calling that route ready. A fresh Apple IPSW candidate reached Setup Assistant's
opening screen. Its stopped stage report now waits for account setup before
asking to record a login credential, and its running report correctly calls
for the human setup handoff.

The prepared-image password was already documented as `admin` and recorded in
the controller's owner-only credential file; a password-only guest login
verified that stored value. The initial agent response nevertheless asked the
user to enter it. After the user corrected that mistake, a new `type-secret`
route read the declared file through standard input only after checking the
foreground Tart window and posted physical keyboard events without placing
the password in arguments, output, or a capture. The visible Accessibility
sheet accepted one submission, and guest health independently reported the
grant. A display-capture request then exposed a separate Screen Recording
grant. Enabling MacVM UI in the visible macOS settings and restarting the
resident made capture ready. All prepared stages and doctor passed, as did the
full Mac smoke suite.

A fresh Apple IPSW VM then completed Setup Assistant, account creation, guest
agent installation, resident deployment, visible Accessibility and Screen
Recording grants, and a resident restart. Its stage report marked all twelve
stages complete; doctor reported administration, desktop, resident, semantic
control, capture, and input ready. The development post-update audit was
healthy, and the full Mac smoke suite passed against the fresh VM. The initial
50 GB virtual disk could not fit Command Line Tools;
after growing Tart's disk to 80 GB, Recovery's APFS resize made space for the
installer. The installed tools chose a newer SDK than the running macOS
release; deployment now selects the guest's matching SDK when available.
Outer Tart screenshots and clicks were corrected for a scaled window, and
Finder double-click was added for the setup route. Synthetic Shift and Command
events still failed to reach this fresh guest; the account was made with a
lowercase-and-digit credential, and the owner-only stored value was verified
through the guest's `sudo` authentication path before acceptance. No password
or private target identifier was recorded in Git.

During cleanup, guest shutdown could not authenticate this fresh account and
waited for a halt that never began. A bounded Tart stop removed the disposable
VM. The guest shutdown path now checks noninteractive administrator authority
first and reports an actionable blocker when it is absent.

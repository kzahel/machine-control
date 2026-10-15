# Control efficiency and usable agent entry points

Owning topics: [Computer Use positioning](../../topics/computer-use-positioning.md),
[unified desktop client](../../topics/unified-desktop-client.md).

Status: **Complete within the bounds below**. Software, guides, live acceptance
and the repeated instruction comparison are committed; owned resources are closed.

## Objective

Make Machine Control easier and more efficient for agents to use, prove its
behavior on disposable machines, and measure whether better instructions reduce
task cost. Deliver reusable software and evidence, with incremental commits.

## Deliverables and completion conditions

| Deliverable | Acceptance | Result |
| --- | --- | --- |
| Claude → Computer Use guide | Fresh agent-led setup, host registration, separate task session, independent effects and cleanup | Complete for two TextEdit workflows; [report](../evidence/claude-skill-acceptance-2026-10.md) |
| Stable native identity and compact observations | Preserve unchanged controls; refuse removed/replaced controls; correct diffs; deterministic and live tests | Complete within documented bounds; [native acceptance](../../research/platforms/macos.md#production-native-identity-acceptance) |
| Representative task harness | Extension loading, Finder, browser form and app menu tasks; readiness, claims, credential handoff, effects and disposal | All 8 pilot and 24 measured trials passed bounded task/lifecycle checks |
| Instruction comparison | Frozen discovery/quickstart prompts, matched model settings, repetitions, held-out tasks; report time, calls, tokens and failures | Complete; [results](../evidence/instruction-comparison-2026-10.md) |

## Boundaries

Use target-native control in disposable guests. Preserve claims and audit;
provider success alone is not proof of application effect. Keep private
inventory, credentials, transcripts and worker coordination outside Git.

No release, global agent configuration, vendor patching, primary-browser test
profiles or proprietary redistribution. Tactical 125's comparison stays
unchanged. Locked use is already implemented and has separate acceptance scope.

## Work and validation

1. Provide reusable [YA session operations](../ya-agent-sessions.md) for launch,
   follow-up, monitoring and cleanup. YA remains the session coordinator.
2. Test the [Claude guide](../../info/claude-computer-use.md) from fresh setup,
   including the host's required registration/new-session transition.
3. Implement identity and diffs, then test deterministic edge cases and real
   native controls before making performance claims.
4. Qualify task fixtures with a pilot; freeze source, prompts, model settings,
   runtime and appliance inputs before the repeated comparison.
5. Report task outcomes and cost distributions, keeping setup and task scopes
   distinct. Retain unsuccessful attempts and unknown measurements.
6. Verify cleanup, publish the comparison, and update the owning topics.

## Results and material limitations

**Claude guide:** two fresh setup/task workflows passed independent TextEdit
file checks and cleanup. The evidence report retains prior setup failures and
an evaluation correction distinguishing native runtime closure from wrapper
process exit. This is bounded workflow acceptance, not universal app coverage.

**Native control:** stable observation identities are separate from fresh action
references. Live tests passed ten unchanged reads, 21 stale-action refusals and
12 current-control effects. Settings, TextEdit menus and Control Center checks
also passed. Validation included 211 Swift tests, focused Python tests, both Mac
architecture builds and resident smoke checks. The platform report owns exact
limits, including incomplete transient menus and unqualified lifetime cases.

Compact unchanged observations were 66 bytes versus 638 bytes for the full
semantic projection. This demonstrates smaller output; **agent-level token and
time improvements from the native changes remain unmeasured**. The instruction
comparison uses its earlier frozen source, not these newer native changes.

**Task harness:** the initial Finder oracle incorrectly treated ordinary
`.DS_Store` metadata as payload. The corrected oracle still verifies exact
payload/decoy contents and rejects symlinks; a complete new pilot passed.
The proposed [agent quickstart](../../info/use-machine-control.md) addresses
observed discovery friction but is not injected into the frozen comparison.

**Instruction comparison:** the first measured phase stopped after 13 reviewed
task passes when a VM failed to start before model execution. The retained clone
was subsequently discarded through claimed recovery. The underlying startup
cause remains unknown. Its results and costs remain separate from the complete
24-trial restart; only the eight byte-identical qualified pilot observations
are reused, counted once. A lifecycle-annotation placement correction preserves
original reviews and raw receipts. Exact provenance stays with private evidence.

## Final result and follow-up

The [instruction report](../evidence/instruction-comparison-2026-10.md) records
24/24 measured successes. Quickstart reduced median tokens from 720k to 475k
and calls from 16 to 13.5. The median paired full-invocation difference was
only 0.41 seconds; no end-to-end speed improvement is established.

Owned workers stopped; final checks found no experiment workspaces and verified
claim release and stored credentials. The scoped runtime client was revoked.
Native agent-level performance, broader app coverage, appliance promotion
identity and independent focus/cursor checks remain roadmap work, not unfinished
claims of this bounded acceptance.

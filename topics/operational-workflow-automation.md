# Operational Workflow Automation

Topic: `operational-workflow-automation`

Status: living implementation tracker; linked tacticals distinguish source
review, implementation, and live acceptance.

## Scope and test for inclusion

**Current:** Fresh desktop appliance bring-ups have a
[dated private provisioning journal](../docs/provisioning-journals.md), with
automatic common CLI intent/result metadata and safe Windows/Linux/macOS phase
projections alongside explicitly agent-authored friction notes. Portable
fixture validation, privacy/refusal cases and coverage limits are recorded in
[Tactical 092](../docs/tactical/092-provisioning-journals.md).

**Decision:** Every fresh bring-up records a run, including successful runs
without friction. Notes preserve workarounds, fix commits and deferred ideas;
recording a problem does not require fixing it during provisioning. Direct
script/guest evidence remains separate and must be referenced explicitly.

This tracker covers operational work in which an agent still has to infer the
current stage, next safe action, or recovery branch from prose. A long document
is not itself a defect. Architecture, policy, consent instructions, and past
execution evidence should stay in Markdown. Repeated state checks and bounded
actions belong in the authoritative CLI when they can be observed reliably.

The audit covered the root/common-client guides, target registry, current
Windows/macOS/Linux factory and bootstrap guides, ChromeOS/iOS/Android/Quest/
Steam Deck setup and recovery, VM promotion, conformance entry points, and
native release guidance. It compared the guides with their existing commands
and scripts. Priority reflects operational frequency and failure cost, the
amount of judgment still encoded only in prose, and whether a safe command can
observe the needed state. This is a source audit, not a fresh run on every
target.

**Proposal:** An agent should drive explicit, independently checked stages. A
stage inspector reports `complete`, `action_required`, `waiting`,
`human_required`, `unverified`, or `blocked`, with stable reason and next-action
identifiers. The agent chooses each mutation and re-inspects its effect. An
unknown state must not become a retry or a guessed repair. A stage command
must preserve doctor read-only behavior, exact target identity, claims, secret
transport, and platform-owned mutation guards. Its output must omit concrete
private inventory and credential values. Shared vocabulary is useful; a
single cross-platform bootstrap script is not.

## Triage

`Now` is the next implementation queue, `Next` follows its dependencies, and
`Later` is worthwhile after repeated use shows the remaining friction. `Hold`
means the current command or human boundary already carries most of the work.
`Done` marks a completed exit check. Rows begin as proposals and stay open
until their exit check is met. Change a row's state to `done` only with the
linked implementation and exit evidence.

| ID | Queue | State | Workflow and evidence | Suggested path | Exit check |
| --- | --- | --- | --- | --- | --- |
| W1 | Done | done | [Windows factory](../platforms/windows/docs/image-factory.md) has read-only stages on Linux/KVM and Mac UTM. Both routes have fresh-candidate certification: [Linux](../docs/tactical/039-linux-windows-factory-stages.md) and [Mac](../docs/tactical/043-macos-utm-windows-factory-stages.md). The Mac run included an explicitly observed firmware recovery before a clean disk-only boot and certification. | Keep stage reports read-only and use the bounded factory commands for each action; retain the outer route for observed bootstrap or recovery failures. | A fresh candidate on each host advanced from media preflight through certification and clean stop, with blocked and secret cases represented truthfully. |
| C1 | Done | done | The [scoped common-client runner](../docs/scoped-runs.md) owns doctor, attributed acquisition, renewal, inherited selection, and cleanup; [tactical 046](../docs/tactical/046-scoped-target-tasks.md) records stateful failure tests and live Mac renewal/release. | Use `run` for bounded tasks and `--intent` for workspace ownership; keep task-owned lifecycle cleanup explicit. | Success, command failure, signal, and renewal failure leave an auditable release or explicit unresolved claim; workspace cleanup uses its returned handle and claim. Native Windows and live workspace evidence remain explicitly distinguished from fixtures. |
| L1 | Done | done | [Linux factory](../platforms/linux/docs/bootstrap.md#native-x86_64-libvirt-image-factory) has native KVM [fresh-candidate acceptance](../docs/tactical/040-linux-kvm-ubuntu-factory-stages.md) and Mac UTM [precreation](../docs/tactical/041-macos-utm-ubuntu-precreation-stages.md) plus [claimed-candidate acceptance](../docs/tactical/042-macos-utm-ubuntu-candidate-stages.md). Both routes reached exact-source certification and clean stop from stage reports. | Keep stage inspection read-only and choose each guarded action explicitly. | Both host routes report the same stage meanings and prove cloud-init/boot generation, exact pin, detached seed, resident readiness, and stopped source without treating command delivery as effect. |
| M1 | Done | done | [macOS bootstrap](../platforms/macos/docs/bootstrap.md) has a read-only [prepared/vanilla Tart inspector](../docs/tactical/044-macos-tart-bootstrap-stages.md). Fresh prepared and Apple IPSW guests each advanced through visible consent to all stages complete and ready doctor. The IPSW run also passed the development post-update audit. [Outer keyboard checks](../docs/tactical/045-macos-tart-outer-keyboard.md) now verify Shift/Command through guest effects and retain refusal for untested modifiers. | Keep stage inspection read-only and choose each guarded action explicitly. | Both fresh paths reported the next safe action and rechecked host and guest state through ready doctor; the inspector did not change TCC or handle passwords, and the chosen one-shot credential route kept the recorded value out of arguments and output. |
| I1 | Next | open | [Target registry setup](../docs/target-registry.md) distributes validation across `targets`, `inventory status`, credential inspection, doctor, and private file editing. | Add a read-only `inventory preflight` report joining schema, resolution, exact pin, credential locator/permissions, and doctor eligibility without copying private values into common output. | A misconfigured controller gets stable blocker codes and the owning private/config action; a valid controller can proceed to claim without interpreting a checklist. |
| P1 | Later | open | [Candidate promotion](target-lifecycle-and-readiness.md#explicit-readiness-and-candidate-handoff) has `validate-candidate` and `prepare-promotion`, but private role update and final ready-base evidence are manual. | Emit a promotion handoff receipt or report binding source, validation, clean stop, and required private-inventory update; verify the selected target again after that update. | A role change cannot be mistaken for validated promotion; exact stopped-source and final selected-role evidence are machine-readable while private inventory remains private-owned. |
| H1 | Later | open | [ChromeOS setup and post-update](../platforms/chromeos/README.md) already has resumable `setup` and guided `post-update`; physical VT2 recovery remains mostly human-directed. | Add machine-readable phase/blocker/resume output to the existing platform commands, especially across rootfs reboot and lost SSH. | An agent can resume the correct phase after each reboot and knows precisely when a VT2 action is needed, without automatic rootfs-policy changes. |
| D1 | Later | open | [iOS setup](../platforms/ios/docs/setup.md) pairs and prepares through CLIs but leaves signing, Developer Mode, Trust, and first-launch prompts as a numbered procedure. | Add a read-only onboarding stage report over current `probe`/`pair`/`doctor`/`prepare` evidence; describe the exact human action for each unobservable gate. | The agent distinguishes missing toolchain, pairing, signing/profile, runner, and local consent, and resumes after each gate without collecting passcodes or account credentials. |
| R1 | Later | open | [Windows workstation release](../release/README.md) uses CI and manifest verification, but run selection, exact source/run binding, version reuse, native acceptance, and publication readiness are split across prose. | Add a local release-candidate preflight/verification command over CI and artifact metadata; leave publication as an explicit separate action. | A candidate report binds source SHA, run attempt, signed bytes, version uniqueness, and native acceptance evidence, or names a blocker before publishing. |
| T1 | Later | open | [Conformance](../tests/client/README.md) and platform suites are scripted, but an acceptance campaign still chooses suites and collates evidence manually. | Add a non-mutating campaign planner and receipt collector keyed by target capabilities, platform, source revision, and test version; continue invoking existing suites. | A report identifies required, run, skipped, and failed suites and never calls an unrun test accepted. |
| A1 | Hold | open | [Android](../platforms/android/README.md), [Quest](../platforms/quest/README.md), and [Steam Deck](../platforms/steamdeck/README.md) have focused doctor/status commands and guarded actions; remaining onboarding mostly involves device approval or project-owned builds. | Keep explicit human prompts and native commands. Add typed handoffs only when a recurring blocker cannot already be distinguished by doctor. | A reproduced gap shows the doctor cannot identify a safe next step; otherwise no new orchestrator. |

## Suggested implementation path

**Current:** Retained appliance bring-up now has a
[shared recipe](../docs/retained-desktop-appliances.md) and
[Tactical 090](../docs/tactical/090-retained-desktop-appliance-rebuild.md).
Both retained ARM64 appliances now pass disk-only cold boot, verified
credentials, startup readiness and common conformance. Their private
development bindings are proven and the appliances remain running.
Linux can establish its stored login password on an independently verified
locked bootstrap account through pinned key-only SSH; it refuses replacement
of an unknown configured password. The NoCloud seed explicitly starts SSH.

**Current:** Linux now adds a required credential handoff to L1's factory
completion and P1's common promotion preparation. See
[Tactical 049](../docs/tactical/049-linux-credential-promotion-gate.md).
This closes the missing-password completion gap without completing P1's
private-inventory role update or claiming live acceptance of the new verifier.

1. **Use W1's accepted stages for later factory runs.** Preserve the
   exact-candidate first-logon receipt, installer-before-seed detach order,
   credential boundary, and claimed inspector. Keep the
   [factory guide](../platforms/windows/docs/image-factory.md) for media
   provenance, security posture, and observed outer recovery.
2. **Use C1 for bounded common-client tasks.** Supply truthful attribution to
   `run`; nested commands inherit selection while the parent owns renewal and
   cleanup. `--intent` owns the workspace handle and its claim together. Check
   the final audit's cleanup state even when the task itself succeeded. Tasks
   still arrange their required lifecycle transitions; a scope does not infer
   shutdown authority or grant an outer route.
3. **Use that scoped invocation on future factory runs.** W1 and L1 have
   fresh-candidate acceptance on both hosts through exact-source certification.
   Use the helper for subsequent checks, while retaining each
   platform's own evidence and repair rules.
4. **Add M1 and I1 as inspectors.** Tart's setup and TCC boundaries need
   `human_required` states; private inventory needs read-only diagnostics.
   Neither inspector should mutate consent, edit private inventory, or reveal
   endpoints. Gate later promotion/report work on their exact-identity output.
5. **Take the later rows only with measured need.** H1 and D1 should extend
   existing guided commands. R1 and T1 should assemble existing CI/test
   evidence rather than replacing those pipelines. P1 should stop at a
   verified handoff to the private inventory owner.

For each implementation slice, record the current source evidence, a bounded
tactical with ownership and completion conditions, simulated error-state
tests, and a live test only where it changes the claim. Mark the tracker row
complete only after the stated exit check, update the owning topic, and shorten
the operational guide once the command actually covers its branching logic.
Historical tactical records and human consent guidance remain intact.

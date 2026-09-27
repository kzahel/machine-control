# Operational Workflow Automation

Topic: `operational-workflow-automation`

Status: source-reviewed audit and proposed roadmap; the rows below are not
implementation commitments or live acceptance results.

## Scope and test for inclusion

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
All rows are **proposed** and open until their exit check is met. Change a
row's state to `done` only with the linked implementation and exit evidence.

| ID | Queue | State | Workflow and evidence | Suggested path | Exit check |
| --- | --- | --- | --- | --- | --- |
| W1 | Now | open | [Windows factory](../platforms/windows/docs/image-factory.md) has six claimed postcreation stages only for Linux; media preparation, creation, bootstrap repair, and UTM still require guide interpretation. | Extend the platform-owned stage inspector before creation and across UTM; keep every mutation explicit. | A fresh candidate on each host can be advanced from media preflight through certification and clean stop using stage output plus named commands, with blocked and secret cases represented truthfully. |
| C1 | Now | open | [Common claim/workspace examples](../README.md#common-workflows) require callers to parse IDs, renew, and arrange cleanup around every task. | Add a scoped common-client runner or SDK helper for doctor, acquire, renewal, command execution, and `finally` release. | Success, command failure, signal, and renewal failure all leave an auditable release or explicit unresolved claim; workspace cleanup uses its returned handle and claim. |
| L1 | Next | open | [Linux factory](../platforms/linux/docs/bootstrap.md#native-x86_64-libvirt-image-factory) has deterministic image/seed/create/bootstrap/detach commands but no fresh-image stage projection on libvirt or UTM. | Add Linux-owned preflight, cloud-init, guest transport, resident, media, and final doctor stages, reusing the W1 result vocabulary. | Both host routes report the same stage meanings and prove cloud-init/boot generation, exact pin, detached seed, resident readiness, and stopped source without treating command delivery as effect. |
| M1 | Next | open | [macOS bootstrap](../platforms/macos/docs/bootstrap.md) still sequences Tart clone/create, agent transport, UI deployment, and Accessibility consent in prose. | Add a Tart-owned prepared/vanilla bootstrap inspector; use typed human handoffs for Setup Assistant, administrator authorization, and TCC. | Each prepared or fresh path reports its next safe action and rechecks the actual guest and host permission state; no command modifies TCC or submits a human password. |
| I1 | Next | open | [Target registry setup](../docs/target-registry.md) distributes validation across `targets`, `inventory status`, credential inspection, doctor, and private file editing. | Add a read-only `inventory preflight` report joining schema, resolution, exact pin, credential locator/permissions, and doctor eligibility without copying private values into common output. | A misconfigured controller gets stable blocker codes and the owning private/config action; a valid controller can proceed to claim without interpreting a checklist. |
| P1 | Later | open | [Candidate promotion](target-lifecycle-and-readiness.md#explicit-readiness-and-candidate-handoff) has `validate-candidate` and `prepare-promotion`, but private role update and final ready-base evidence are manual. | Emit a promotion handoff receipt or report binding source, validation, clean stop, and required private-inventory update; verify the selected target again after that update. | A role change cannot be mistaken for validated promotion; exact stopped-source and final selected-role evidence are machine-readable while private inventory remains private-owned. |
| H1 | Later | open | [ChromeOS setup and post-update](../platforms/chromeos/README.md) already has resumable `setup` and guided `post-update`; physical VT2 recovery remains mostly human-directed. | Add machine-readable phase/blocker/resume output to the existing platform commands, especially across rootfs reboot and lost SSH. | An agent can resume the correct phase after each reboot and knows precisely when a VT2 action is needed, without automatic rootfs-policy changes. |
| D1 | Later | open | [iOS setup](../platforms/ios/docs/setup.md) pairs and prepares through CLIs but leaves signing, Developer Mode, Trust, and first-launch prompts as a numbered procedure. | Add a read-only onboarding stage report over current `probe`/`pair`/`doctor`/`prepare` evidence; describe the exact human action for each unobservable gate. | The agent distinguishes missing toolchain, pairing, signing/profile, runner, and local consent, and resumes after each gate without collecting passcodes or account credentials. |
| R1 | Later | open | [Windows workstation release](../release/README.md) uses CI and manifest verification, but run selection, exact source/run binding, version reuse, native acceptance, and publication readiness are split across prose. | Add a local release-candidate preflight/verification command over CI and artifact metadata; leave publication as an explicit separate action. | A candidate report binds source SHA, run attempt, signed bytes, version uniqueness, and native acceptance evidence, or names a blocker before publishing. |
| T1 | Later | open | [Conformance](../tests/client/README.md) and platform suites are scripted, but an acceptance campaign still chooses suites and collates evidence manually. | Add a non-mutating campaign planner and receipt collector keyed by target capabilities, platform, source revision, and test version; continue invoking existing suites. | A report identifies required, run, skipped, and failed suites and never calls an unrun test accepted. |
| A1 | Hold | open | [Android](../platforms/android/README.md), [Quest](../platforms/quest/README.md), and [Steam Deck](../platforms/steamdeck/README.md) have focused doctor/status commands and guarded actions; remaining onboarding mostly involves device approval or project-owned builds. | Keep explicit human prompts and native commands. Add typed handoffs only when a recurring blocker cannot already be distinguished by doctor. | A reproduced gap shows the doctor cannot identify a safe next step; otherwise no new orchestrator. |

## Suggested implementation path

1. **Finish W1 on the already accepted Linux path.** Add read-only media and
   host preflight before `factory-create`, then typed bootstrap and recovery
   branches after it. Preserve the current exact-candidate first-logon receipt,
   installer-before-seed detach order, password store/verify/rotate boundary,
   and claimed inspector. Make UTM report the same stages only after its
   provider-specific probes are independently established. Keep the
   [factory guide](../platforms/windows/docs/image-factory.md) for media
   provenance, security posture, and human decisions; make stage output the
   agent's operational index.
2. **Implement C1 as a small common-client composition.** It should take a
   truthful caller-supplied authority, claimant ID, reason, and bounded
   metadata; call read-only doctor, acquire, renew while work runs, pass the
   claim to the child operation, and release in `finally`. Workspace scope
   must retain both returned values and release the exact handle under its
   claim. Doctor may report an ordinary powered-off target as unready; an
   unresolved exact identity or invalid doctor result must stop acquisition.
   Do not make this a long-lived generic agent session or hide outer routes.
3. **Use that scoped invocation to exercise W1 and L1.** Linux's factory owns
   its cloud-init and NoCloud evidence. Its stages should share result fields
   with Windows, but no Windows-specific repair assumption. Run focused
   simulated states first, then one fresh candidate per available host route.
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

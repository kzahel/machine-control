# Reproduce and repair background browser click effects

Owning topic: [browser control](../../topics/browser-control.md).

Status: **implemented and VM-qualified for the focus/layout defect**;
the original static-page physical failure remains unattributed. Follows the
[physical locked-console click report](../../gaps/2026-11-01-locked-background-browser-click.md).

## Objective and completion conditions

The user requested committing the roadmap/triage, then reproducing the browser
click problem on a VM, fixing it if reproduced and committing the result.

- Pin the runtime, browser and extension used for each comparison.
- Exercise active/background tabs with the console unlocked/locked using an
  owned fixture and independent application/HTTP effects.
- Separate deployment differences, focus preparation, target geometry and
  application effects; do not infer a shared cause from acknowledgements.
- If reproduced, add a meaningful regression, implement a bounded repair and
  verify effects and foreground non-interference before committing.
- Finish with private evidence, verified workspace disposal and honest limits
  on physical and installed-store qualification.

## Boundaries

Use a claimed disposable Mac workspace, Chrome for Testing and target-native
administration/control. No primary browser testing, outer input, physical-host
app replacement, permission weakening, automatic input retry or publication.
Keep concrete identities, credentials, logs and captures private. The inherited
login credential remains in the controller's canonical owner-only secret store.

## Ordered work

### 1 — pin deployment and prepare the isolated guest

Compare installed store/bundled extension JavaScript with source and inspect
manifest-origin differences. Journal and claim the clone, verify readiness,
stage the exact runtime and retain immutable baseline inputs.

### 2 — reproduce native browser input effects

Reuse the existing background/locked browser harnesses. Record independent
click/text callbacks, HTTP effects, DOM state, captures, page geometry and
selected-tab/foreground state across the comparison matrix.

### 3 — isolate and repair a reproduced defect

Reduce any failure to a deterministic fixture. Change only the implicated
provider behavior, preserve authority/generation checks and classify unavailable
or uncertain effects truthfully. Do not replace native input with script clicks
to make an oracle pass.

### 4 — validate, dispose and report

Run focused contract tests and live regression comparisons. Verify cleanup,
finish the private provisioning journal, update the owning evidence/topic and
commit the bounded result. Recommend the next investigation from remaining
evidence.

## Validation and final result

The installed desktop is 0.6.11; source, bundled and installed-store extension
JavaScript matched at the start of the investigation. Store and development
manifest keys/origins differ. These on-disk matches do not fingerprint the
historical running provider. Physical Chrome reports 156.0.8078.74; the
separate test binaries were CfT 155.0.8059.79 and 156.0.8078.80, not that exact
physical build.

Initial ordinary unlocked/background and locked-console fixtures passed, as
did eight static selected/background zoom cells on CfT 156. The reported
static-page failure did not reproduce in this VM configuration.

A focus/visibility-sensitive fixture isolated a different failure: the worker
read `DOM.getContentQuads`, then first enabled virtual focus immediately before
mouse delivery. The fixture moves its button from x=8 to x=188 CSS pixels on
that transition. All four background zoom cases acknowledged input at the old
position, hit the body and produced zero HTTP clicks; selected-tab controls
passed. This is independently observed geometry/effect evidence, not merely a
command-order assertion.

The repair shares existing virtual-focus preparation and invokes it before
scrolling and measuring the referenced target. Raw input still prepares focus;
authority, stale-reference, refusal, release and explicit-foreground semantics
remain. There is no script-click fallback or automatic input replay.

- The worker's independent moved-target regression fails before the repair and
  passes afterward; all 29 extension tests pass.
- The tracked `--focus-layout-change` guest harness fails before the repair and
  passes all 18 checks afterward on CfT 156: independent HTTP click/text, PNG,
  native foreground/key-window/cursor sampling, selected-tab preservation,
  virtual-focus cleanup and explicit foreground/reconnect behavior.
- Eight repaired store-origin unpacked comparisons pass while independently
  locked, covering selected/background tabs at 50%, 100%, 125% and 200% zoom.
  Every case records one HTTP click; background selection remains unchanged.
- The existing one-shot verifier confirms the inherited canonical appliance
  credential without disclosure. Owned browser/sentinel processes are absent;
  reviewed raw receipts and the fixture PNG are retained controller-private.

`python3 bin/check --portable`, Python harness compilation and whitespace/link
checks pass. Exact workspace release reports `discarded`; follow-up inventory
is empty and the unchanged source remains powered off. The private provisioning
record is closed failed because the earlier reboot transport left an unpaired
intent, despite independently observed reboot/readiness. It is not promoted to
a complete bring-up certificate; the retained fixture and disposal receipts
stand separately.

This source change is not published or installed on the physical host. The
original static-page failure, animated/asynchronous layout beyond the tested
callbacks, physical/store rollout and other platforms remain separate
qualification work. Native sentinel samples are 20 ms apart; shorter transient
foreground changes are not excluded.

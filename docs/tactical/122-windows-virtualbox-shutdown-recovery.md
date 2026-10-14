# 122 — Windows VirtualBox shutdown recovery

Status: complete; stable paired comparisons and root cause remain open.
Owning topics: [target lifecycle](../../topics/target-lifecycle-and-readiness.md)
and [VM storage policy](../../topics/vm-workspaces-and-storage-policy.md).

## Objective and completion conditions

Investigate why the documented post-request pause/resume assist did not finish
one Windows development-guest shutdown, while pause/resume followed by an ACPI
request did. Improve the provider guide and Windows skill with an executable,
honest shutdown/recovery decision path and the limits of the evidence.

Complete when source and historical evidence are reconciled, bounded live
comparisons distinguish sequence from request method where possible, public
guidance is updated, and the owned development guest is Off and claim-free.

## Boundaries

Use the unprotected development guest under an exclusive disruptive claim.
Keep its hardware, guest power policy, credentials and host hypervisor, WSL
and security settings unchanged. Do not start or change the protected base.
No saved state, new provisioned image, product deployment, provider code change
or production qualification is implied. Exact identity, logs, captures and
execution scripts stay private. Force-stop is permitted by the operator only
if bounded clean recovery fails; it is never evidence of clean shutdown.

## Ordered investigation

1. Review provider dispatch/tests, existing lifecycle traces and upstream
   command semantics. Distinguish scheduling pause from saved-state suspend.
2. Observe cold-boot administration and servicing readiness. Compare the
   normal delayed-assist path, pre-request pause/native shutdown, ACPI alone,
   and pre-request pause/ACPI on separate boots when readiness permits.
   Record boot/session/idle conditions and request-to-Off time. Short research
   observations are censored measurements, not replacements for the normal
   fifteen-minute shutdown deadline. Adapt comparisons to concrete failures.
3. Observe recovery effects independently, record every fallback in the
   private usage journal, and leave the guest Off before releasing the claim.
4. Reconcile guidance, provider dossier and owning topics. Run documentation
   checks and review the public diff for private infrastructure before commit.

## Results

### Source and retained evidence

Reviewed `providers/virtualbox-windows/adapter.py` dispatch for normal shutdown,
ACPI, force-stop, identity/claim checks and scheduling assistance, plus
`images.py` qualification invalidation and the adapter/image tests. All 29
existing provider tests pass. The native path requests `shutdown.exe /s /t 0`
through SSH, then performs one configured delayed pause/resume and waits up to
900 seconds. The wait starts only after the guest command returns. An earlier
SSH/command error can prevent the assist from running. ACPI delivers a virtual
power-button event; neither request delivery nor guest events prove Off.

Retained audit history confirms the product-session shutdown failed after
903.965 seconds. The provider log confirms its delayed cycle occurred roughly
34 seconds after the request. Windows kernel shutdown event 109 was recorded
roughly 185 seconds after the request. A second authorized cycle much later
reset roughly 4,572 seconds of timer backlog, followed by provider Off about
3.3 seconds after resume. ACPI was also delivered in that recovery, so it does
not isolate order from method. The older pause-only trace in
[Tactical 094](094-windows-hyperv-development-host.md#unassisted-shutdown-trace--2026-10-05)
already demonstrates completion of a pending shutdown without a new request.

Inference: a single early scheduling cycle can precede a later shutdown stall.
It is not evidence that pre-request ordering is inherently better. Guest and
host clocks can diverge during these stalls, so event timing is not an exact
stall-onset oracle. Neither a timer catch-up reset nor prior successful
qualification establishes a reliable root-cause fix.

### Live servicing/restart observation

The unprotected development guest started from confirmed Off. Its first boot
applied Windows servicing, changing build `26300.9457` to `26300.9711`; host
VirtualBox and guest Additions both reported `7.2.20`. Temporary administration
confirmed servicing processes, then the guest entered its own restart and lost
administration. This is a servicing boot, not a stable comparison condition.
Host hardware, power/security/WSL settings and guest power policy were unchanged;
no credential submission or product deployment occurred.

After the complete ten-minute initial boot observation, one authorized
scheduling cycle verified Running, Paused and Running under the existing
provider's exact-identity/protected-base checks and operation lock. It reset
about 480 seconds of timer backlog. No new shutdown request accompanied that
cycle. Running persisted through its 30-second observation and administration
remained unavailable. A subsequent public ACPI request was delivered, but
independent status still showed Running after a separate 120-second observation.
This short recovery budget is not a new fifteen-minute shutdown failure.
A later outer capture was unavailable with the display reporting zero bit
depth; capture failure did not substitute for the power-state oracle.

The operator had explicitly permitted force-stop if clean recovery failed.
The public force-stop command succeeded, and a separate claimed status verified
Off. This is forced cleanup, not clean lifecycle evidence. The guest was not
rebooted/requalified afterward. The protected base was not started or changed.
Private usage notes record direct research steps, measured budgets and cleanup;
owned scripts/captures are removed and the claim is released.

The planned stable native/ACPI and pre/post-request matrix was not executed:
servicing and the unavailable restart prevented equal starting conditions.
Do not claim an order winner, reliable pre-request workaround, or unassisted
acceptance from these observations. Resume controlled comparisons on a stable
unprotected candidate; retain the existing compatibility profile until the
three distinct qualified cold-boot gates pass with any replacement policy.

### Documentation and validation

The provider guide now distinguishes scheduling pause, saved-state suspend,
native request, ACPI delivery and power cut. It records the actual delayed
assist order, its early-command failure boundary, independent terminal-state
checks and a bounded authorized recovery path. The Windows skill links that
guide and respects already-granted power-cut authority. The provider dossier
and lifecycle/storage topics retain the evidence and remaining gaps without
promoting recovery to production reliability.

Validation: 29 existing provider regression tests, changed-document local-link
resolution and `git diff --check`. No provider/runtime code changes or new
release are included.

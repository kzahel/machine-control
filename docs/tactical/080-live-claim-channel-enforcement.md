# Live target claims at the channel adapter

Status: complete for source, deterministic fixtures and remote Mac native AX
acceptance; native Windows acceptance remains unqualified.
Owning topics: [access admission and pause](../../topics/access-admission-and-pause.md),
[target-use claims](../../topics/target-use-claims.md).

## Objective and completion conditions

A raw admission transport must not outlive the selected exact-resource claim
merely because it can keep sending resident heartbeats. Preserve the existing
claim's duration, renewal owner and fencing, refuse before transport launch,
check again before each complete frame, and close on expiry, replacement,
release, parent loss or input EOF. Never acquire or renew on the caller's behalf.

## Boundaries and ordered work

1. Add a bounded transport guardian to the existing exact-resource claim helper.
   The adapter supplies resource binding; public claimant labels remain
   self-asserted coordination rather than authenticated authority.
2. Check the existing claim before launch and every incoming frame; perform
   independent periodic checks even when the caller stops polling. Reap only
   the owned transport process group and preserve legitimate target claims.
3. Integrate Mac physical/inner and Windows physical/inner adapter channels,
   including the installed CLI payload. Keep legacy fail-fast claim behavior.
4. Verify direct raw expiry, release/replacement, external renewal, oversized
   frames and refusal before launch; repeat native inner effect acceptance.

## Validation and result

**Current:** 21 claim/provider fixtures, five Windows host adapter tests and
seven control SDK fixtures pass. Mac and Windows platform smoke suites pass.
A fresh claimed Mac appliance session repeated native snapshot and AX action;
independent fixture state increased exactly once and the fixture was reaped.

The guardian queues at most eight complete 64 KiB request frames alongside
bounded reader/writer buffers, does not
replay them and checks liveness independently each second. Resident/session
watchdogs remain separate. Closing a transport cannot undo an action already
forwarded; uncertain effects still require observation before another action.
The explicit optional claim mode remains the existing diagnostic/test profile,
not authenticated authorization or a stronger same-user containment boundary.

Queueing target-use claims, shared outer transactions and authenticated YA
integration remain separate work in [Tactical 074](074-access-admission-and-pause.md).

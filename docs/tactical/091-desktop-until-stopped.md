# 091 — Indefinite manual access on every desktop platform

Status: active.

Owning topics: [host control](../../topics/host-control.md),
[Windows desktop](../../topics/windows-desktop.md),
[Linux desktop](../../topics/linux-desktop.md), and
[native distribution](../../topics/native-distribution.md).

## Objective and completion conditions

The operator wants **Until I turn it off** on every packaged desktop platform,
not only Mac. Implement explicit indefinite manual grants on Windows and
Linux, retain Mac support, and deliver all six architectures in one tagged
release. Test the installed product on available Machine Control VMs.

- Advertise native support and reuse the shared duration choice and status.
- Model no expiry explicitly; do not substitute a very large timeout.
- Keep selected scopes, Stop, pause, availability, stale references, pending
  approvals and update exclusion enforced. Public agent approvals stay timed.
- Pass deterministic clock-based tests and native installed fixture effects.
- Authenticate all six release packages and verify production update delivery,
  including Windows replacement from public 0.5.3.

## Boundaries

No new restart/reboot persistence semantics or protected login capabilities.
Preserve existing Mac consent behavior and each platform's session rules.
This slice covers the Mac/Windows/Linux desktop product, not new desktop UI
for mobile or device providers. Keep private VM identities and raw evidence
outside Git. Use doctor, exclusive claims, renewal and finally-style release;
prefer target-native scripted acceptance. Outer recovery is authorized when
needed, with the required disruptive claim. Preserve unrelated working edits.

## Ordered work

### 1 — implement explicit native grant lifetimes

Extend Windows and Linux operator arming with `timed` and `until_stopped`.
Make expiration optional, guard every expiry consumer, report lifetime and a
null countdown, and advertise `manualUntilStoppedSupported`. Reject unknown
lifetimes and retain bounded public requests. Cover Windows admission expiry.

### 2 — prove authorization and installed behavior

Add fake-clock tests for long elapsed time, timed replacement, bounded agent
approval, scopes, Stop, stale generations, update exclusion and existing
pause/session behavior. Run Windows format, contract tests and ARM64/x64
publishes; Linux grant tests; Mac regression and shared frontend checks.
Exercise visible arming, no countdown, independent fixture effects and Stop
on available claimed VMs using candidate packages. Record actual coverage.

### 3 — publish and verify one complete release

Write meaningful versioned notes, commit source, build a unified signed
candidate, authenticate packages and perform native acceptance. Promote the
same bytes with one immutable annotated tag. Verify public assets, six updater
entries, downloads and production Windows 0.5.3 replacement. Update topics
and acceptance evidence, leaving architecture execution gaps explicit.

## Validation and final result

Pending implementation and acceptance. Source review confirms that the shared
UI and Mac already support this lifetime, while Windows and Linux currently
require numeric grant durations and do not advertise indefinite arming.

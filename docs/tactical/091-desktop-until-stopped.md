# 091 — Indefinite manual access on every desktop platform

Status: complete. Public desktop 0.5.4 released on 2026-10-04.

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

**Current:** Public [desktop 0.5.4](https://github.com/kzahel/machine-control/releases/tag/desktop-v0.5.4)
ships **Until I turn it off** on Mac, Windows and Linux. Windows and Linux
represent indefinite access with an absent expiration and report
`lifetime: until_stopped` plus null remaining seconds. The existing shared UI
selects it through the private operator channel. Public agent approvals remain
timed. No new restart/reboot persistence semantics were introduced.

### Source and publication

- Immutable annotated tag: `desktop-v0.5.4`.
- Release source: `3cf849532efb86f76baaa7fa9496eb51c6409de5`.
- Unified candidate: [37195098707](https://github.com/kzahel/machine-control/actions/runs/37195098707),
  attempt 1; all six architectures passed.
- Promotion: [37197076604](https://github.com/kzahel/machine-control/actions/runs/37197076604);
  the same accepted bytes were published without rebuilding.
- Cross-platform checks: [37195082520](https://github.com/kzahel/machine-control/actions/runs/37195082520),
  all six native/coordinator jobs passed.
- All 29 public assets match GitHub SHA-256 digests and candidate receipts.
  Mac signing/notarization/staples, Windows signed installed inventory, and
  Linux signed containers and inventories pass authentication. Tampering is
  rejected. All six bundled CLI payloads pass hosted relocation checks.
- Both production update services return the matching signed 0.5.4 entry for
  all six 0.5.3 senders, and HTTP 204 for 0.5.4. All eight download redirects
  and the downloads page select 0.5.4.

### Deterministic and installed validation

Windows contract checks, format verification and ARM64/x64 publishes pass.
Linux's 12 grant tests and Mac's 16 grant-broker tests pass. Fake-clock coverage
proves indefinite access survives long elapsed time while timed access still
expires. Scope enforcement, Stop, stale generations, bounded agent approval,
update exclusion and existing pause/readiness rules remain covered. Frontend
and release tooling checks pass.

All three available local desktop VMs are ARM64. Tests used exclusive renewed
claims and target-native scripted UI actors, with independent fixture state as
the effect oracle. No outer control or Computer Use was needed.

- **Windows ARM64:** exact signed installed source and complete payload
  inventory; native visible duration choice; indefinite lifetime and null
  countdown; independent Cua counter effect; Pause blocks operations while
  retaining the grant; Resume restores access; Stop revokes it; subsequent
  agent approval remains timed. The independent UIA actor launches `--gui`
  in a maximized window, with WebView2 accessibility enabled for inspection.
  It selects the visible popup item through UIA SelectionItemPattern and
  waits for the resulting combobox value; synthetic End/Enter had left the
  previous duration selected. The full check passes again on the installation
  upgraded from public 0.5.3. Installed package files remain unchanged.
- **Mac ARM64 Tart:** exact signed/notarized package; visible indefinite
  selection and null countdown; native denial and narrowed approval;
  independent AppKit counter effect; self/protected refusal; input refusal
  during a pending prompt; Stop. The isolated test-state directory uses the
  required private permissions; no product permission check was bypassed.
  A hash-verified archive was extracted inside the guest before signature and
  source verification, avoiding stale shared-folder directory entries.
- **Linux ARM64 GNOME Wayland:** exact signed Debian package and source;
  supported graphical session readiness; visible indefinite choice/status;
  null countdown; AT-SPI delivery and independent GTK counter effect; Stop
  revokes access and leaves the user fixture alive. The actor ran through the
  graphical systemd user manager to inherit the real session context.
- **Windows production update:** the actual public 0.5.3 installation discovers
  0.5.4 in Settings. Installation is disabled while access is armed and enabled
  after Stop. The signed update replaces and automatically relaunches the app
  at the exact release source, with access off, a fresh generation and refusal
  of old-generation requests. The independent user application survives.

The earlier 0.5.3 Windows “Up to date” response was accurate: it was the latest
published release, and it did not implement indefinite arming. Mac had shipped
that choice earlier. This was a platform feature gap, not evidence of an
updater failure or an independent Windows release channel.

### Release blockers repaired

The full release checks exposed pre-existing portability and packaging gaps:
Bash 3 empty-array expansion, Windows subprocess/pipe assumptions and native
path/inode behavior, POSIX-only fixture boundaries, a redundant unavailable
`fchmod`, and the Linux journal payload inventory. They were repaired with
focused tests before publication. Concurrent first-use audit initialization
also exposed SQLite initialization contention on Windows; initialization now
uses a bounded busy/locked retry and closes failed connections, without
replaying event writes. Native Windows Python 3.12 checks and repeated
concurrent-first-use tests passed. A hosted ARM64 Git Bash cold-start timeout
was bounded at 30 seconds. Its independent adapter check now sends real
heartbeats while waiting, preventing correct lease expiry during a slow Bash
startup. A six-second injected cold-start delay passes on all three adapters;
the audit stress actor retries bounded BUSY/LOCKED errors while still requiring
exactly forty unique committed events. Production audit wait limits and writes
remain unchanged. The Mac large-reply fixture uses a 16 KiB receive buffer
for its 512 KiB payload, retaining backpressure within the existing five-second
write bound; all 141 native tests and twenty repeated regressions pass.
Installed Windows discovery compares directory identity rather than spelling
so canonical long paths and temporary 8.3 aliases are equivalent. The native
short/long alias probe passes. Final native/coordinator and signed-build
checks pass.

### Limits and cleanup

This is focused feature acceptance, not a new full lifecycle/browser pass on
every architecture. Intel Mac and Windows/Linux x64 packages are authenticated;
their GUI evidence retains its earlier recorded versions. ARM64 Linux portal
capture/input, AppImage replacement and browser tasks, and broader ARM64
Windows lifecycle/browser work remain separate. Physical hardware, reboot
persistence and protected unlock were not added to this slice.

All test grants were revoked and owned fixture processes cleaned up. The Mac
appliance's exact policy was restored and it was returned to its initial
powered-off state. Windows and Linux remain running, as found. Exclusive
claims were explicitly released. No appliance credentials were changed;
private identities, raw logs and evidence remain outside Git.

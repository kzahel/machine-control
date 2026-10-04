# Windows owner-session native acceptance

Status: focused native candidate acceptance complete on Windows ARM64. Signed
release qualification is separate.
Owning topics: [unified desktop client](../../topics/unified-desktop-client.md),
[Windows desktop](../../topics/windows-desktop.md), and
[access admission](../../topics/access-admission-and-pause.md).

## Objective and completion conditions

Qualify Tactical 095 on a dedicated Windows VM before expanding the session
API or adding a persistent language runtime. Run SDK and retained CLI
snapshot/action workflows against independent native and browser fixtures.
Exercise competing owners, direct-call refusal, disconnect, heartbeat expiry,
Pause/Resume and Stop. Confirm effects independently and preserve uncertain
outcomes without replay. Commit a repeatable runner and fixes it exposes.

## Boundaries

Use the common doctor, an exclusive exact-target claim, and target-native
administration/UI only. Preserve initial power state, installed release and
unrelated applications. A staged app copy may combine the installed operator
with a locally built runtime for behavior qualification; identify that mixture
honestly rather than claiming signed-release acceptance. Use a separately
identified test browser, retain private evidence outside Git, and release the
claim after all owned processes and grants are cleaned up.

## Ordered work

### 1 — stage the candidate and independent actors

Inspect the accepted VM, installed app and available fixtures. Stage a private
candidate with exact source/runtime identity. Operate real consent, Pause and
Stop UI from an independent actor in the guest interactive session.

### 2 — exercise the same authority through SDK and CLI

Verify typed negotiation, one live owner, reference lifetime, independent
application effects, and browser extension delivery. Exercise negative and
handoff cases without suppressing native authorization or notice behavior.

### 3 — repair, rerun and record qualification

Fix bounded defects exposed by native execution, add focused regression
coverage, and run appropriate format/contracts/build checks. Record actual
provider routes, architecture, skipped cells and cleanup; leave other platforms,
authenticated claim binding and the Mac incident as separate follow-up work.

## Validation and result

**Current, conformance-tested for the bounded candidate route:** the independent
operator actor, common Python SDK and common CLI exercise real Windows named
pipes, native provider effects and the browser extension. The candidate uses
the installed 0.5.4 operator with a source-built ARM64 runtime at
`0a11e09a6549e6fe62e021ac67b76986fcf62f18` and its matching upstream-pinned Cua
0.17.0 provider. It is an explicitly mixed staging assembly, not a signed new
release. The runner records exact native executable digest, source revision,
operator identity, browser version, actual routes and cleanup separately.

### Observed behavior

- Real operator UI enables access and presents the native admission notice.
  Idle standing grants and forged JSON ownership cannot dispatch native work.
- SDK snapshot/action/observation and retained CLI workflows independently
  advance the native fixture counter. Routes include
  `windows.user_session/cua/get_window_state` and
  `windows.user_session/cua/accessibility`.
- A second owner waits and cannot borrow the first connection's fence. After
  release, the successor acts while the previous reference is rejected.
- Pause interrupts ownership without another effect. Resume permits fresh
  admission. A silent owner expires while its transport remains open; a late
  dispatch is refused with the independent counter unchanged.
- Killing a retained CLI owner releases ownership and permits an SDK successor
  to act. One-shot native and browser CLI calls negotiate short ownership.
- Chrome for Testing uses `chrome.extension/cdp` to change a separate browser
  counter through both the SDK and retained CLI. Direct browser mutation cannot
  bypass the owner, and operator Stop revokes it without another effect.

### Defects and fixture corrections

Native execution exposed a client compatibility defect: Cua confirms delivery
while honestly reporting `effect: unverifiable` until an independent oracle is
supplied. The CLI had interpreted any uncertainty text as a reason to close the
session, preventing the next observation. Commit `b4d7f0b` preserves the result
and owner for explicit follow-up observation. Refusal, unknown delivery and
unknown/partial effects still terminate; no action is replayed.

Commit `c473267` fixes the SDK interruption error's argument placement: the
admission view belongs in structured error data, not the numeric exit code.

Initial fixture setup also caught a legitimate provider digest refusal when a
locally built runtime was paired with the differently signed installed Cua
binary. The candidate was rebuilt with its matching pinned provider, without
weakening digest verification. A preflight session transition was recovered
through the existing stored-credential login route and fresh session selection;
its cause was not established. The absent legacy UI relay was not required:
the existing appliance resident launches the independent interactive actor.

One repeat returned a first browser snapshot without the expected fixture
control after tab-load completion. The harness now waits for that control using
bounded observations only, retaining a diagnostic snapshot on failure. It does
not retry navigation or input. The final full run passes all 39 checks with no
cleanup errors; an earlier full run also passed before this readiness hardening.

### Validation and limits

All 231 common client tests pass, including 19 control-session tests. Portable
Windows desktop/live-channel and admission contracts pass, along with native
runtime format verification and ARM64/x64 cross-publishes.

This pass uses a staged candidate and source common client. It does not qualify
a complete signed installer, bundled-client relocation, production update,
broader application lifecycle, protected desktop, hostile same-user containment,
or authenticated claim-to-caller binding. Older direct-IPC release runners need
session-aware migration before use on an owner-required release candidate.
Interruption tests kill an idle owner or refuse subsequent work; they do not
establish transactional cancellation of an OS effect already in flight.
Windows x64 native execution and other platform cutovers remain separate.
No Mac failure reproduction or subprocess-churn improvement is claimed.

The repeatable entry point is
[`owner-session-live.py`](../../tests/windows/owner-session-live.py), documented
in the [Windows test guide](../../tests/windows/README.md#live-owner-session-acceptance).
Raw outputs and concrete deployment details remain private.

### Cleanup

Independent post-run inspection finds no owned app, browser, actor, server or
native fixture processes, and no browser registration pointing at the candidate.
The installed 0.5.4 operator/runtime retain valid signatures and their original
release metadata. The final doctor reports an unlocked, ready resident and the
VM remains running as found. The exact target claim was explicitly released;
no credentials changed. Staging files and raw evidence are retained privately
for reproduction, not published as release artifacts.

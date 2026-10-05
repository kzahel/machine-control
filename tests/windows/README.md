# Windows conformance

## Streaming CDP acceptance

[`browser-cdp-live.py`](browser-cdp-live.py) runs in the interactive Medium
session of an exclusively claimed VM. Stage the desktop app, matching runtime
and pinned provider, Chrome extension, bundled Python, source `client/`, actor
and [`cdp_socket.py`](cdp_socket.py). Supply `--install`, a separately identified
Chrome for Testing `--chrome` and private `--output`. Launch through a Limited
interactive scheduled task or the target-native application route, with the
installed operator closed. The HTTP oracle listens only on target loopback.

The actor uses actual operator setup/Access/Pause/Stop UI and retained SDK
ownership. It checks page reads, console events, command correlation, provider
errors, independent HTTP effects, scope/token/Origin refusals, disconnect and
native-host restart. Progress and final evidence stay private. Cleanup restores
registration, closes ownership and reaps the owned app/browser/server. The
outside caller must independently inspect cleanup, retrieve evidence, remove
staging/tasks, restore original VM power and release the claim in finally/trap
cleanup. [Tactical 099](../../docs/tactical/099-windows-streaming-cdp.md) records
actual candidate evidence; this does not qualify a signed public package.
Each run creates a fresh browser profile so a retained Manifest V3 worker
cannot mask changes to the staged extension.

## Browser upload acceptance

[`browser-upload-live.py`](browser-upload-live.py) runs in the interactive
Medium session of a dedicated, exclusively claimed VM. Stage a desktop app,
matching runtime/provider and extension, bundled Python, source `client/`, and
the runner under `tests/windows/`. Pass `--install`, a separately identified
Chrome for Testing `--chrome`, and a private `--output` outside AppData/hidden
storage. The output includes synthetic upload files, a dedicated browser
profile and private result evidence; the HTTP fixture listens only on loopback.

The runner operates the real operator UI, enables only browser access, uses the
live SDK owner and CLI upload request parser, and checks independent received
bytes. It covers direct/multiple-file inputs, intercepted single choosers,
invalid batches, stale references, browser versus DevTools, Pause and Stop.
Its cleanup restores native-host registration and reaps owned app/browser/
server processes. The controller must independently inspect cleanup, retrieve
private evidence, remove owned staging, restore initial VM power and release
the claim. This runner does not qualify a signed installer or public release.

The Windows suites exercise the same installed facade from two placements:

- `conformance.ps1` drives ordinary system-shell and window behavior through
  an authenticated administration carrier.
- `provider-composition.ps1` runs the deterministic fixture workflow through
  Cua and native providers from either remote or local placement. Its optional
  failure lane terminates only the supervised Cua child to prove bounded
  restart, stale-reference, timeout, and disclosed fallback behavior.
- `inbox-application-workflow.ps1` drives Calculator, Settings, Character Map,
  and Notepad through the resident facade. It proves native registered/package
  activation with settled content and application-frame surfaces when Windows
  splits a package across HWNDs, classic launch, system semantics, four
  UIA-confirmed window transitions, persisted document bytes,
  reopen/readback, exact-window capture, full/compact/unchanged payload
  metrics, preservation of pre-existing state, and owned-artifact cleanup.
- `provider-absence.ps1` is an explicitly confirmed, reversible package test.
  It withholds the installed Cua executable after revocation, proves truthful
  unavailable capability and native observation fallback, then restores the
  exact file and revokes the temporary helper generation.
- `run-local-probe.cmd` starts `local-probe.ps1` as the logged-in Medium user
  and proves that it reaches the same named pipe and result contract.
- `uac-conformance.ps1` originates elevation from the Medium fixture, cancels
  and approves genuine secure-desktop prompts, and verifies a High-integrity
  fixture through an independent marker.
- `lifecycle-conformance.ps1` runs separately authorized lock, logout, or
  protected-state inspection and records only minimized route/state evidence.
- `scripts/login-windows.sh` is the separately supervised PIN/password
  acceptance route. It prompts the human without echo and uses the runtime's
  dedicated non-JSON secret channel.

`scripts/bootstrap-windows.sh` is the reproducible host-to-target installation
path used before these suites. It requires a UUID-pinned candidate assertion
from the authoritative testbed, or the explicit `--allow-unattested-target`
mode for physical and non-integrated targets. It detects ARM64/x64, builds and
verifies the matching package, installs through administrative SSH, waits for
the Medium helper and adopted providers, and removes transfer staging. Its
default `development` profile first installs and verifies Python 3 plus .NET
8; `runtime` explicitly omits that toolchain. It assumes a testbed-ready
Windows base; it is not an OOBE or credential bootstrap.

`platforms/windows/bin/winvm appliance-certify` is the heavier retained-image
acceptance path. It requires a clean commit and exact candidate, observes a
changed boot epoch, runs `bin/check --portable` and `bin/check --native` from a
digest-bound archive in the guest, removes staging, and shuts down only after
success. Fixture coverage proves the successful handoff and that a guest-check
failure does not request shutdown.

Run its host-side target-safety checks with:

```bash
tests/windows/bootstrap-target-safety.sh
```

The suites write generated evidence only to caller-selected target-local paths.
Do not commit raw output or screenshots. A testbed operator must separately
authorize and supervise lock, logout, reboot, and credential-gated recovery.

Before running UAC conformance, verify all three policy conditions:

- UAC is enabled;
- administrator elevation requires consent; and
- consent prompts use the secure desktop.

The test is invalid if policy is weakened to avoid `Winlogon`. When semantic
controls are unavailable, the result must identify target-local pixels/input
as a fallback rather than count delivery as a semantic pass.

Credential login is intentionally not an unattended suite. Begin from a real
no-user `Winlogon` state, run the helper once with `pin` or `password`, and
independently confirm WTS user state, the `Default` input desktop, and a fresh
Medium helper. Never put the credential in a PowerShell command, test
parameter, JSON fixture, environment variable, evidence file, or deliberate
wrong-credential case. A discovery refusal must end the case without retrying.

`provider-composition.ps1 -Placement local` deliberately skips
`service.revoke`: a local caller is a child of the helper generation, and
successful revocation is expected to terminate that process tree. The remote
lane proves revocation and helper recreation instead.

## Workstation distribution acceptance

`workstation-conformance.ps1` addresses an explicit installed user instance and
interactive session. It proves Medium integrity, protected refusals, stale
generation fencing, direct Cua semantics and capture, and an independent
fixture-owned counter effect. Pass the fixture separately from the product
payload. `workstation-lifecycle.ps1` runs inside the ordinary interactive
session against two different packages and exercises upgrade refusal while
running, stop/start, rollback, stale requests, two-instance isolation, and
removal. Both scripts retain their evidence outside the product package.
See [Tactical 036](../../docs/tactical/036-windows-workstation-distribution.md)
for the appliance and signed-artifact acceptance gates.

`workstation-package-trust.ps1` requires a signed package and trusted publisher.
It tampers with a payload file and forges the unsigned hash inventory, then
requires catalog verification to refuse installation before activation.

Run workstation conformance with `-ExerciseProviderFailure` only on a distinct
candidate instance: it terminates that instance's provider and briefly withholds
its binary, restoring the file in cleanup. It checks stale provider references,
one restart, disclosed fallback, and disconnected/malformed IPC resilience.
For the idle-session regression, launch the candidate with the upstream test
setting `CUA_DRIVER_RS_SESSION_IDLE_TTL_SECS=5` and pass `-IdleSeconds 35`.
The test requires expiry to occur, refuses an old action, obtains a fresh
observation, and independently verifies exactly one subsequent action. Restore
the launch environment afterward; normal product launches retain upstream TTLs.

## Exact semantic reference regression

`reference-fixture.ps1 -EvidencePath <owned-path>` exposes duplicate buttons and
text fields with independent file effects. Launch it in the interactive guest,
then run `reference-conformance.ps1` with an isolated user-host executable,
instance, session ID and that evidence path. It checks exact reference routing,
removed-element and generation refusal, and unchanged query-only behavior.
Close the owned fixture and stop the user host after the suite.

Omit `-Instance` to run the same reference assertions against the installed
appliance facade after deployment.

## Desktop app CLI acceptance

`desktop-cli.ps1` runs in the ordinary interactive user session against an
explicit desktop installation. Select exactly one `-Client` (the installed
`mc-cli\commands\machine-control.cmd`) or `-Source` checkout. The installed
route invokes that command for every operation and artifact retrieval; it does
not invoke a system Python or read the checkout. Verify the candidate's
publisher and complete CLI/native inventories before running it.

Without `-Fixture`, the harness proves the local desktop profile and native
approval refusal. An independently armed fixture run proves semantic action,
a separate counter marker, capture hash, stale reference refusal and cleanup.
Both release the local target-use claim in `finally`. This harness does not
replace signed installation, browser, YA model/media or update acceptance.

`cli-installed.py` under `tests/desktop` separately copies the entire client
payload to an unrelated path and checks offline discovery, runtime isolation
and bundled claims. Windows x64 execution passes in a claimed appliance with
no source checkout mounted into the test. This is CLI execution evidence; it
does not authenticate an unsigned staging payload.


## Live owner-session acceptance

`owner-session-live.py` runs from the controller against an already claimed
Windows VM. Stage a copy of the desktop app with the candidate runtime and its
matching pinned provider; retain the installed release. A locally assembled
candidate is behavior evidence, not signed-package acceptance. Supply the
exact native build revision and SHA-256 independently of the runner revision.
The VM must have an unlocked interactive session, the accepted appliance
resident, Python, and a separately identified Chrome for Testing executable.
The installed desktop app must be closed before starting this isolated run.

```sh
python3 tests/windows/owner-session-live.py \
  --target windows --claim "$claim_id" \
  --install '<guest candidate app directory>' \
  --guest-root '<owned guest acceptance directory>' --session SESSION_ID \
  --chrome '<Chrome for Testing executable>' \
  --fixture '<native medium counter fixture executable>' \
  --runtime-revision COMMIT --runtime-sha256 SHA256 \
  --output '<private controller evidence directory>'
```

The caller runs doctor, acquires and renews the exact VM claim, and releases
it in finally/trap cleanup; this harness borrows that claim without renewing or
replacing it. It verifies readiness and claim validity again, uploads only its
independent UI actor/browser fixture, and launches the actor through the
appliance's target-native application route. The actor operates real Access,
Pause/Resume, Stop and browser setup UI. Its private mailbox is test-operator
control, not an agent approval API. Agent work uses the ordinary desktop
product's live channel through the existing Python SDK or common CLI.

Checks cover unowned/forged requests, native notice, independent counter
changes, two competing connections, stale references, Pause, silent-heartbeat
expiry, killed CLI owner, successor progress, one-shot negotiation, browser
extension effects and Stop. Results preserve actual provider routes. Cleanup
closes sessions, kills only owned fixture/app/browser processes, restores
browser native-messaging registration, and reports cleanup failures. Evidence,
resolved inventory, guest paths and runtime identifiers are private; commit
only minimized findings to Tactical 096. No controller desktop input is used.

Older direct-IPC desktop grant/browser/release runners describe the pre-owner
contract and are not substitutes for this runner on an owner-required candidate.
Their full release/lifecycle cases need session-aware migration before release;
this focused pass does not qualify those unexecuted cases.

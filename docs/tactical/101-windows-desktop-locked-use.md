# Windows desktop bounded unlock and relock

Owning topics: `windows-desktop`, `windows-protected-unlock`,
`access-admission-and-pause`.

Status: source implementation and focused unsigned x64 VM acceptance;
signed installed qualification remains pending authenticated release tooling.

## Objective

Following the request to finish Windows desktop qualification and locked use,
integrate the existing guarded unlock protocol with native desktop consent,
connection-owned tasks and an independent privileged relock watchdog.

## Completion conditions

- Exact installed-candidate qualification for the accumulated Windows changes.
- Initially disabled operator preparation and explicit controller approval.
- One-shot password transport after exact provider/field discovery, without
  caching passwords or changing Windows security policy.
- Same account and logon session after unlock, independently observed task
  effects, and relock after completion, Pause, Stop, expiry or failure.
- Unprepared, stale, foreign, paused and observe-only requests refuse before
  credential use; interrupted effects are never automatically replayed.
- Owned processes, services and staging are cleaned up; runtime format,
  contracts and both Windows architecture publishes pass before commits.

## Boundaries

The first Windows profile temporarily exposes the console while a task runs.
The operator must see this before enabling it. Opaque covered control is a
separate presentation/capture qualification; this slice claims no Mac cover
privacy. Local console accounts and password fields inherit the existing
unlock broker's exact discovery limits. No cold login, account switching,
appliance authority, persistent password, arbitrary privileged dispatch or
automatic retry is added.

## Ordered work

### 1 — qualify the installed Windows candidate

Resolve authenticated release tooling and build a signed CI candidate. Exercise
native and browser workflows, install/update with the test browser open,
optional helper setup/removal and uninstall against its exact bytes.

### 2 — bind unlock to desktop consent and task ownership

Reuse protected controller grants and one-shot credential transport. Expose
operator-only setup and opt-in, explicitly prepared owner admission, and an
exact owner-bound unlock preparation. Keep ordinary dispatch unavailable until
independent unlock evidence, and rotate stale observation generations.

### 3 — own relock independently of the desktop process

Start a privileged guardian before possible credential submission. Bound it to
the exact account/logon session, task authority and finite deadline. Observe
physical takeover, service/resident failure and authority loss; confirm relock
before admitting another task.

### 4 — validate and document the product contract

Use the existing deterministic contracts and a command-driven interactive VM
actor with independent OS and fixture evidence. Record exact candidate identity,
architecture limits, cleanup and remaining signed/physical qualification gaps.

## Final result

The native implementation is committed in `0d3964a`; controller challenge
binding and installed CLI packaging are committed in `bdd3272`. The operator
guide is [Windows bounded locked use](../../desktop/WINDOWS-LOCKED-USE.md).

### Candidate and evidence boundaries

The campaign uses a Tauri debug app with embedded frontend assets and a
self-contained x64 resident in a dedicated Windows-hosted VirtualBox
development VM. The actual operator UI installs the optional helper, selects a
public controller proposal, completes administrator approval, enables the
initially disabled option and grants access. The native resident remains Medium;
the protected service and independent guardian run as SYSTEM. The separate
testbed appliance handles setup consent, independent lock observations and
canonical-credential recovery only. It is not a fallback for product unlock.

Runtime hashes:

- Earlier lifecycle candidate:
  `9d0c940bc39e7daddff768fa13f553425ee8d38d1e20aa86f24ede27779b9c40`.
- Final native candidate:
  `07629fd5d77610222aacfc3281cf7a5bfcf1ecc5ffed6ef5f94427f1c05ce59e`.

The earlier candidate proves one-shot existing-session password unlock, owned
native semantic observation, an independent fixture counter effect, target-local
capture and independent WTS relock after completion, owner transport failure,
45-second task expiry and operator Pause. Its final Stop attempt refused during
controller proof before credential use. The final candidate gives proof its own
bounded 15-second wait within the unchanged 45-second signed challenge.

The final candidate also proves injected pointer and keyboard effects without
ending guarded ownership. Its final Stop campaign passes all twelve checks,
including the actual operator control and independently observed relock.
Process-crash completion is recorded below; partial runs are not counted as
complete acceptance.

This first profile temporarily exposes the console. Signed installed packages,
accumulated-feature replacement/uninstall, broad Cua post-unlock workflows,
ARM64 live, physical takeover, localized/domain/cloud accounts, RDP, PIN and
opaque display privacy remain open. GitHub CLI authentication is unavailable on
the controller, so no signed CI candidate or publication is claimed.

### Validation and friction

Runtime format verification, desktop/admission/CDP contracts, unlock contracts,
nine controller protocol tests, frontend type checks, Rust formatting and both
x64/ARM64 self-contained publishes pass. The file-symlink fixture reports an
unavailable OS privilege; its remaining file-boundary tests pass. These builds
do not establish ARM64 execution.

The campaign caught and fixed callback identification, Medium inspection of
the protected shared-parent ACL, stale phase acknowledgements and a setup notice
that survived completion. The shared parent receives only non-inheriting Users
read-permissions metadata access when it already hosts another unlock instance.
Grant contents and privileged payloads remain protected.

Stock lock-screen notifications and one display-wake failure caused
pre-credential refusal. The outside
fixture waits for stock locked presentation and may dismiss an exactly observed
notification; the broker's discovery restrictions remain unchanged. The actor
also needed integer click coordinates, a minimized operator window to respect
self-protection, a retained settings HWND distinct from the task notice,
and forced termination only
after verifying its own crash fixture's process identity. No mutating or
credential operation is automatically replayed.

The VM exhibited long scheduling stalls and timer catch-up during extended
load. A separately claimed bounded pause/resume recovery restored execution;
it invalidated development qualification history and supplied no host desktop
input. This is infrastructure recovery, not evidence of ordinary feature
delivery or an unassisted VM reliability fix. The
[VirtualBox dossier](../../research/providers/virtualbox.md) owns that finding.
Logoff and canonical stored-credential sign-in recovered interrupted runs and
do not count as product in-place unlock. Private evidence keeps exact identity,
claims, credentials, controller keys and raw captures outside Git.

### Interruption and cleanup outcome

The final native candidate passes isolated service-crash and resident-crash
campaigns, each with nine checks through the real operator setup and retained
owner. The outside fixture verifies and terminates the exact owned process;
the independent appliance observes WTS locked afterward. These checks establish
guardian independence from those two processes, not resilience to a killed
guardian or hostile privileged software. The final Stop campaign passes twelve
checks, including independently observed pointer/keyboard effects and relock.

Cleanup removes the optional desktop helper/service and its protected grant,
all campaign scheduled tasks, checked guest staging, the owned fixture marker
and temporary controller key/public preparation. It restores the exact added
shared-parent metadata ACL rule. The independent appliance/provisioning services
remain running; the common doctor is healthy before shutdown and the canonical
stored login credential verifies. UAC and secure-desktop policy remain enabled.
The common shutdown completes in 40.2 seconds under the declared scheduler
assistance profile. A separate status confirms power off, and the cleanup claim
is released. This does not qualify unassisted shutdown reliability.

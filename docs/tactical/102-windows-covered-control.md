# Windows covered control and initial lock-state cleanup

Owning topics: `windows-desktop`, `macos-locked-use`,
`access-admission-and-pause`.

Status: source implementation and focused x64 development VM qualification;
physical, signed-package and new native Mac execution remain open.

## Objective

Add opaque Windows display covers to the bounded locked-use profile. Honor
the requested UX: task cleanup may lock only a task that began locked.
An unlocked-origin task never acquires relock authority from a later idle lock.

## Completion conditions

- Target-native opaque covers exist before possible password submission.
- Capture and injected agent input reach underlying apps with independently
  observed fixture effects; physical input ends control before leaking through.
- Owner completion, expiry, Stop and process failure keep covers until the
  locked-origin console is independently observed locked.
- Native task-start observations fence unlock authority. Unlocked-origin tasks
  finish without requesting lock on both Windows and macOS.
- Format, contract tests, frontend checks and Windows x64/ARM64 publishes pass.
- Development VM evidence, route limits and remaining physical/signed gates
  are recorded; owned artifacts and processes are cleaned up.

## Boundaries

Reuse the existing one-shot credential protocol, independent SYSTEM guardian
and explicit native consent. Do not weaken lock policy, capture passwords,
cache secrets or introduce arbitrary privileged dispatch. A display cover is
presentation privacy, not containment against privileged local processes.
Qualify the initial one-display VM route before claiming hardware coverage.
Keep signed package acceptance separate from development evidence.

## Ordered work

### 1 — prove capture and presentation separation

Measure native capture exclusion, cover opacity and underlying input on the
accepted Windows VM. Refuse unsupported display/capture conditions before
credentials can be read.

### 2 — bind cleanup to the task's starting state

Capture native console state at ownership acceptance. Only locked-origin
owners may prepare unlock; preserve this state through subsequent transitions.
Correct the macOS waiting-for-lock path and test its immutable origin rule.

### 3 — integrate independent covers and interruption

Extend the guardian to own cover lifetime and physical-input interception.
Expose honest capability and operator wording, and qualify completion and
failure with independent OS and fixture observations.

### 4 — record validation and cleanup

Record exact candidate identity and bounded evidence. Remove owned helper,
controller approval, staging and processes, verify appliance credentials,
shut down through the common CLI and release the target claim.

## Result and evidence boundaries

The native implementation is in `9c2e456`, with configuration reporting in
`8fb4d8d`. The [Windows guide](../../desktop/WINDOWS-LOCKED-USE.md) owns the
current operator and controller workflow. `a2c8c1b` preserves otherwise valid
Mac approval when the original ordinary lease ends at an idle lock.
The single-display Windows-hosted VM uses an embedded-frontend Tauri debug app
and self-contained x64 resident. Actual operator controls install/arm the
helper, approve the public controller proposal and grant desktop access.

### Candidates and observed effects

- Initial covered candidate:
  `a746bc232bb595ed832086bf7b5ef02fba07230c5f768077bd83ec14f0925e8e`.
- Final native candidate:
  `46e0ae0ddee7865dadc02e0936964b527a73f7ffddf48536c5a9dc9e70f0d10f`.

The initial candidate passes 14 covered-task checks and two seven-check origin
scenarios. The latter independently confirm that ordinary completion leaves
Windows unlocked and that a later idle lock refuses credential preparation
from the original task. They retain their initial candidate identity.

The final candidate passes 15 covered-task checks. Independent VirtualBox
display capture is entirely black while native full-display GDI capture
contains the underlying apps. Injected pointer and keyboard actions produce
independent fixture counter effects while ownership remains active. An agent
attempt to close the guardian is refused. Owner completion is followed by
independent WTS lock readback before cover cleanup. The final resident-crash
scenario and the final service-crash scenario each pass nine checks, with
independent opaque presentation before termination and WTS relock after the
exact owned process is terminated. The final native candidate thus has 33
focused checks across covered completion and the two independent crash cases.

A preliminary red-window probe independently separates black presentation
from captured red GDI pixels. This establishes the measured native capture
route; it does not qualify broader Cua, GPU app, hardware or multi-display
behavior. VirtualBox screenshots are independent diagnostic evidence; task
semantics, capture, input and unlock run inside Windows without host input.

### Refusal and fixture preparation

One resident-crash attempt refuses during stock display wake with
`lock_display_wake_refused`, `credentialRead: false` and `delivery: not_sent`.
No password or failed effect is replayed. After canonical testbed recovery,
a new owner starts the subsequent scenario. The separate testbed fixture
dismisses only the observed stock curtain and confirms Winlogon before handing
over to product unlock for the crash test. Those crash checks therefore prove
guardian lifetime, not the stock curtain/wake route. The normal covered runs
retain their earlier product preparation evidence. The refused wake transition
remains a compatibility gap rather than being hidden by a product fallback.

The host's declared scheduler recovery is needed once after boot before its
guest route becomes usable. That bounded outer lifecycle recovery has no host
input and is separate from feature evidence. Readiness and exact target claims
are carried through ordinary operations; raw private fixture scripts retain
the audit contract's coverage limits.

### Validation and remaining gates

Windows runtime format, desktop/admission/CDP and unlock contracts,
x64/ARM64 publishes, nine controller tests, frontend typecheck, embedded debug
build and Rust format pass. Mac source now rejects later covered activation
from an unlocked-origin legacy lease and preserves otherwise valid standing
approval at that ordinary lock. Its regression covers locked, unlocked and
unknown origins. No configured Mac target or native Swift/AppKit build route
is available on this Windows controller; new native Mac execution remains
pending.

Signed installed qualification, ARM64 live, physical takeover, other display
configurations, other capture providers and abrupt guardian-process death have
no new acceptance claim. Covers are presentation windows, with no zero-frame
privacy guarantee. Existing credential, UAC, lockout and desktop policy remain
unchanged.

### Cleanup

The owned helper service/payload and desktop controller approval are removed.
The shared parent ACL is restored, owned scheduled tasks, staging and fixture
marker are deleted, and the temporary controller key/preparation are removed.
The baseline appliance remains healthy and its canonical stored credential
verifies. Common CLI shutdown confirms power off in 37.6 seconds under the
declared scheduler-assistance profile; this is not unassisted-shutdown
qualification. The exclusive target-use claim is released afterward.

# Windows covered control and initial lock-state cleanup

Owning topics: `windows-desktop`, `macos-locked-use`,
`access-admission-and-pause`.

Status: implementation and Windows development VM qualification in progress.

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

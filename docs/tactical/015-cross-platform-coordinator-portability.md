# Tactical 015: Cross-Platform Coordinator Portability

Status: complete.

Topics: `cross-platform-coordinator`, `target-lifecycle-and-readiness`, and
`unified-desktop-client`.

## Objective

Make the common coordinator and its private-inventory boundary run natively on
macOS, Linux, and Windows while keeping controller-host eligibility distinct
from target OS and worker placement. Add reproducible target-native static
checks and prove the Linux and Windows paths from inside the existing UTM
appliances without requiring separate agent sessions.

## Completion conditions

- The registry contract declares controller platforms and portable launcher
  behavior for every route.
- Target listing reports the current controller, route eligibility, and
  adapter availability without exposing command, environment, or selectors.
- Selecting an unsupported controller route returns a typed refusal before
  command lookup or execution.
- Python, PowerShell, Bash, and direct launch behavior is covered by
  dependency-free tests; the coordinator itself is invoked portably through
  the active Python interpreter.
- One root check command runs common and platform unit tests from their correct
  directories and provides OS-native static/build checks.
- Hosted CI runs coordinator portability on macOS, Linux, and Windows, plus
  the matching target-native check on each OS.
- Dotfiles emits explicit controller eligibility and continues to resolve all
  currently configured macOS-controller routes into `machine-control`.
- The checked-in coordinator passes its portable and Linux-native checks from
  inside the existing Linux appliance.
- The checked-in coordinator passes its portable and Windows-native checks,
  including the Windows runtime build, from inside the existing Windows
  appliance.
- macOS portable/native checks pass on the controller host.
- No live target value, VM identity, endpoint, credential, or captured UI is
  committed or emitted by portable CI.

## Boundaries

- Do not implement Linux equivalents of Tart or UTM, or a Windows hypervisor
  provider, in this slice.
- Do not make an adapter appear supported merely because Bash, WSL, or another
  compatibility layer happens to be installed.
- Do not add a generic privileged shell to the common contract.
- Do not replay full semantic, capture, input, protected-session, or physical
  device acceptance.
- Do not require private dotfiles in public hosted CI; use a sanitized fixture
  provider.
- Do not start a separate agent session in either guest. The macOS controller
  stages and invokes the exact committed source through the authoritative
  testbed administration route.

## Implementation steps

### 1 — type controller routes

Extend the target registry and private provider with normalized controller
platforms and explicit launch behavior. Keep those public route facts separate
from private commands and environment.

### 2 — make coordinator execution portable

Centralize command resolution for Python, PowerShell, Bash, and direct
executables. Use it for availability, adapter calls, explicit testbed/OS
escapes, and inventory delegation. Refuse unsupported controller routes before
resolution.

### 3 — own lightweight checks

Add one Python root check command. Run common-client and dependency-free device
tests from their canonical working directories, validate JSON and shell
syntax, and dispatch a bounded native check for the current OS.

### 4 — add target-native CI

Add hosted macOS, Linux, and Windows jobs. Run fixture-backed coordinator tests
on every OS and matching Swift/plist, Linux Python/shell, or Windows
.NET/PowerShell checks on the native job. Do not use private inventory or live
targets.

### 5 — prove Linux from inside Linux

Start or recover the dedicated Linux appliance through its authoritative UTM
adapter, stage the exact committed source, and run portable plus Linux-native
checks through guest administration. Record only minimized pass/fail and tool
version evidence.

### 6 — prove Windows from inside Windows

Start or recover the dedicated Windows appliance, stage the same committed
source, ensure the required public build tools are present on that dedicated
test appliance, and run portable plus Windows-native checks through PowerShell
administration. Record minimized evidence and clean temporary source afterward.

### 7 — close the contract

Update topics, system map, entry documentation, and this tactical with actual
hosted/local evidence, deviations, and remaining work. Commit and push only
after public-safety and clean-worktree checks pass.

## Validation

- `python3 bin/check --portable` on the macOS controller and both guests.
- `python3 bin/check --native` on macOS and Linux; `py -3 bin/check --native`
  or equivalent on Windows.
- Common-client tests for redaction, unsupported-route refusal, and launchers.
- Dotfiles inventory tests and canonical-path assertions.
- Workflow syntax inspection and hosted CI results after push.
- Read-only status before VM mutation; target guard checks before lifecycle or
  guest writes; no outer input during ordinary validation.

## Result

The coordinator now normalizes Darwin, Linux, and Windows controller hosts;
types every adapter's eligible controller platforms and launcher; reports
route support without private commands or environment; and refuses an
unsupported controller before adapter lookup. The private inventory emits the
same route facts for its current controller. A root `bin/check` owns portable
unit/syntax checks and dispatches bounded native checks, including all three
Windows .NET builds. Public CI contains independent portable and native jobs
for macOS, Linux, and Windows.

The macOS portable/native checks passed. Commit `c25c699` was exported without
Git metadata, transferred through the guard-pinned Linux UTM adapter, and
matched by SHA-256 in the guest. It passed the portable corpus, Linux-native
checks, and a direct target-list invocation that reported Linux as the
controller platform. Temporary guest source was removed and the appliance was
shut down.

The original live Windows attempt found only a generalized seal with no
authorized administration route. Tactical 018 later recovered the retained
stateful candidate and supplied its missing public Python and .NET 8 build
toolchains. The first exact-archive retry exposed that the native check runner
did not bypass Windows' default per-process script-execution restriction;
`bin/check` now supplies `-ExecutionPolicy Bypass` only to the checked-in static
script invocation. Tactical 018 owns the final exact-source and reboot record.

Hosted public run `31481111956` passed all six coordinator/native jobs on
macOS, Linux, and Windows at commit `5ed134a`. Windows parsed the PowerShell
corpus and built all three .NET projects with .NET 8. The portable Windows job
executes the common coordinator and dependency-free device logic; five
ChromeOS post-update cases are explicitly skipped there because their fake SSH
fixture requires native POSIX execution, and both Unix jobs cover them. Private
inventory run `31480390146` passed its three-controller registry matrix and
portable agent-config check at dotfiles commit `4ef3ded`.

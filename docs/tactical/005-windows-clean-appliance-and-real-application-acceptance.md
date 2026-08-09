# Tactical 005: Windows Clean Appliance and Real-Application Acceptance

Status: active; started 2026-08-09.

Topics: `windows-resident-control`, `architecture`, and
`capabilities-and-results`.

Parent tactical:
[`000-windows-resident-control-vertical-slice.md`](000-windows-resident-control-vertical-slice.md).

Precursor:
[`004-windows-provider-composition-and-agent-ergonomics.md`](004-windows-provider-composition-and-agent-ergonomics.md).

## Objective

Turn the proven Windows runtime into a reproducible appliance output rather
than a hand-maintained installation. Begin with a stopped, authoritative
Windows testbed base on which MachineControl is completely absent. Build and
install the correct architecture package through the administration carrier,
prove resident readiness after a cold start, run sustained inbox-application
work through the same local and remote facade, clean test state, shut down, and
retain a sealed clone that passes a disposable verification boot.

Keep base-image and product-image responsibilities distinct. The authoritative
testbed owns Windows OOBE, licensing, guest tools, key-only SSH bootstrap,
explicit appliance auto-logon, hypervisor lifecycle, cloning, and recovery.
This repository owns the reproducible MachineControl package, installer,
readiness contract, UI workflow, and conformance result. A testbed-ready base
is the input; a controller-ready stopped clone is the output.

## Completion conditions

- The authoritative testbed exposes safe stopped-source sealing/cloning and a
  disposable verification boot. It refuses source/target identity collisions,
  a running source, and an already registered destination.
- No VM name, UUID, address, account, host key, private path, or retained clone
  identity is committed. Candidate and seal selection remain ignored local
  configuration or command input.
- The candidate starts as a testbed-ready Windows installation with no
  `MachineControlRuntime` service, install root, provider process, artifact
  root, fixture process, or prior conformance state.
- One host command selects Windows ARM64 or x64 from the target architecture,
  publishes the self-contained package, verifies the pinned provider and
  license, installs it through the authenticated administration carrier,
  removes staging on success or failure, and returns a minimized readiness
  result.
- Installation is idempotent. A second run replaces only the owned service and
  runtime files, starts one automatic LocalSystem service, attaches one Medium
  helper to the interactive `Default` desktop, and exposes the adopted Cua and
  native-provider capabilities.
- A remote caller and a target-local Medium caller complete the same
  deterministic provider workflow after clean installation.
- A sustained real-application workflow controls Windows Calculator and
  Notepad through the resident facade. It uses bounded semantic observations,
  generation-scoped references where applicable, target-local input only when
  explicitly reported, and independent application or filesystem effects.
- The workflow performs multiple state transitions rather than a launch-only
  smoke test: calculation and display verification; document creation, save,
  close, reopen, edit or readback, and cleanup; exact-window capture and window
  lifecycle; plus bounded response and round-trip measurements.
- Service restart or revocation invalidates stale identity and returns to a
  ready Medium helper without outer input. A failed or repeated installation
  cannot leave a half-installed service or unbounded staging.
- The candidate contains no test document, screenshots, raw JSON, fixture
  process, conformance marker, or installer staging before sealing. UAC and
  testbed policy are unchanged.
- The candidate shuts down cleanly. The testbed retains one stopped sealed
  clone, boots it once in disposable mode, proves SSH, service, Medium helper,
  provider capability, and a bounded real-application smoke test, then shuts
  it down without persisting verification changes.
- The disposable candidate is removed only after the retained seal is
  independently verified. The original source appliance remains stopped and
  unmodified.

## Architecture under test

```text
authoritative stopped testbed base
  Windows + guest tools + SSH + authorized appliance login
                     |
                     | provider-owned stopped clone
                     v
             disposable build candidate
                     |
       publish/select/install/readiness command
                     |
          owned resident Windows runtime
             /                    \
 authenticated outside caller   target-local Medium caller
             \                    /
              Calculator + Notepad effects
                     |
          cleanup + clean guest shutdown
                     |
               provider-owned seal
                     |
       disposable boot + readiness/workload smoke
```

The seal is a stopped registered UTM clone, not an immutable distribution
artifact or a claim that Windows has been generalized with Sysprep. Disposable
verification supplies a non-persistent first-boot check. Image export,
cross-host distribution, activation generalization, and secret rotation remain
separate testbed concerns.

## Boundaries

- Do not destroy, reinstall, or mutate the configured source appliance. Clone
  it while stopped and perform all clean-state mutation on the candidate.
- Do not claim a fresh Windows OOBE installation. The current testbed documents
  one interactive administrator bootstrap for Windows, guest tools, and SSH;
  automating that base layer requires a separate testbed tactical.
- Do not use host/hypervisor pixels or input for product installation,
  readiness, application work, or verification. Hypervisor lifecycle and clone
  operations are authorized outer testbed responsibilities, not UI delivery.
- Do not rerun credential submission, weaken UAC, or expose appliance secrets.
  Use only the already authorized guest-local auto-logon of the dedicated
  source and its clones.
- Do not install another provider, YA worker, build toolchain, browser, or
  third-party application merely to create workload breadth. Use Windows inbox
  applications and the adopted Cua/native composition.
- Do not treat semantic dispatch as an effect. Calculator display state,
  Notepad file bytes, process/window disappearance, service state, and provider
  generation are the oracles.
- Do not persist raw screenshots or full UI trees in Git. Retain only minimized
  generic measurements in this tactical and delete target-local artifacts.
- Do not make the seal name or hypervisor clone identifier part of the product
  contract. The testbed owns target selection and private inventory.

## Implementation steps

### 1 — add safe clone and disposable lifecycle

Extend the authoritative UTM provider with a stopped-source `seal` operation
and a `disposable-up` operation. Add capability metadata, explicit validation,
and smoke tests. Keep destructive clone cleanup separately confirmed and bound
to an exact target.

### 2 — make bootstrap one reproducible command

Add a host-side bootstrap command that discovers target architecture,
publishes the matching package, verifies provider digest/license, transfers a
temporary archive, invokes the checked-in installer, probes service and Medium
readiness, and removes local and remote staging in a finally path.

### 3 — define clean baseline and readiness

Clone the stopped source to a private candidate. Start only the candidate,
remove the existing MachineControl installation and evidence, and independently
prove the clean baseline. Run the bootstrap command twice and verify
idempotency, exact package architecture, service recovery policy, provider
inventory, interactive helper integrity, and absence of leaked staging.

### 4 — implement a sustained inbox-application workflow

Create one repeatable suite over Calculator and Notepad. Discover real HWNDs,
use compact semantics, execute several application transitions, verify display
and file effects independently, capture exact windows, exercise window state,
close every created window, and report route, payload, latency, fallbacks,
round trips, focus, and cursor consequences.

### 5 — prove local and remote workflow parity

Run deterministic provider composition and the real-application suite through
the authenticated carrier. Launch the same suites from a target-local Medium
process through `app.launch`; allow only transport and measured latency to
differ.

### 6 — prove restart and reinstall recovery

Restart the owned service, reject stale generations, observe helper and Cua
recreation, and rerun a bounded application effect. Repeat the bootstrap
command and prove there is still one correct automatic service and no provider
or staging leak.

### 7 — clean and seal the candidate

Delete only workflow-owned documents, screenshots, evidence, markers, and
staging. Confirm no fixture or inbox-application process remains, retain the
installed runtime, verify UAC/testbed policy, and shut the candidate down
through the authoritative provider. Clone it to the private retained seal.

### 8 — verify the seal without changing it

Start the retained seal in disposable mode. Run testbed diagnostics, runtime
readiness, capability and package checks, and a bounded Calculator smoke test.
Cleanly shut it down so UTM discards the disposable overlay. Confirm stopped
state and remove the now-redundant candidate through an exact confirmed
testbed operation.

### 9 — close the Windows coordinating milestone

Update the testbed runbook, Windows topic, root runtime instructions, Tactical
000, this execution record, and tactical indexes. Record exact deviations and
remaining OOBE/distribution work without copying private inventory or raw
evidence into this repository.

## Validation plan

Use source/candidate/seal identities only in ignored local configuration and
target-local evidence. Commit generic scripts and redacted summaries. The
minimum durable result records:

- source, candidate, and seal lifecycle transitions without their names;
- clean-baseline absence checks;
- detected architecture and provider package digest agreement;
- first and second installation readiness;
- local and remote fixture/application outcomes;
- Calculator and Notepad operation counts, compact payloads, latency,
  fallbacks, and independent effects;
- restart, stale-generation, and reinstall behavior;
- pre-seal cleanup and policy state; and
- disposable seal verification and final retained/deleted lifecycle states.

## Validation record

Execution started on 2026-08-09. The source appliance was stopped before this
tactical began. UTM 4.7.5 exposes full stopped-VM clone and disposable-start
primitives, but `winvm-testbed` did not yet expose them through its lifecycle
contract. The current source is a valid testbed-ready base source but already
contains the adopted runtime; all clean-state proof will therefore occur only
after cloning and complete runtime removal on the candidate.


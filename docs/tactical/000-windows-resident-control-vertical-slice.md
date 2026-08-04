# Tactical 000: Windows Resident-Control Vertical Slice

Status: proposed; implementation has not started.

Topic: `windows-resident-control`

## Objective

Prove the North Star completely on Windows: an authorized outside agent and a
target-local process can use the same Windows-resident semantic, visual, input,
session, and administration contract without routine host-window control. The
resulting test appliance is bootstrapped and sealed reproducibly rather than
maintained as a manually curated prerequisite.

## Completion conditions

- Outside control does not require a Windows YA worker or focus the VM window.
- Local and remote callers receive the same capability and result semantics.
- UIA, guest-local capture/input, administration, session state, and the one
  justified protected path are represented honestly.
- Semantic references, observations, mutations, restart, revocation, and
  recovery pass deterministic conformance checks.
- The authoritative WinVM testbed retains lifecycle, bootstrap, outer recovery,
  and image/snapshot ownership.
- Automation validates, shuts down, and seals or snapshots the resulting image.

## Boundaries

- Do not freeze a universal cross-platform wire protocol in this slice.
- Do not make Cua, Computer Use, MCP, SSH, WinApp, or YA delegation the sole
  expression of the target-control contract.
- Do not expose UTM/QEMU input to the ordinary inside or outside control path.
- Do not build macOS and Linux implementations in parallel; record only the
  reusable contract evidence needed for their later slices.

## Implementation steps

### 1 — bootstrap a clean Windows test appliance

Create a clean installation through the authoritative WinVM testbed. Bootstrap
the stable resident service and interactive-session companion with minimal
routine console interaction. Define health checks that survive reboot and
distinguish service, administration, interactive-session, and semantic state.

### 2 — assemble the target-oriented facade

Compose capability/state discovery, UIA snapshots and actions, guest-local
screenshots and input, and administration behind one target-oriented contract.
Existing PowerShell, SSH, WinApp, and evaluated Cua mechanisms may remain
adapters; none becomes the product boundary by accident.

### 3 — prove remote direct control

Exercise the facade from an authenticated outside agent without spawning a
Windows agent. Verify that ordinary administration and desktop work neither
focuses UTM nor moves, captures, or types through the Mac host desktop.

### 4 — prove local contract parity

Call the same conceptual contract from a Windows-local process or YA worker.
Record only legitimate transport, latency, streaming, and artifact-transfer
differences; target vocabulary, capability meaning, and action results remain
the same.

### 5 — verify identity, evidence, and lifecycle behavior

Test snapshot-scoped references, process/window identity, explicit coordinate
spaces, paired semantic/visual observation epochs, delivery-versus-effect
results, stable refusal reasons, degraded capabilities, restart, cancellation,
lease expiry, and revocation.

### 6 — cover session and privilege boundaries

Exercise normal, elevated, locked, logged-out, user-switched, and secure-desktop
states. Add only the narrow protected route the dedicated test appliance
actually requires, with explicit arming and honest omissions.

### 7 — prove independent outer recovery

Disable or break resident control, emit a structured recovery request, and let
the controller use the authoritative outer provider to diagnose and repair it.
Verify that the failing target never holds the only recovery authority.

### 8 — evaluate optional in-target providers

Install YA and Computer Use in the guest when useful. Verify that they improve
selected local build, debug, or token-efficiency workflows without becoming a
prerequisite for outside semantic control.

### 9 — validate and seal the reproducible image

Run the deterministic fixture and conformance corpus, collect bounded evidence,
clean up temporary authority and artifacts, shut down the appliance, and let
the testbed seal or snapshot it as a reproducible output.

## Validation record

Not started. As slices execute, record exact commands and experiment evidence
in their owning implementation/testbed repository or in
`machine-control-spike`. Keep only the cross-provider result and links here.

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
- Start, taskbar, notification area, shell flyouts, Windows Settings, dialogs,
  and ordinary window management are controllable without host input.
- Exact-window identity, semantics, visual capture, action scope, delivery
  posture, and independently observed effect pass as separate dimensions.
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
- Do not treat control of one deterministic test application as proof of
  system-wide Windows control. The slice requires both fixture conformance and
  real Windows-shell acceptance.
- Do not build macOS and Linux implementations in parallel; record only the
  reusable contract evidence needed for their later slices.

## Implementation steps

### 1 — establish a baseline on the existing Windows VM

Inventory the current PowerShell/SSH, WinApp/UIA, screenshot, input, session,
and outer-recovery routes. Compare current Cua Driver and WinApp on one exact
window and the smallest Windows-shell path, using the criteria in the
[provider landscape](../../topics/provider-landscape.md). Run one deterministic
fixture through the existing healthy VM before combining facade design with
clean-install automation. Record real gaps rather than replacing working
adapters speculatively.

### 2 — assemble the target-oriented facade

Compose capability/state discovery, UIA snapshots and actions, guest-local
screenshots and input, and administration behind one target-oriented contract.
Current Cua Driver, WinApp, PowerShell, SSH, and any narrower native helper may
remain adapters; none becomes the product boundary by accident.

### 3 — drive the real Windows shell

Use a desktop-root UIA observation scope to inspect and control Start, taskbar,
notification area, shell flyouts, Windows Settings, ordinary dialogs, and
window state. The acceptance flow must:

- open Start, inspect it semantically, search, and launch an application;
- enumerate and activate taskbar applications;
- inspect the notification area and open representative flyouts;
- open Settings directly and through the shell, navigate semantically, change
  a harmless reversible setting, verify it independently, and restore it;
- move, minimize, maximize, switch, and close ordinary windows; and
- report UAC, lock/login, and secure-desktop boundaries honestly.

Use UIA first, then a native Shell/Win32 action, then guest-local keyboard or
pointer input with fresh visual evidence. Never turn a missing semantic node
into host-side input. Support compact observation scopes such as `start_menu`,
`taskbar`, `notification_area`, and one Settings window so system-shell control
remains token-efficient.

### 4 — prove remote direct control

Exercise the facade from an authenticated outside agent without spawning a
Windows agent. Verify that ordinary administration and desktop work neither
focuses UTM nor moves, captures, or types through the Mac host desktop.

### 5 — prove local contract parity

Call the same conceptual contract from a Windows-local process or YA worker.
Record only legitimate transport, latency, streaming, and artifact-transfer
differences; target vocabulary, capability meaning, and action results remain
the same.

### 6 — verify identity, evidence, and lifecycle behavior

Test snapshot-scoped references, process and native-window identity, owner
mismatch and recreation, exact-window semantics, compositor capture versus
desktop cropping, occlusion and minimization, explicit coordinate spaces,
paired semantic/visual observation epochs, background focus/z-order/cursor
invariants, delivery-versus-effect results, stable refusal reasons, degraded
capabilities, restart, cancellation, lease expiry, and revocation.

### 7 — cover session and privilege boundaries

Exercise normal, elevated, locked, logged-out, user-switched, and secure-desktop
states. Add only the narrow protected route the dedicated test appliance
actually requires, with explicit arming and honest omissions.

### 8 — prove independent outer recovery

Disable or break resident control, emit a structured recovery request, and let
the controller use the authoritative outer provider to diagnose and repair it.
Verify that the failing target never holds the only recovery authority.

### 9 — evaluate optional in-target providers

Install YA and Computer Use in the guest when useful. Verify that they improve
selected local build, debug, or token-efficiency workflows without becoming a
prerequisite for outside semantic control.

### 10 — reproduce, validate, and seal a clean image

Create a clean installation through the authoritative WinVM testbed. Bootstrap
the proven stable service and interactive-session companion with minimal
routine console interaction. Run the deterministic fixture, Windows-shell
acceptance, and conformance corpus; collect bounded evidence; clean up temporary
authority and artifacts; shut down; and let the testbed seal or snapshot the
image as a reproducible output.

## Validation record

Not started. As slices execute, record exact commands and experiment evidence
in their owning implementation/testbed repository or in
`machine-control-spike`. Keep only the cross-provider result and links here.

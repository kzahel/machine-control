# ChromeOS Closed-Lid Readiness

Status: in progress

Owning topics:

- [`target-lifecycle-and-readiness`](../../topics/target-lifecycle-and-readiness.md)
- [`platform-notes`](../../topics/platform-notes.md)

## Objective

Make closed-lid SSH availability a required invariant of the dedicated
ChromeOS test appliance. Preserve read-only diagnostics, install and reapply
the policy through the existing bootstrap and maintenance boundary, and prove
that an ordinary reboot leaves the closed device reachable without VT2.

## Completion conditions

- Bootstrap disables inactivity and lid-close suspend using ChromeOS's
  documented stateful powerd preferences and embedded-controller override.
- The stateful SSH boot path reapplies the controller override and records
  current-boot evidence before accepting remote work.
- A powerd-start guard reapplies the baseline after an in-boot power-manager
  reset, and audit requires that guard.
- Restoring stock sleep behavior is refused unless the caller supplies an
  explicit acknowledgement after a user-authorized opt-out request.
- Routine and common doctor report a required minimized closed-lid check
  without changing power state.
- Post-update audit reports helper installation, effective preferences, and
  current-boot application independently.
- Safe active-image repair installs missing power policy without reboot;
  pending-update and read-only-rootfs recovery retain their existing guided
  VT2 refusal boundary.
- Fixtures cover ready, missing-policy, repair, and reboot-proof states.
- Live validation repairs the accepted Chromebook, observes a changed-boot
  proof, and confirms SSH remains reachable after the physical lid closes.

## Boundaries

- Do not make `doctor` or `maintenance audit` mutate the target.
- Do not block SSH recovery merely because power-policy application failed;
  start SSH and report the required failure so repair remains possible.
- Do not treat closed-lid readiness as permission to power on a fully-off
  device or weaken update/rootfs recovery gates.
- Keep the dedicated appliance ventilated and preferably on AC because this
  profile intentionally disables ChromeOS's normal lid safeguard.

## Work

### 1 — promote closed-lid availability to required readiness

Add platform and common doctor checks plus minimized maintenance projection
for the helper, stateful preferences, and current-boot application evidence.

### 2 — make bootstrap and repair own policy application

Install a stateful policy helper, apply it during bootstrap, invoke it from
automatic and manual SSH startup, and let ordinary safe-image repair converge
missing policy without an implicit reboot.

### 3 — defend the baseline from cleanup and in-boot resets

Treat always-awake as permanent appliance state in agent instructions, gate
the exceptional stock-power opt-out, and reapply policy after powerd starts.

### 4 — prove behavior and publish current truth

Run dependency-free fixtures, Bash and Python checks, portable validation, a
live repair and reboot, then close the physical lid and verify bounded SSH and
doctor reachability before recording the result.

## Validation

- `python3 -m unittest discover -s platforms/chromeos/tests -v`
- `bash -n platforms/chromeos/bin/chromeos platforms/chromeos/scripts/*.sh`
- `python3 -m py_compile platforms/chromeos/scripts/*.py`
- `python3 bin/check --portable`
- live common doctor and maintenance audit/repair
- one explicit proof reboot
- physical closed-lid SSH and common-doctor observation

## Result

Implementation and non-physical live validation are complete. No-reboot repair
restored the required policy after an observed stock-power reset and installed
the powerd-start guard. A bounded live `powerd` restart produced current-boot
`powerd-started` success evidence, after which all 13 maintenance checks and
the common doctor were healthy; effective lid behavior was ignored and idle
action was no-op. The controller-side stock-power command now refuses without
the explicit make-unavailable acknowledgement.

Physical closed-lid confirmation remains pending because no person was present
at the appliance. No additional proof reboot was performed for this hardening.

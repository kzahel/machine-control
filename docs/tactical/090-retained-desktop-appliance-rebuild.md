# Retained Windows and Linux appliance rebuild

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[VM workspaces and storage policy](../../topics/vm-workspaces-and-storage-policy.md).

Status: active; analysis implemented, fresh appliance acceptance pending.

## Objective and completion conditions

The operator requested cleanup of a selected legacy Windows factory export,
reusable disk-prune analysis, and retained usable Windows and Linux VMs. Finish
with exact private registry bindings, canonical mode-0600 guest-verified login
credentials, SSH and the target-native resident installed and started by
default, proven semantics/capture/input, cold-boot recovery, and released
claims. Retain the newly accepted appliances during test cleanup.

## Boundaries

Private identity, configuration, artifacts and credentials stay out of Git.
Analysis is read-only and does not infer orphan status. The dedicated
appliance profile supplies full authorized resident control; workstation
desktop grants are a distinct profile. Use explicit outer recovery only for
an observed unavailable inner route with the appropriate disruptive claim.
Provisioning does not authorize disabling protected-desktop policy.

## Ordered work

### 1 — inspect storage and remove the selected artifact

Measure logical and allocated storage, include legacy factory exports, retain
coverage and shared-extent uncertainty. Remove only the selected unused export
and matching manifest, then remeasure free space.

### 2 — make precreation reachable

Expose existing factory preflight/create and exact inventory-bootstrap commands
through the common CLI before a target can have a claim. Keep guest operations
fenced and unused-destination guards in the adapters. An independently
confirmed empty UTM inventory must permit first creation.

### 3 — provision and retain the appliances

Verify official media, render seed inputs from stored credentials or public
keys, create unused targets, pin and doctor, then claim. Advance stage reports
through administration, credential establishment/verification, bootstrap,
seed detachment, disk-only cold boot and observed effects. Record readiness
only after evidence succeeds. Retain targets and release claims.

### 4 — leave repeatable recipes and validate

Document the common stages and repair concrete live gaps. Run focused,
platform and appropriate resident checks. Keep exact evidence private and
public results generic.

## Current result

The unused export and manifest were removed; the private volume measurement
observed the expected storage increase. Offline storage analysis and packaging
are implemented, with sparse-file, hardlink, overlapping-root, scan-bound and
offline-CLI tests. Fresh appliance acceptance remains in progress.

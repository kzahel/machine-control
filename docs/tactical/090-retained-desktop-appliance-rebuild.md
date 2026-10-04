# Retained Windows and Linux appliance rebuild

Topics: [operational-workflow-automation](../../topics/operational-workflow-automation.md),
[VM workspaces and storage policy](../../topics/vm-workspaces-and-storage-policy.md).

Status: complete; retained ARM64 Windows and Linux appliances accepted on a
macOS controller.

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

## Final result

The selected unused legacy Windows export and matching manifest were removed.
The allocated measurement was about 53 GiB, with an independently observed
volume-space increase. Offline disk-image analysis is packaged in the common
CLI; sparse capacity, allocated storage, overlapping roots, hardlinks, secret
directory exclusion and scan/result bounds are covered. It does not declare
unregistered images orphaned or estimate exclusive APFS reclaimability.

Fresh retained Windows 11 Pro ARM64 and Ubuntu 24.04 ARM64 GNOME appliances
were created from official media through the common CLI. Ubuntu's detached
signature and publisher digest passed. The Windows artifact matched a
publisher-listed whole-file digest, but its locale row was inconsistent with
the selected download; read-only image metadata independently proved English
Pro ARM64. This discrepancy is preserved in the private media receipt rather
than reported as a matching English checksum.

Both exact provider identities and development/ready-base bindings are in the
private controller inventory. Canonical mode-0600 passwords were verified
against each guest. Linux now establishes the password on a locked key-only
bootstrap account; Windows's setup password was rotated and verified before
handoff. Source setup seeds and the derived installer copy were removed after
media detachment and disk-only cold-boot proof. Verified official source media
remains cached for future rebuilding.

Both residents start automatically. Linux uses explicitly selected UUID-pinned
key-only SSH administration, preserving UTM lifecycle and exact identity.
Windows bootstrap, login and maintenance now use the same claim-checked direct
provider carrier as ordinary administration. The Windows dedicated appliance
broker proved stored-password login across Winlogon after cold boot; this is
separate from workstation desktop-product grants.

Both common desktop conformance runs passed outside/local generation parity,
semantic fixture effects and capture/artifact retrieval. Linux additionally
passed Unicode input and the platform smoke's pointer, drag, scroll, keyboard,
application lifecycle and file-transfer oracles. Windows independently proved
native pointer delivery through its fixture counter with no host interference.
Its development post-update audit was healthy after the disk-only boot.

Portable checks, Linux static checks with 42 unit tests, Windows Python tests
with 19 cases, and the controller ARM64 runtime publish passed. Windows's
native shell suite also passed after its fixtures were adjusted to provide
exact fake provider identity and accept carrier options before SCP operands.

Both appliances remain running and retained. Successful validation scopes
released their claims; no VM was discarded as factory-test cleanup. Exact
identities, credentials, claim receipts and captures remain private.

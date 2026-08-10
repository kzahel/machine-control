# Tactical 007: Windows ISO Factory Acceptance

Status: active.

Topic: `windows-resident-control`.

Precursor:
[`006-windows-safety-launch-efficiency-and-image-factory.md`](006-windows-safety-launch-efficiency-and-image-factory.md).

## Objective

Close Tactical 006's exact unexecuted boundary by creating a disposable
Windows ARM64 appliance from Microsoft's current public multi-edition ISO,
without a product key or activation. Prove unattended Setup, driver and
network viability, first-logon SSH bootstrap, installation-media removal,
MachineControl installation, target-native acceptance, and stopped cleanup
through the authoritative Windows testbed.

This is acceptance of the factory path, not a request to retain another large
golden image. The already verified generalized export remains authoritative
unless the fresh build exposes a defect that requires replacing it.

## Completion conditions

- The ISO is downloaded from Microsoft's official public ARM64 channel into
  ignored private factory storage and its SHA-256 digest is checked against
  Microsoft's published value.
- The selected Windows edition is resolved from the actual image catalog,
  installed without a product key, and reported honestly as unactivated.
- The answer-media renderer and UTM creation recipe work against the live ISO;
  Setup reaches the configured local session without host-driven routine UI.
- Required storage, network, and guest-agent drivers are available early
  enough for first-logon bootstrap and deterministic target discovery.
- OpenSSH starts with public-key authentication, the setup credential is
  rotated without disclosing it, and answer/install media are detached before
  ordinary operation.
- The candidate is identity-pinned before mutation. MachineControl installs
  through target-attested bootstrap and passes health plus representative
  semantic, visual, input, window, and cleanup acceptance locally and
  remotely.
- Temporary credentials, media, screenshots, host keys, and the disposable
  candidate are removed or placed in ignored private storage. Any retained
  target is stopped, and both repositories are clean.

## Boundaries

- Use the normal public Windows 11 ARM64 multi-edition ISO. Do not use a
  subscription-only image, embed a product key, activate Windows, or claim an
  evaluation entitlement that was not selected.
- Never commit the ISO, answer media, passwords, account names, target names,
  UUIDs, addresses, host keys, screenshots, or private bundle paths.
- Do not mutate or persistently boot the retained seal or generalized export.
- Initial outer observation is permitted for installer diagnosis, but routine
  control after bootstrap must be target-native.
- Do not retain a second full export merely to satisfy this tactical. Export
  only if live evidence shows the existing authoritative artifact must be
  replaced and local storage can hold it safely.
- A reachable SSH port is not sufficient acceptance. Prove the resident
  facade and independently observed application effects.

## Implementation steps

### 1 — acquire and inspect official installation media

Download the current public English ARM64 ISO, verify its Microsoft-published
digest, validate its partition map, and inspect its image catalog. Replace
hard-coded image assumptions with catalog-based selection if necessary.

### 2 — make first boot self-sufficient

Audit the UTM recipe and answer media against the live ISO. Supply only the
drivers and guest tooling needed for unattended disk, network, deterministic
target discovery, and SSH bootstrap. Keep all generated media private.

### 3 — install and establish resident access

Create a uniquely pinned candidate, let Windows Setup and first logon run,
prove public-key SSH, rotate the setup credential, detach installation media,
and reboot without relying on a visible VM window for ordinary control.

### 4 — install and accept MachineControl

Bootstrap the checked-in product through the candidate assertion. Run health,
provider, protected-boundary, and a representative real-application workflow
from authenticated-remote and target-local placements. Record routes and
independent effects, then remove acceptance artifacts.

### 5 — clean up and close the boundary

Stop and delete the exact disposable candidate under the role/UUID guards,
remove temporary credentials, answer media, ISO, host keys, and captures, and
update the Windows topic, Tactical 006 boundary note, testbed runbook, and this
record with measured results and any remaining limitation.

## Validation record

Pending live execution.

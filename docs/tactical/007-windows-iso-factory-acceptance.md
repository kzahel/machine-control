# Tactical 007: Windows ISO Factory Acceptance

Status: complete.

Topic: `windows-resident-control`.

Precursor:
[`006-windows-safety-launch-efficiency-and-image-factory.md`](006-windows-safety-launch-efficiency-and-image-factory.md).

## Objective

Close Tactical 006's exact unexecuted boundary by creating a disposable
Windows ARM64 appliance from Microsoft's current public multi-edition ISO,
without a customer activation key or activation. Microsoft's public
installation-only Pro setup key may select the intended catalog edition but
must not be described as an activation entitlement. Prove unattended Setup,
driver and network viability, first-logon SSH bootstrap, installation-media
removal, MachineControl installation, target-native acceptance, and stopped
cleanup through the authoritative Windows testbed.

This is acceptance of the factory path, not a request to retain another large
golden image. The already verified generalized export remains authoritative
unless the fresh build exposes a defect that requires replacing it.

## Completion conditions

- The ISO is downloaded from Microsoft's official public ARM64 channel into
  ignored private factory storage and its SHA-256 digest is checked against
  Microsoft's published value.
- The selected Windows edition is resolved from the actual image catalog,
  installed without a customer activation key, and reported honestly as
  unactivated.
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

Completed 2026-08-10.

### Official media and unattended installation

Microsoft's public English Windows 11 25H2 multi-edition ARM64 ISO was stored
only in ignored private factory storage. Its published SHA-256 was verified
before use and reverified unchanged before deletion. Catalog inspection
selected index 3, Windows 11 Pro. The renderer used Microsoft's public Pro KMS
client setup key only to select that edition, suppressed automatic activation,
and installed ARM64 build 26200 in unactivated notification state. No customer
activation key was accepted or used.

The official source ISO was preserved. A private copy replaced only the
byte-verified prompted loader inside the firmware-visible El Torito image with
Microsoft's equal-size signed no-prompt loader from the same ISO. Live
iteration also established that UTM firmware reads a direct FAT boot volume
but not the seed data ISO, while Windows Setup reads the seed ISO but does not
accept the direct FAT volume as answer media. The final factory therefore used
three explicit removable devices: prepared installer, data seed, and a small
firmware boot image.

A blank UUID-pinned candidate entered unattended Windows Setup without guest
input. The answer file selected the edition and disk, injected VirtIO storage,
network, serial, balloon, and guest-agent drivers into both Windows PE and the
offline image, created the one-use local account, and suppressed the routine
OOBE pages. At the expected firmware stop after Setup's disk phase, no guest OS
was available for graceful shutdown; a separately authorized, UUID-bound
outer force stop allowed the guarded installer-only detachment. Both seed
devices were independently still present. The next boot completed
specialization, OOBE, one-time login, and guest-tools installation without
host-driven guest UI.

### Fresh-media corrections

The run exposed a real OpenSSH packaging edge. Fresh Windows OpenSSH 9.5
generated valid host keys but left explicit access for the setup administrator;
`sshd` rejected every private key and exited with 1067. The checked-in
bootstrap now rebuilds each host-key ACL using the well-known SYSTEM and
Administrators SIDs before validating and starting the service. The repair was
applied to the fresh candidate, `sshd` started, the final bootstrap wrote its
normal receipts, key-only SSH worked, and password SSH remained disabled.

The first real-application rerun exposed another honest Windows split: current
Calculator can place UI content in the activation process while
`ApplicationFrameHost` owns the full lifecycle frame. `app.activate` now
reports a stable primary content window and an associated frame window. The
workflow uses the content HWND for native UIA and the frame HWND for full
capture and lifecycle instead of treating one incomplete HWND as universal.

### Resident acceptance

The one-use setup credential was rotated through a private file and removed
from the target without appearing in an argument or durable evidence.
Target-attested bootstrap installed MachineControl as an automatic LocalSystem
service with a Medium ordinary helper, pinned Cua 0.17, and the native Windows
provider.

Default UAC policy remained intact: UAC enabled, administrator consent behavior
5, and secure desktop enabled. The live suite originated elevation from the
Medium fixture, cancelled and approved genuine `Winlogon` prompts through
target-native semantics/input and input-desktop capture, and independently
confirmed the High-integrity effect.

Both authenticated-remote and target-local workflows passed Calculator,
Settings, Character Map, and Notepad. They confirmed native package activation,
classic launch, semantic mutation, persisted and reopened file bytes, exact
capture, four Calculator state transitions, pre-existing-state preservation,
and owned-artifact cleanup. Remote Calculator compact/unchanged ratios were
0.702/0.060 and target-local ratios were 0.694/0.053; Settings measured
0.773/0.256 in both placements.

### Disk-only recovery and cleanup

The stopped media guard removed the two remaining seed devices and observed
zero removable drives. After disk-only reboot, key-only SSH and the protected
resident route were available before login on `Winlogon` as LocalSystem. The
rotated password passed the stock Credential Provider in one target-native
request. The ordinary `Default` helper then returned at Medium integrity, and
system input, Run-dialog semantics, and target-native capture still worked.

The exact candidate was stopped and UUID-confirmed before deletion. The prior
testbed target selection and SSH host-key file were restored byte-for-byte.
The official ISO, prepared copy, both seed images, one-use credentials,
captures, and acceptance artifacts were deleted. The existing generalized
export and manifest were not modified and remain stopped. Final ARM64 and x64
runtime builds, bootstrap target-safety tests, and both testbed suites pass.

The authoritative command-level record and media architecture live in the
testbed's
[`image-factory.md`](../../platforms/windows/docs/image-factory.md).

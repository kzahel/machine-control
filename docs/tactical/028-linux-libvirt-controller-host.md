# Tactical 028: Linux Libvirt Controller Host

Status: complete.

Topics: [`vm-workspaces-and-storage-policy`](../../topics/vm-workspaces-and-storage-policy.md),
[`target-lifecycle-and-readiness`](../../topics/target-lifecycle-and-readiness.md),
[`cross-platform-coordinator`](../../topics/cross-platform-coordinator.md),
[`windows-resident-control`](../../topics/windows-resident-control.md), and
[`linux-resident-control`](../../topics/linux-resident-control.md).

## Objective

Add and live-validate a Linux controller-host provider that uses system
libvirt over QEMU/KVM to provision and operate native x86_64 Windows 11 and
Ubuntu GNOME Wayland appliances. Preserve the existing target-resident
Windows and Linux contracts while changing lifecycle, bootstrap, recovery,
and workspace ownership from UTM/macOS to libvirt/Linux.

Hardware virtualization is mandatory. The provider must refuse before start
or provisioning when the resolved domain would use QEMU software emulation,
an architecture other than x86_64, or a non-KVM libvirt domain type.

## Completion conditions

- A shared Linux/libvirt provider owns exact domain identity, guarded
  lifecycle, storage, guest-agent transport, recovery capture/input, and
  QCOW2 workspace operations without making `virsh` output part of the public
  contract.
- Host capability discovery proves x86_64, `/dev/kvm` access, a `kvm` domain,
  QEMU's KVM accelerator, suitable Q35/UEFI firmware, and the configured
  libvirt network and storage pool before any domain mutation.
- Start and workspace acquisition re-read provider-native XML and refuse
  architecture, domain type, emulator, machine, source-role, identity, or
  acceleration mismatches.
- A native x86_64 Windows 11 appliance boots with Q35 UEFI, Secure Boot,
  emulated TPM 2.0, VirtIO storage/network, QEMU guest agent, hardened
  OpenSSH, and the existing Windows resident runtime.
- A native x86_64 Ubuntu 24.04 GNOME Wayland appliance boots with VirtIO
  devices, QEMU guest agent, SSH, and the existing Linux resident, AT-SPI,
  capture, and input services.
- Both targets expose the existing common doctor and desktop contracts
  locally and remotely without focusing or manipulating a host console during
  ordinary control.
- Provider capture and bounded keyboard/pointer input remain explicit outer
  bootstrap/recovery routes and can be prohibited during ordinary acceptance.
- Persistent workspaces reuse the pinned development domain. Isolated
  workspaces use provider-owned transient domains with QCOW2 backing overlays
  and receipt-bound cleanup. Candidate retention, source protection, capacity
  preflight, and last-ready-base protection fail closed.
- Private inventory declares the Linux controller routes, concrete domain
  UUIDs, storage/network selectors, transport endpoints, roles, and policy
  without committing any of them to this public repository.
- Claims bind to exact provider identity and gate every meaningful accepted
  target operation, including workspace release.
- Live readiness, workspace outcome, reboot persistence, target-native
  conformance, host non-interference, and clean stopped-base state are
  recorded at the appropriate evidence level.

## Boundaries

- Support only native x86_64 guests on this x86_64 host. Do not import or
  emulate the existing ARM64 UTM appliances.
- Do not provide or silently fall back to TCG, a `qemu` domain type, a
  cross-architecture emulator, or an unaccelerated install path.
- Do not virtualize macOS or move iOS controller-host responsibilities away
  from an authorized Mac.
- Do not expose arbitrary host root commands, arbitrary libvirt provider
  dispatch, private storage paths, domain names or UUIDs, network addresses,
  credentials, ISO metadata, or workspace receipts through normalized output.
- Do not use a personal downloads directory as provider storage. Use a
  dedicated libvirt pool with explicit capacity policy and private concrete
  configuration.
- Do not make virt-manager, a visible SPICE console, or host pointer/keyboard
  injection part of ordinary application testing. They are human bootstrap
  and explicit recovery surfaces only.
- Do not weaken Windows Secure Boot, TPM, UAC, secure desktop, credential,
  lockout, or guest firewall policy to simplify provisioning.
- Do not treat successful guest-agent, SSH, input, or semantic calls as proof
  of effect without the existing independent target or fixture observations.

## Ordered work

### 1 — capture the authorized host baseline

Record a minimized, read-only Linux-host capability result and deterministic
fixtures for supported and refused configurations. Validate KVM access,
libvirt system connection, Q35/OVMF, Secure Boot, TPM 2.0, network, storage,
and available capacity without publishing concrete host inventory.

### 2 — implement exact libvirt lifecycle

Add a shared provider core and thin Windows/Linux adapter integration. Resolve
domains by private UUID, validate XML and role before mutation, implement
status/start/clean shutdown/reboot, and report actual provider route and outer
effects. Require KVM and x86_64 again at every start boundary.

### 3 — implement administration and recovery transport

Use typed QEMU guest-agent operations for bootstrap and bounded recovery, then
retain each platform's existing SSH/resident route for ordinary work. Add
provider-native display capture and explicit recovery input with normalized
coordinates, generation checks, and the existing outer-UI prohibition.

### 4 — implement QCOW2 workspaces

Map persistent intent to the pinned development domain and isolated intent to
a transient KVM domain with an adapter-owned QCOW2 backing overlay. Bind every
derivative to a private receipt and fresh source/derivative UUIDs. Prove safe
release, failed-release retention, capacity refusal, source protection, and
absence of guest changes after discard.

### 5 — provision the Windows x86_64 appliance

Build from an official native x86_64 Windows 11 ISO and separately verified
VirtIO media. Use Q35, enrolled-key Secure Boot firmware, TPM 2.0, and only
KVM acceleration. Adapt the unattended factory and guest-driver preparation,
bootstrap the resident/runtime profile, pin the exact candidate privately,
and prove stopped generalized or controller-ready image state as selected by
the existing appliance policy.

### 6 — provision the Linux x86_64 appliance

Build an Ubuntu 24.04 GNOME Wayland x86_64 guest with the same display
contract as the accepted Linux appliance. Bootstrap the QEMU agent and
target-resident runtime, pin the exact candidate privately, and prove the
AT-SPI, capture, input, fixture, and reboot contracts.

### 7 — wire private controller inventory

Add Linux-eligible Windows and Linux routes to the canonical private dotfiles
inventory. Keep concrete domain, pool, volume, network, endpoint, account, and
authorization values private. Validate registry projection on Linux without
changing the existing macOS routes or controller eligibility.

### 8 — prove end-to-end acceptance

Run portable/native checks, provider fixtures, libvirt host doctor, exact
target doctor, claims, persistent and isolated workspaces, changed-boot
readiness, Windows and Linux resident conformance, and explicit recovery.
Keep host-console routes absent during ordinary tests, release claims in
finally-style cleanup, leave accepted bases stopped, and update current topics
and platform reports with only minimized evidence.

## Validation

- `python3 bin/check --portable`
- `python3 bin/check --native`
- provider fixture tests for KVM-only validation, identity, lifecycle,
  transport, recovery prohibition, capacity, overlay creation, and cleanup;
- `virt-host-validate qemu` plus a provider-owned minimized host doctor;
- private-inventory tests on Linux and the existing controller matrix;
- read-only common doctor before every accepted-target use;
- claim acquisition, renewal where necessary, and prompt release for every
  live accepted-target operation;
- Windows x86_64 native builds, appliance certification, and resident
  application acceptance;
- Linux native checks, appliance certification, smoke tests, and GNOME
  acceptance; and
- stopped exact-domain and empty temporary-receipt assertions after each live
  validation.

## Result

Complete. The initial authorized-host audit found working AMD-V/KVM, libvirt
system services, Q35/OVMF with enrolled Secure Boot keys, emulated TPM 2.0, a
provider network, and sufficient dedicated-pool capacity. The implemented host
doctor minimizes those observations. The shared provider validates the exact
UUID and native x86_64 KVM/Q35 domain shape before lifecycle or derivation and
has no TCG or cross-architecture fallback. Fixture tests cover identity,
security devices, guest-agent transport, recovery input, factory media,
capacity, and receipt-bound QCOW2 derivation.

The Linux route provisioned a separate Ubuntu 24.04 GNOME Wayland appliance
from the official x86_64 cloud image. Development bootstrap, maintenance,
changed-boot exact-source certification, common target-native conformance, and
an isolated overlay outcome passed. Local and outside calls used the same
resident generation, independently observed semantic and Unicode effects, and
left outer UI prohibited. Release removed the exact derivative and overlay.

The Windows route provisioned a separate native x86_64 Windows 11 appliance
from official installation media and separately verified VirtIO media. Q35
UEFI Secure Boot, TPM 2.0, VirtIO storage/networking, QEMU guest agent,
hardened key-only OpenSSH, native PowerShell, the development toolchain, and
the resident/provider composition passed. Appliance certification observed a
reboot, verified the exact committed archive, ran portable and Windows-native
checks in the guest, removed staging, and shut down cleanly. All installer and
seed attachments were then removed and deleted from provider storage.

A disk-only Windows boot reached the stock locked Winlogon state without
persistent auto-logon. The protected resident reported native semantics,
capture, and input ready with no host interference. Its dedicated one-shot
secret route entered the ordinary desktop, where full doctor passed. An
isolated QCOW2 workspace repeated the protected and ordinary readiness paths,
matched local/outside generations, produced an independently observed Cua
fixture effect and exact window capture, and was discarded through its
claim-bound receipt. Generated answer media and the setup secret were removed
after acceptance.

Headless QMP capture and bounded keyboard/text were exercised only during
bootstrap/recovery; ordinary acceptance prohibited every outer route. Pointer
normalization and bounded delivery remain fixture-covered. Private inventory
contains all concrete domains, UUIDs, storage/network selectors, transports,
roles, proof flags, and receipts. No such value entered this repository.

Final controller validation passed the root portable and Linux-native checks,
Windows smoke and target-safety suites, the Linux-native Windows factory test,
and all 22 shared libvirt provider tests. Both accepted bases are stopped,
claims are available, temporary workspace inventories are empty, and no
factory removable media remains attached.

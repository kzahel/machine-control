# Controller-host support

This guide covers VM hosting and device-controller eligibility. Desktop app
downloads for the computer you use are listed on the
[download page](https://machinecontrol.dev/downloads/).

The **target platform** is the OS being controlled. The **controller host** is
the machine that executes the selected adapter and is physically or logically
attached to its hypervisor or device. These are independent: coordinator code
running on Linux is not by itself a Linux-hosted route to a Windows VM.

The common coordinator and its fixture-backed checks run on macOS, Linux, and
Windows. Live desktop-VM hosting remains provider-specific:

| Controller host | Coordinator evidence | Live-tested desktop VM routes | Planned desktop VM routes |
| --- | --- | --- | --- |
| macOS | Portable and native checks; current live controller | UTM/QEMU for Windows and Linux; Tart for macOS | Current baseline |
| Linux | Portable and native checks plus exact-source execution inside both native guests | libvirt with QEMU/KVM for native x86_64 Windows and Linux guests | Broader host and guest-profile coverage |
| Windows | Hosted CI, native runtime builds and experimental host execution | Experimental VirtualBox guests on Home; protected Windows base and development copy | VirtualBox factory/isolated workspaces; unassisted lifecycle; QEMU/WHPX blocked on Windows 11 TPM; Hyper-V remains a candidate on eligible editions |

The Linux row is live-accepted only for native x86_64 KVM domains. Its provider
refuses software emulation and cross-architecture domains before start or
derivation. The Windows row has an opt-in local adapter and bounded Linux
resident evidence, not a supported production factory/workspace provider.
Each new provider must independently
prove exact target identity, guarded lifecycle, administration, workspace
isolation and cleanup, resident desktop conformance, explicit recovery, and
host non-interference before being documented as supported.

macOS guests remain on Apple hardware. A Linux or Windows caller will reach a
physical Mac, its target-resident controller, or an Apple-hosted Tart provider
through an authenticated remote route; the plan does not emulate macOS under
KVM or Hyper-V. Device routes have their own controller-host constraints—iOS,
for example, requires an authorized Mac—so `machine-control targets` reports
eligibility for the concrete selected route rather than inferring it from the
target OS.

The provider direction and adoption gates are maintained in
[`vm-workspaces-and-storage-policy.md`](../topics/vm-workspaces-and-storage-policy.md),
while coordinator-versus-route portability is maintained in
[`cross-platform-coordinator.md`](../topics/cross-platform-coordinator.md).

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
| Linux | Portable and native checks plus exact-source execution inside Windows and Linux guests | libvirt with QEMU/KVM for x86_64 Windows and Linux. Bounded [Intel Tahoe on Quickemu and libvirt/KVM](../platforms/macos/docs/intel-kvm.md) | Automated Intel macOS installation from media. Broader host and guest-profile coverage |
| Windows | Hosted CI, native runtime builds and experimental host execution | Experimental VirtualBox guests on Home; protected Windows base and development copy | VirtualBox factory/isolated workspaces; unassisted lifecycle; QEMU/WHPX blocked on Windows 11 TPM; Hyper-V remains a candidate on eligible editions |

The Linux libvirt provider requires native x86_64 KVM domains before start or
derivation. Intel macOS uses exact disk identity for a retained Quickemu VM
and libvirt UUID identity for an independent base and its workspaces.
Both use pinned SSH. The Windows row has an opt-in local adapter and bounded Linux
resident evidence. Full factory and workspace support requires independent
proof of exact identity, guarded lifecycle, administration, workspace isolation
and cleanup, resident desktop conformance, explicit recovery, and host
non-interference.

The established Apple-silicon macOS guest route uses Tart. Linux can also host
the bounded Intel Tahoe profile using KVM acceleration. Device routes have
their own controller-host constraints. iOS requires an authorized Mac.
`machine-control targets` reports eligibility for each concrete route.

The provider direction and adoption gates are maintained in
[`vm-workspaces-and-storage-policy.md`](../topics/vm-workspaces-and-storage-policy.md),
while coordinator-versus-route portability is maintained in
[`cross-platform-coordinator.md`](../topics/cross-platform-coordinator.md).

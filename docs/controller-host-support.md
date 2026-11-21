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

## Prepare a Linux KVM controller

For the Linux and Windows image factories on Ubuntu, install QEMU/KVM, system
libvirt, `virt-install`, the OS information database, OVMF, and the QEMU SPICE
module. The Windows factory also needs `swtpm` and Windows ISO tools. The
Windows resident bootstrap builds with the full .NET 8 SDK and
[pinned shared runtime dependencies](../runtime/README.md). The Ubuntu
factory uses `cloud-localds` to render NoCloud media. See the
[Ubuntu factory guide](../platforms/linux/docs/bootstrap.md#native-x86_64-libvirt-image-factory)
and [Windows factory guide](../platforms/windows/docs/image-factory.md) for
the complete media and guest setup sequence.

Check that the controller account can access `/dev/kvm` and run
`virsh -c qemu:///system list --all` in a new login session. Configure an
active libvirt network and a dedicated directory pool. The controller account
needs write access to the configured pool path to stage images. The libvirt
QEMU account also needs directory traversal access along that path. On an
Ubuntu controller using a private pool, an execute-only ACL for the
`libvirt-qemu` user on the pool directory can provide that access while keeping
the directory private. Check the libvirt journal if the factory defines the
domain successfully and the first start is refused.

## Verify an existing desktop baseline

Run these commands on the controller that owns the selected VM. From another
machine, use the controller's authenticated SSH route to run the same CLI.

```bash
bin/machine-control targets
bin/machine-control inventory credentials TESTBED
bin/machine-control --target TARGET target doctor
```

An off VM can have a valid identity and an unavailable resident. Use the
[claimed readiness workflow](cli-guide.md#set-up-a-controller) to start
it, then repeat doctor after the guest has finished booting. Live desktop
readiness requires the guest administration route, resident, and applicable
desktop capabilities to be ready. On a provisioned Windows appliance at
Winlogon, use the [stored-password login command](../platforms/windows/README.md#what-survives-a-reboot)
under the same claim, then repeat doctor.

For a stronger smoke test, open a fixture
on the unlocked desktop and check a native button action against its
guest-side result. Keep the snapshot and action within one
[Desktop control stream](cli-guide.md#inspect-and-control-a-desktop)
so the action can use the observed reference.

The provider direction and adoption gates are maintained in
[`vm-workspaces-and-storage-policy.md`](../topics/vm-workspaces-and-storage-policy.md),
while coordinator-versus-route portability is maintained in
[`cross-platform-coordinator.md`](../topics/cross-platform-coordinator.md).

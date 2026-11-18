# Quickemu and OpenCore

Quickemu is an [MIT-licensed launcher](https://github.com/quickemu-project/quickemu/blob/master/LICENSE)
for QEMU VMs. QEMU's [top-level license](https://gitlab.com/qemu-project/qemu/-/blob/master/COPYING)
is GPL-2.0 with additional component terms. OpenCorePkg declares
[BSD-3-Clause](https://github.com/acidanthera/OpenCorePkg/blob/master/LICENSE).
Firmware, bundled third-party components, and Apple installation media carry
their own terms. Machine Control's adapter uses the installed launcher and QEMU
protocols. Its distribution includes none of these images or binaries.

**Current, source-reviewed:** Quickemu selects the OpenCore image separately
from its macOS system disk. It starts QEMU with a recoverable private firmware
and disk layout. The QMP socket exposes running state, KVM acceleration,
block devices, framebuffer capture and absolute tablet input. Loopback VNC
provides an independent console for early login and keyboard input.

**Current, live-tested:** one x86_64 Tahoe guest runs under KVM and retains
separate QCOW2 disk roles. The owned adapter binds QMP observations to the
local QEMU process and the two pinned file identities. The native resident
keeps its existing macOS Desktop permission model and is reached over pinned
SSH. See the [platform guide](../../platforms/macos/docs/intel-kvm.md) for the
deployment contract and the limits of libvirt reuse.

**Open:** libvirt installation and multi-disk workspace derivation require
new cold-boot and isolation evidence on a disposable copy.

# QEMU with Windows Hypervisor Platform

Status: bounded Windows Home x64 feasibility probes are `live-tested`;
Windows guest boot and Machine Control provider integration remain open.

## Provider and licensing

[QEMU](https://www.qemu.org/) is an open-source machine virtualizer. Its
[declared license](https://www.qemu.org/docs/master/about/license.html) is
GPL version 2, with component-specific terms in its
[LICENSE](https://gitlab.com/qemu-project/qemu/-/blob/master/LICENSE).
Bundled firmware and Windows binary dependencies retain their own terms;
the experiment is not a redistribution/license audit. Microsoft's installed
Windows Hypervisor Platform remains a separately supplied OS component.

## Architecture and reach

**Upstream-claimed:** [WHPX](https://www.qemu.org/docs/master/system/whpx.html)
accelerates QEMU on x64 and ARM64 Windows. QEMU owns virtual devices, disk
images and its [QMP management protocol](https://www.qemu.org/docs/master/interop/qemu-qmp-ref.html);
Microsoft supplies the hypervisor API. This differs from the full Hyper-V
role and its VM-management service. Upstream instructs operators to enable
the Windows Hypervisor Platform optional feature.

QEMU is already beneath other adopted Mac/Linux hosting routes. That does
not establish Windows-hosted guest support. QMP lifecycle and optional outer
display/input do not supply guest semantic UI, administration, credentials,
or protected-desktop authority. Those remain in the existing Windows guest
runtime and authenticated transport. Headless management permits automation
without a visible VM window; remote provider hosting is untested here.

## Bounded evidence

**Current (2026-10-04), `live-tested`, Windows 11 Home x64:**

- A diskless reset-vector program, launched with WHPX explicitly selected and
  no software-emulation fallback, wrote an independently checked exit marker.
- Loopback QMP observed prelaunch, running and paused states and clean exit.
  An initial stdio harness had framing errors and needed bounded process
  cleanup; the socket harness passed.
- Offline QCOW2 overlay writes/readback preserved the base file's digest.
  Discarding and recreating the overlay removed the marker. This tests disk
  primitives, not claimed workspace or guest-level isolation conformance.
- Probes used no host desktop input, no guest credentials and no networking
  devices. All QEMU processes exited or were reaped; probe disks were deleted.

The host already ran WSL2 and reported an active hypervisor. These probes
succeeded while the separate HypervisorPlatform feature reported disabled.
A pending feature-enable elevation was cancelled; no feature change or reboot
was performed. Do not generalize this observation into an installation recipe
or bypass upstream prerequisites. A supported, reproducible setup remains a
qualification gate. Private provisioning records retain exact artifacts and
direct-script evidence; [Tactical 094](../../docs/tactical/094-windows-hyperv-development-host.md)
owns the sanitized execution summary.

## Fit and next evidence

**Proposal:** use QMP plus receipt-bound QCOW2 derivation behind the existing
common contract if Windows guest acceptance succeeds. There is no common
adapter, exact-identity/claim integration, or authenticated management endpoint
from this experiment. Loopback alone is not an authorization boundary.

**Open:** boot official Windows media with Secure Boot and TPM intact; prove
canonical credential handoff, unattended guest transport, resident effects,
reboot recovery, workspace cleanup and WSL2 coexistence under load. Firmware
file availability is not Secure Boot or TPM evidence. ARM64 Windows hosts,
guest performance, package provenance/distribution and protected operations
have not been qualified on this route.

# Oracle VirtualBox

Status: Windows Home x64 hosting is `live-tested` through an experimental
common adapter. Linux resident conformance and repeated cold boot pass with a
guest workaround. Windows reached authenticated desktop/Guest Additions;
resident acceptance is in progress. Production adoption remains open.

## Provider and licensing

[Oracle VirtualBox](https://www.virtualbox.org/) provides desktop VM hosting
and the [VBoxManage CLI](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/vboxmanage.html).
The base package declares GPL-3.0-only; bundled components retain their
[separately listed terms](https://docs.oracle.com/en/virtualization/virtualbox/7.2/licensing/licensing-licensing-info.html).
The separately licensed Extension Pack is not part of this experiment. Exact
distribution/source review is required before redistribution.

## Architecture and claimed reach

**Upstream-claimed:** Windows x64, Linux and macOS hosts are supported with
platform-specific restrictions. Windows ARM support is experimental and is
not covered by this x64 experiment. See the
[installation guide](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/installation.html).

VBoxManage supplies UUID-based inventory, headless start, lifecycle, virtual
disk and snapshot management, EFI variables, emulated TPM and unattended
installation. Guest Additions supplies authenticated guest process/file
operations, including password-file input. These are candidates for bootstrap
and recovery; ordinary Machine Control administration and semantic UI should
continue through the existing target-resident implementation.

**Upstream-claimed:** VirtualBox can use Microsoft's active hypervisor on a
Windows host, but performance can suffer. WSL2 coexistence and useful iteration
latency require live qualification. Do not disable host security or WSL merely
to make an experiment pass. Host installation includes a support driver;
bridged/host-only networking, USB and Python bindings are separate installer
features. NAT and the CLI do not require those optional drivers/bindings.

## Initial evidence and setup pitfalls

**Current (2026-10-04), `live-tested`, Windows Home x64:** the signed core
application/driver installed with restart suppressed and no restart requested.
An isolated private VM library and exact UUID receipt bound a scratch Windows
11 guest to EFI, TPM 2.0, Microsoft Secure Boot signatures and an Oracle
platform key. The headless installer booted from official evaluation media
whose full digest matched Microsoft's published value. WSL remained responsive.

The supplied unattended template contains hardware-check bypass commands in
both Windows PE and the installed OS. The private experiment removed all of
them before rendering and checked the result. Using stock defaults would not
establish acceptance with Windows 11 requirements intact. Setup credentials
were stored atomically in the controller's private secret store before use and
provided through password-file inputs; generated answer media remained private.

Before firmware initialization, screenshot capture reported a zero-sized
display. A later provider-native capture observed Windows installation without
host focus or input. This bootstrap capture is an explicit outer route, not
proof of ordinary resident desktop control. Secure Boot configuration readback
is not a substitute for checking its effective state inside Windows.

Installation reached 77%, then presented a blank console without Guest
Additions becoming available. Read-only debugger inspection reported a Windows
kernel and no bugcheck; the disk file timestamp stopped changing. That timestamp
alone does not establish an absence of I/O. The native Windows hypervisor backend
reported its slow execution mode. These observations do not identify the cause
of the stall or establish a general compatibility failure.

An operator-authorized force-stop and cold boot resumed setup on the existing
disk and reached the installed Windows kernel. Setup advanced, then returned
to a blank console without Guest Additions. Actual storage counters showed
ongoing writes before becoming unchanged for several minutes; a second clean
ACPI shutdown did not stop the guest. It was force-stopped under the recovery
authorization and retained for diagnosis, without a further boot or host reboot.
Guest security, password authentication and command effects remain unverified.
Do not infer stalled I/O from a VDI file timestamp: use provider storage counters.

## Follow-up guest qualification

**Current (2026-10-04), `live-tested`:** an official Ubuntu 24.04 cloud image
was provisioned with pinned SSH host keys, a canonical verified login password,
GNOME Wayland and the existing Linux resident. Common-CLI tests independently
observed semantic button effects, Unicode text and capture hashes. Secure Boot
was enabled inside the guest. A warm reboot and two cold boots without seed
media passed; the candidate was cleanly stopped and its claim released.

Four-vCPU cold boots initially stopped during initramfs driver loading. A
one-vCPU boot recovered access. Guest kernel arguments
`nox2apic rcupdate.rcu_normal=1`, with ordinary APIC enabled, then allowed
repeated four-vCPU boots and resident tests. The workaround was suggested by
[upstream issue 861](https://github.com/VirtualBox/virtualbox/issues/861), whose
reported host/backend differs; this does not establish an identical cause.

Windows recovery reached a responding login screen with three vCPUs,
paravirtualization set to `none`, x2APIC disabled and ordinary APIC enabled.
The canonical password authenticated and Guest Additions became available.
Two vCPUs had stalled in EFI, resembling but not proving the cause in
[upstream issue 799](https://github.com/VirtualBox/virtualbox/issues/799).
These are experiment settings, not a qualified universal host profile.

The [experimental adapter](../../providers/virtualbox-windows/README.md)
checks exact VM/disk identities, serializes claimed operations, uses pinned
loopback SSH and existing credential verifiers, and exposes explicit recovery
separately from ordinary resident calls. Initial creation and console bootstrap
still require private factory scripts with manual journal coverage.

## Fit and remaining gates

**Proposal:** qualify this Home-capable provider before implementing common
production workspaces. Identity/role, claims and operation serialization have
initial implementation and tests; complete factory/audit coverage and cleanup
receipts still need adoption work.
CLI support for snapshots/clones alone does not prove safe disposable
workspaces or preservation of TPM/NVRAM state across derivation.

**Open:** complete Windows guest-side security verification, resident command
effects, cold-start recovery, common-factory integration, resident protected
control, isolated workspace acceptance, and measured build/deploy/test cycles.
Remote provider hosting and Windows ARM hosts remain untested. Evidence and
cleanup results belong to [Tactical 094](../../docs/tactical/094-windows-hyperv-development-host.md);
private journals retain exact media, resource and credential locators.

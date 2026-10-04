# Oracle VirtualBox

Status: headless Windows 11 installer boot on Windows Home x64 is
`live-tested`; installation stalled before guest acceptance. Not adopted
behind the common adapter.

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
kernel and no bugcheck; disk writes stopped. The native Windows hypervisor backend
reported its slow execution mode. These observations do not identify the cause
of the stall or establish a general compatibility failure. Guest security,
password authentication and command effects remain unverified.

## Fit and remaining gates

**Proposal:** qualify this Home-capable provider before implementing common
VM lifecycle and workspaces. A provider must bind identity/role, claims,
serialization, journal/audit coverage, and cleanup receipts before adoption.
CLI support for snapshots/clones alone does not prove safe disposable
workspaces or preservation of TPM/NVRAM state across derivation.

**Open:** complete guest-side security/credential verification and command
effects, cold-start recovery, common-adapter integration, resident protected
control, isolated workspace acceptance, and measured build/deploy/test cycles.
Remote provider hosting and Windows ARM hosts remain untested. Evidence and
cleanup results belong to [Tactical 094](../../docs/tactical/094-windows-hyperv-development-host.md);
private journals retain exact media, resource and credential locators.

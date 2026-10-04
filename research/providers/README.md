# Provider Index

Provider dossiers examine architectural breadth: whether one library can be a
common spine, which platforms it actually reaches, and where platform-specific
components remain necessary. Evidence levels are defined in the
[research corpus guide](../README.md#evidence-levels).

| Provider | Declared top-level license | Platform reach under review | Strongest evidence here |
| --- | --- | --- | --- |
| [VirtualBox](virtualbox.md) | Base GPL-3.0-only; bundled components and Extension Pack have separate terms | Windows Home x64 hosting; other hosts upstream-claimed here | Headless Windows 11 installer boot; installation stalled before guest acceptance |
| [QEMU/WHPX](qemu-whpx.md) | GPL-2.0; bundled components retain their terms | Windows-hosted VMs | Live x64 execution/QMP/overlay probes; Windows 11 qualification blocked by native-host TPM exclusion |
| [UTM](utm.md) | Apache-2.0; bundled (L)GPL and other components retain their terms | macOS-hosted Windows/Linux VMs | Adopted lifecycle provider; live CLI failure diagnosis |
| [Sky Computer Use](sky-computer-use.md) | Proprietary plugin/service; separate Codex source Apache-2.0 | macOS caller authorization; Windows unreviewed | JS/native static review; bounded live discovery and rejection of Python/signed-Node socket callers |
| [Machine Control Chrome extension](chrome-extension.md) | MIT; browser distributor terms remain separate | macOS, Windows; Linux integration open | Source-native browser conformance; signed Windows acceptance pending |
| [Codex / ChatGPT browser extension](codex-browser-extension.md) | No top-level source license found in reviewed package; proprietary reference | Chromium browser indicators; platform behavior untested here | Source-reviewed tab groups, favicons, and cursor overlay |
| [Cua Driver](cua-driver.md) | MIT; published skill copies have separate MIT-0 terms | Windows, macOS, Linux | Adopted by the Windows runtime; Windows/macOS conformance-tested |
| [XDG Desktop Portal](xdg-desktop-portal.md) | RemoteDesktop LGPL-2.1-or-later; per-file terms | Linux compositor backends | Source-native GNOME x64 capture/input and independent effects |
| [Open Computer Use](open-computer-use.md) | MIT; third-party notices apply | Windows, macOS, Linux | Source-reviewed at the spike pin |
| [WinApp](winapp.md) | MIT | Windows | Adopted by `winvm-testbed`; external differential for the resident runtime |
| [Agent Device](agent-device.md) | MIT | iOS, Android, macOS, Linux, web, TV/device variants | Adopted for iOS; macOS source-reviewed |
| [libimobiledevice](libimobiledevice.md) | LGPL-2.1-or-later | Apple device services from macOS, Linux, and Windows hosts | Adopted narrowly for physical-iOS `os_trace_relay` capture |
| [Touchpoint](touchpoint.md) | MIT | Windows, macOS, Linux, browser CDP | Source-reviewed |
| [Peekaboo](peekaboo.md) | MIT | macOS | Source-reviewed |
| [kwin-mcp](kwin-mcp.md) | MIT | Linux/KDE Wayland | Source-reviewed |
| [Terminator](terminator.md) | MIT | Windows | Source-reviewed |
| [OculOS](oculos.md) | MIT | Windows, macOS, Linux | Source-reviewed; implementation depth differs sharply |
| [agent-desktop](agent-desktop.md) | Apache-2.0 | macOS implemented; Windows/Linux contract stubs | Source-reviewed |
| [native-devtools-mcp](native-devtools-mcp.md) | MIT | macOS, Windows, Android | Source-reviewed |
| [RustDesk](rustdesk.md) | AGPL-3.0 | Windows, macOS, Linux and remote-device variants | Windows service architecture source-reviewed |
| [Sudo](sudo.md) | ISC-style with per-file BSD/ISC terms; uses installed OS binary | macOS askpass integration | Signed native dialog and independent root effect in ARM64 appliance |
| [AsyncVNC](asyncvnc.md) | GPL-3.0 license text; package metadata says GPL | VNC servers; macOS Screen Sharing tested | Live-tested headless guest consent/bootstrap; not adopted |

Search-triage projects that do not yet warrant dossiers remain listed in the
[adjacent-project ledger](../adjacent-projects.md). Promote one when its
architecture or a measured platform gap justifies source review.

- [python-build-standalone](python-build-standalone.md): relocatable CPython for the installed client, with component licensing.

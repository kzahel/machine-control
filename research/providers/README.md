# Provider Index

Provider dossiers examine architectural breadth: whether one library can be a
common spine, which platforms it actually reaches, and where platform-specific
components remain necessary. Evidence levels are defined in the
[research corpus guide](../README.md#evidence-levels).

| Provider | Declared top-level license | Platform reach under review | Strongest evidence here |
| --- | --- | --- | --- |
| [Cua Driver](cua-driver.md) | MIT; published skill copies have separate MIT-0 terms | Windows, macOS, Linux | Windows/macOS conformance-tested in the recent spike |
| [Open Computer Use](open-computer-use.md) | MIT; third-party notices apply | Windows, macOS, Linux | Source-reviewed at the spike pin |
| [WinApp](winapp.md) | MIT | Windows | Adopted by `winvm-testbed` |
| [Agent Device](agent-device.md) | MIT | iOS, Android, macOS, Linux, web, TV/device variants | Adopted for iOS; macOS source-reviewed |
| [Touchpoint](touchpoint.md) | MIT | Windows, macOS, Linux, browser CDP | Source-reviewed |
| [Peekaboo](peekaboo.md) | MIT | macOS | Source-reviewed |
| [kwin-mcp](kwin-mcp.md) | MIT | Linux/KDE Wayland | Source-reviewed |
| [Terminator](terminator.md) | MIT | Windows | Source-reviewed |
| [OculOS](oculos.md) | MIT | Windows, macOS, Linux | Source-reviewed; implementation depth differs sharply |
| [agent-desktop](agent-desktop.md) | Apache-2.0 | macOS implemented; Windows/Linux contract stubs | Source-reviewed |
| [native-devtools-mcp](native-devtools-mcp.md) | MIT | macOS, Windows, Android | Source-reviewed |
| [RustDesk](rustdesk.md) | AGPL-3.0 | Windows, macOS, Linux and remote-device variants | Windows service architecture source-reviewed |

Search-triage projects that do not yet warrant dossiers remain listed in the
[adjacent-project ledger](../adjacent-projects.md). Promote one when its
architecture or a measured platform gap justifies source review.

# WinVM Testbed

Agent-friendly bootstrap, management, screenshots, input injection, and
accessibility-tree automation for Windows virtual machines.

WinVM Testbed fills the gap between “the VM is running” and “an automated
agent can reliably operate it.” It provides one CLI for VM lifecycle, dynamic
network discovery, key-only SSH, PowerShell and WSL, interactive Windows UI
Automation, and low-level visual recovery.

## Supported Today

| Layer | Current implementation |
| --- | --- |
| Host | macOS |
| VM provider | UTM/QEMU |
| Guest driver | Windows 11 (x64 or ARM64) |
| Command channel | Windows OpenSSH and PowerShell |
| Semantic UI | Microsoft WinApp CLI in the interactive desktop session |
| Recovery | UTM screenshot, text, scan-code, and mouse APIs |

The host provider and guest driver are separate. Future providers can support
UTM or other hypervisors on Linux and Windows. A future macOS guest driver is
possible, although its accessibility and TCC model will require a different
guest-side implementation.

## Why a Relay Is Necessary

Windows OpenSSH commands run in non-interactive session 0. Desktop
applications and their accessibility trees run in the logged-in user's
interactive session. A scheduled task starts a small relay in that session:

```text
Host agent
  |
  +-- SSH/PowerShell (session 0) -------- system management
  |
  +-- SSH -> named pipe -> relay (session 1+) -> WinApp UI Automation
  |
  +-- provider API ---------------------- lifecycle and visual recovery
```

The relay pipe allows only the logged-in user and SYSTEM. It runs without
elevation, so it cannot bypass Windows secure desktops or UIPI.

## Quick Start

Clone the repository and inspect the configured machine:

```bash
git clone https://github.com/kzahel/winvm-testbed.git ~/code/winvm-testbed
cd ~/code/winvm-testbed
bin/winvm help
bin/winvm doctor
```

The defaults expect a UTM VM named `Windows` and an SSH alias named `winvm`.
Copy `config.example` to ignored `config.local` if yours differs.

For a fresh guest, install UTM Windows Guest Tools, log into Windows, and
stage the OpenSSH bootstrap plus your public key through the guest agent:

```bash
bin/winvm stage-bootstrap ~/.ssh/id_ed25519.pub
```

Run the printed PowerShell command once as Administrator inside Windows. Then
print and add the SSH entry, replacing the username:

```bash
bin/winvm ssh-config WINDOWS_USER
```

After `ssh winvm` works and the Windows desktop is logged in:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

The deployment installs Microsoft WinApp CLI with `winget`, copies the relay,
registers its interactive-logon scheduled task, and verifies the named-pipe
path from SSH session 0 to the desktop session.

See [docs/bootstrap.md](docs/bootstrap.md) for the complete fresh-guest and
recovery procedure. See [docs/auto-logon.md](docs/auto-logon.md) for the
explicit, guest-local auto-logon option used by dedicated test appliances.

## Daily Use

```bash
bin/winvm doctor                  # Check every control layer
bin/winvm up                      # Start/resume and print the guest IP
bin/winvm capabilities --json     # Inspect lifecycle support and down policy
bin/winvm ssh                     # Interactive PowerShell over SSH
bin/winvm ps 'Get-Process'        # PowerShell command
bin/winvm wsl -- uname -a         # Command through wsl.exe
bin/winvm down                    # Safely suspend or cleanly shut down
```

Discover and operate semantic Windows controls:

```bash
bin/winvm ui windows
bin/winvm ui launch notepad.exe
bin/winvm ui inspect -a notepad --interactive --depth 8
bin/winvm ui search Close -a notepad
bin/winvm ui invoke Close -a notepad
bin/winvm ui screenshot -a notepad
```

Use provider-level recovery when SSH or semantic automation is unavailable:

```bash
bin/winvm screenshot              # Live visible UTM window
bin/winvm type 'whoami'
bin/winvm key enter
bin/winvm key ctrl-shift-escape
bin/winvm click 800 600 left
bin/winvm scan 28 156             # Enter make/break scan codes
```

Semantic automation is preferable to coordinates. UTM mouse coordinates are
guest-display coordinates and exclude the UTM title bar. `winvm screenshot`
crops the title bar and Retina backing pixels, then scales the image to the
configured guest display. A screenshot pixel `(x, y)` is therefore the exact
coordinate accepted by `winvm click x y`.

## What Survives a Reboot

- OpenSSH starts automatically and remains usable before desktop login.
- The UI relay starts at interactive user login.
- `winvm down` uses suspend only when the provider positively declares it
  available. Known UTM/QEMU blockers such as GPU displays and NVMe disks select
  a clean guest shutdown instead.
- A cold boot normally requires one manual Windows login. A dedicated test
  appliance may use explicitly authorized guest-local auto-logon, but its
  credential must never be stored in this repository or command output.

## Application Limits

Accessibility quality depends on the application. Native Notepad exposes a
rich semantic tree. Some packaged applications expose only their outer frame.
Tauri and other embedded webviews may expose window chrome without exposing
web content; use screenshots/input or add a WebView-specific driver.

RustDesk or RDP can be added for convenient human viewing, but neither is
required for the agent control path or a substitute for semantic automation.

## Repository Layout

```text
bin/winvm                      Main agent-facing CLI
bin/winui                      Windows UI relay client
guests/windows/                Windows bootstrap and relay implementation
providers/utm-macos/           UTM lifecycle, discovery, capture, and input
scripts/                       Shared configuration, deployment, and doctor
docs/                          Architecture and recovery details
skills/drive-winvm/            Reusable agent skill
```

See [docs/architecture.md](docs/architecture.md) before adding another host
provider or guest driver.

Open automation gaps found while driving real applications are tracked in
[docs/problems.md](docs/problems.md).

## Requirements

Host:

- macOS with UTM and its bundled `utmctl`
- Bash, OpenSSH, `jq`, `base64`, `iconv`, `nc`, and Swift
- macOS Screen Recording permission for live UTM-window capture

Windows guest:

- Windows 11 with UTM Windows Guest Tools
- An administrator account
- `winget` for automatic WinApp installation
- An interactive login for UI automation

## Security

- Public-key SSH is required; password and keyboard-interactive SSH are
  disabled by the bootstrap.
- No passwords, private keys, or auto-login settings are stored.
- The UI relay pipe is restricted to the current Windows user and SYSTEM.
- Secure desktops and elevated windows remain protected by Windows.

## Upstream References

- [UTM scripting reference](https://docs.getutm.app/scripting/reference/)
- [Microsoft WinApp CLI](https://github.com/microsoft/winappCli)
- [WinApp UI automation](https://github.com/microsoft/winappCli/blob/main/docs/ui-automation.md)
- [Microsoft session 0 guidance](https://learn.microsoft.com/en-us/windows/win32/services/interactive-services)
- [Microsoft UIPI guidance](https://learn.microsoft.com/en-us/troubleshoot/power-platform/power-automate/desktop-flows/ui-automation/uipi-issues)

## License

MIT

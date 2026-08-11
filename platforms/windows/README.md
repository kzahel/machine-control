# WinVM Testbed

Agent-friendly bootstrap, management, screenshots, input injection, and
accessibility-tree automation for Windows virtual machines.

This directory is the canonical public source. The former
`winvm-testbed` repository is retained only as legacy history and a possible
future generated distribution.

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

From a `machine-control` checkout, inspect the configured machine:

```bash
cd ~/code/machine-control/platforms/windows
bin/winvm help
bin/winvm doctor
```

The defaults identify a UTM VM named `Windows` and an SSH alias named `winvm`,
but do not authorize mutation. Copy `config.example` to ignored `config.local`,
pin its provider-native UUID and role with `bin/winvm pin-target ROLE`, where
the role is `source`, `candidate`, or `seal`, before using mutating commands.

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

After `ssh winvm` works, install the target-resident runtime and reproducible
development profile:

```bash
../../scripts/bootstrap-windows.sh --testbed . \
  --profile development winvm
bin/winvm post-update audit --json
bin/winvm doctor
```

The default `development` profile installs and verifies Python 3 and the .NET
8 SDK before transactionally installing the resident. Select `--profile
runtime` for an appliance that intentionally omits build tooling.

The older WinApp comparison relay remains available when a differential test
specifically needs it:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

That optional deployment installs Microsoft WinApp CLI with `winget`, copies
the relay, registers its interactive-logon scheduled task, and verifies its
named-pipe path. It is not required by the installed MachineControl resident.

See [docs/bootstrap.md](docs/bootstrap.md) for the complete fresh-guest and
recovery procedure. See [docs/auto-logon.md](docs/auto-logon.md) for the
explicit, guest-local auto-logon option used by dedicated test appliances.
See [docs/image-factory.md](docs/image-factory.md) for unattended answer media,
factory creation, Sysprep generalization, and stopped UTM export.

## Daily Use

```bash
bin/winvm doctor                  # Check every control layer
bin/winvm doctor --json           # Minimized common readiness projection
bin/winvm candidate-status --json # Minimized role/identity/power assertion
bin/winvm post-update audit --json # Read-only startup/toolchain/readiness audit
bin/winvm post-update repair --json # Bounded candidate-only inner repair
bin/winvm post-update repair --reboot --json # Repair and prove new boot epoch
bin/winvm assert-target connect --json # Verify UUID pin and role policy
bin/winvm up                      # Start/resume and print the guest IP
bin/winvm capabilities --json     # Inspect lifecycle support and down policy
bin/winvm ssh                     # Interactive PowerShell over SSH
bin/winvm ps 'Get-Process'        # PowerShell command
bin/winvm wsl -- uname -a         # Command through wsl.exe
bin/winvm down                    # Safely suspend or cleanly shut down
bin/winvm seal READY_NAME         # Clone a stopped VM as a stopped seal
bin/winvm disposable-up           # Verify a seal without persisting changes
bin/winvm delete --confirm NAME   # Delete only the exact configured stopped VM
```

The installed MachineControl resident is also available through first-class
testbed entry points:

```bash
bin/winvm control '{"operation":"status"}'
bin/winvm control-local '{"operation":"status"}'
capture="$(bin/winvm control '{"operation":"screenshot"}')"
bin/winvm artifact "$(jq -r '.data.artifactId' <<<"$capture")"
```

Both control commands invoke the same guest-local installed client through the
authorized SSH administration route. `artifact` accepts only the resident's
32-hex-character capture identifier and the fixed resident artifact namespace;
it is not an arbitrary guest file transfer command.

`doctor --json` emits the minimized `machine-control-doctor/v0` projection for
the common client. It reports independent power, administration, desktop,
resident, semantic, capture, input, and outer states without publishing the
configured machine identity, desktop user, or network address. It is read-only
and exits nonzero when the accepted resident surface is not ready.

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

Set `WINVM_FORBID_OUTER_UI=true` during ordinary acceptance. In that mode the
provider refuses `screenshot`, `type`, `click`, `key`, and `scan` before they
can observe or manipulate the host UTM window.

Semantic automation is preferable to coordinates. UTM mouse coordinates are
guest-display coordinates and exclude the UTM title bar. `winvm screenshot`
crops the title bar and Retina backing pixels, then scales the image to the
configured guest display. A screenshot pixel `(x, y)` is therefore the exact
coordinate accepted by `winvm click x y`. Capture also finds a matching UTM
console on another macOS Space, preferring an on-screen console when possible.

## Target-Safety Interlock

Friendly VM names are selectors, not mutation authority. `pin-target` writes
an ignored, mode-0600 `.target.local`. Before changing
state, the UTM provider resolves the selected VM's UUID and compares it with
`WINVM_EXPECTED_UTM_ID` in ignored configuration. It also applies the declared
`WINVM_TARGET_ROLE` policy:

- `source` can be inspected, stopped, or cloned while stopped, but cannot be
  booted, connected to, bootstrapped, driven, force-stopped, or deleted unless
  the narrowly scoped source-mutation override is present;
- `candidate` supports ordinary build, control, sealing, and exact-confirmed
  deletion; and
- `seal` supports disposable verification and teardown, but a persistent boot
  requires its own explicit override. A stopped seal may be cloned without
  changing it.

`pin-target ROLE NAME` atomically changes the private selection and its UUID
pin together. `pin-target ROLE --configured` returns to the target named in
`config.local` without copying that private name into a command or document.

An assertion is a local safety interlock, not a credential. SSH keys and the
provider's authorization remain the security boundary. Keep real UUIDs and
role selection in `.target.local`; do not paste them into documentation or Git.

From the repository root, the common client combines these guards with fresh
readiness evidence:

```bash
bin/machine-control --target windows target ensure-ready
bin/machine-control --target windows target validate-candidate
bin/machine-control --target windows target prepare-promotion
```

The last command cleanly stops the candidate and reports whether it is
eligible for a private-inventory role update. It neither changes that inventory
nor boots or clones a seal.

## What Survives a Reboot

- The QEMU guest agent and hardened OpenSSH services start automatically;
  OpenSSH remains usable before desktop login.
- The MachineControl service starts automatically and creates its Medium
  interactive helper after the dedicated appliance logs in.
- An installed legacy WinApp relay starts at interactive user login, but it is
  optional and is not the ordinary resident route.
- `post-update audit` verifies these claims after OS or package updates without
  starting a stopped target. `post-update repair` may restore only the declared
  installed-service, SSH-policy, and firewall invariants; it does not install
  missing components or clear a pending reboot.
- `winvm down` uses suspend only when the provider positively declares it
  available. Known UTM/QEMU blockers such as GPU displays and NVMe disks select
  a clean guest shutdown instead.
- A stopped UTM VM can be cloned into a provider-owned seal. A seal can be
  started in disposable mode for verification without saving guest changes.
- A cold boot normally requires one manual Windows login. A dedicated test
  appliance may use explicitly authorized guest-local auto-logon, but its
  credential must never be stored in this repository or command output.

## Application Limits

Accessibility quality depends on the application. Native Notepad exposes a
rich semantic tree. Some packaged applications expose only their outer frame.
Tauri and other embedded webviews may expose window chrome without exposing
web content; use screenshots/input or add a WebView-specific driver.

Windows system-modal and secure-desktop prompts are outside the unelevated
semantic relay. The relay also depends on SSH, so it cannot dismiss a prompt
when the command channel is unavailable. Keep provider screenshot and raw
input available for those recovery cases, and re-run `doctor` afterward.

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

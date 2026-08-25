# Fresh Windows Guest Bootstrap

This runbook establishes a durable command channel first, then adds semantic
desktop automation. It applies to the ARM64 UTM/macOS and native x86_64
libvirt/Linux routes while retaining the original bootstrap failure evidence.
It contains no concrete machine identifiers or credentials.

## 1. Prepare the Guest

Create or import a Windows 11 VM through the selected provider. UTM uses its
Windows Guest Tools; libvirt uses the separately verified VirtIO tools and the
native-x86_64 image factory. Complete setup and confirm the provider can see
the running VM:

```bash
bin/winvm status
bin/winvm ip
```

Copy `config.example` to ignored `config.local`, even when the friendly name
matches, then run `bin/winvm pin-target candidate`. This records the resolved
UUID and role in mode-0600 ignored `.target.local`. Mutating commands
intentionally fail when the pin is absent or stale.

## 2. Stage OpenSSH Without Guest Networking

The QEMU guest agent can transfer files before SSH exists:

```bash
bin/winvm stage-bootstrap ~/.ssh/id_ed25519.pub
```

This writes only these temporary files:

```text
C:\Users\Public\winvm-bootstrap-openssh.ps1
C:\Users\Public\winvm-host.pub
```

Open PowerShell as Administrator inside Windows and run:

```powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass `
  -File C:\Users\Public\winvm-bootstrap-openssh.ps1
```

The idempotent script:

1. Installs Windows OpenSSH Server.
2. Installs a digest-pinned native PowerShell 7 archive for ARM64 or x64.
3. Installs the staged key in the administrator authorized-keys file.
4. Restricts its ACL to Administrators and SYSTEM.
5. Enables public-key authentication and disables password/keyboard-interactive
   authentication.
6. Selects the native PowerShell runtime as the default SSH shell.
7. Creates an explicit inbound TCP/22 firewall rule.
8. Validates the SSH configuration and starts `sshd` automatically.
9. Writes `C:\Users\Public\winvm-openssh-report.json`.

Current Windows media may install `sshd.exe` without first creating
`ProgramData\ssh\sshd_config`. The bootstrap initializes that file from the
capability's installed `sshd_config_default` before applying and validating the
key-only policy. It also generates the capability's missing server host keys
before fail-closed configuration validation.

The native PowerShell archive uses a pinned release URL and SHA-256 for each
supported architecture rather than a Store/MSIX application-execution alias.
That gives the machine-wide OpenSSH service a stable executable path and avoids
the multi-second Windows PowerShell 5 startup penalty observed on the ARM64
appliance. Post-update audit and repair preserve the version, path, and `-c`
command option as one OpenSSH automation-shell invariant.

## 3. Configure the Stable SSH Alias

Print the OpenSSH client block with the Windows account name:

```bash
bin/winvm ssh-config WINDOWS_USER
```

Add it to `~/.ssh/config`. The ProxyCommand starts/resumes the VM, discovers
its current shared-network address through the guest agent, waits for TCP/22,
and connects to it. `HostKeyAlias` binds the host key to the stable alias
instead of a replaceable DHCP address.

Non-PTY commands are the machine-readable automation path. The testbed encodes
PowerShell scripts into the configured shell without starting a second shell,
and common `target doctor` uses one guest session with a 60-second bound. PTY
allocation remains for interactive use and is not an automation workaround.

Verify key-only access:

```bash
ssh winvm '$PSVersionTable.PSVersion.ToString(); whoami; hostname'
```

To confirm password authentication is not offered:

```bash
ssh -vv \
  -o PubkeyAuthentication=no \
  -o PreferredAuthentications=password,keyboard-interactive \
  -o NumberOfPasswordPrompts=0 \
  winvm exit
```

The expected result is `Permission denied (publickey)`.

## 4. Install the Resident and Development Profile

From the Windows platform directory, use the UUID-attested controller
bootstrap:

```bash
../../scripts/bootstrap-windows.sh --testbed . \
  --profile development winvm
```

The `development` profile idempotently installs Python 3 and the .NET 8 SDK
through their exact WinGet package identifiers, verifies both commands, then
builds, transfers, transactionally installs, and probes the MachineControl
resident. Use `--profile runtime` only when the appliance intentionally should
not build the repository. Both profiles install the guest-native post-update
support scripts beside the runtime.

Audit the installed startup contract without changing the guest:

```bash
bin/winvm post-update audit --json
```

After a Windows or package update, an explicitly selected candidate may run
the bounded idempotent repair and an optional reboot proof:

```bash
bin/winvm post-update repair --json
bin/winvm post-update repair --reboot --json
```

Repair prefers key-only SSH. If SSH is unavailable, the UTM provider may stage
the same guest-native script and execute it through the QEMU guest agent. UTM's
process result is not trusted: the controller requires a fresh caller-nonce
report pulled through the independent file channel and then requires SSH plus
the full doctor to return. Repair never enters a credential, uses the UTM
window, force-stops the VM, installs an absent component, or clears a
pending-reboot marker.

For an occasional complete proof after material controller, toolchain, or
Windows changes, commit the source tree and run:

```bash
bin/winvm appliance-certify --json
```

Certification does not repair. It audits, reboots, requires a changed boot
epoch and common-doctor readiness, transfers a digest-bound archive of the
exact commit, runs portable and Windows-native checks in the guest, removes
staging, and cleanly shuts down only on success. Failure leaves the appliance
running for diagnosis and never creates another VM.
Each portable or native guest check has a configurable supervised-process
timeout (20 minutes by default); timeout cleanup targets only that check's
process tree and the unique certification staging directory.

## 5. Install the Optional WinApp Comparison Relay

Keep the Windows desktop logged in, then run:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

The deployer installs `Microsoft.WinAppCli`, copies the relay files to the
current Windows user's Local AppData, and registers `WinVM UI Relay` as a
non-elevated interactive-logon scheduled task. This legacy differential route
is optional; the MachineControl resident owns the ordinary interactive helper.

## 6. Remove Bootstrap Staging Files

After verification:

```powershell
Remove-Item -Force -ErrorAction SilentlyContinue -LiteralPath @(
  'C:\Users\Public\winvm-bootstrap-openssh.ps1',
  'C:\Users\Public\winvm-host.pub',
  'C:\Users\Public\winvm-openssh-report.json'
)
```

## Observed Failure Modes

### Guest-agent execution reports false success

On the original guest, `utmctl ip-address`, `file push`, and `file pull` worked,
while `utmctl exec` returned success without launching a process or creating
probe files. Ordinary work deliberately uses SSH. The bounded post-update
fallback accepts guest-agent execution only when a fresh nonce-bound report is
independently pulled and SSH plus the full resident doctor subsequently return.

### The stock OpenSSH firewall rule is insufficient

The original guest reached this deceptive state:

```text
sshd service: Running
listener: [::]:22
localhost TCP/22: reachable
host -> guest:22: timeout
```

The Windows-provided OpenSSH rule was enabled but did not admit traffic from
UTM's shared network. The bootstrap's explicit profile-independent TCP/22 rule
fixed it. A timeout suggests the firewall path; a refusal suggests the listener.

### The ordinary user helper is absent after a locked reboot

SSH and the protected resident start before login, while the Medium user
helper correctly waits for an interactive desktop. A dedicated-appliance
doctor therefore reports the desktop locked but protected semantics, capture,
and input ready. Use the typed one-shot secret login operation when authorized,
or an explicitly armed outer console for recovery, then rerun doctor. Do not
enable persistent auto-logon or place a credential in repository content,
arguments, environment variables, logs, or ordinary JSON.

## Recovery Order

1. `bin/winvm doctor`
2. `bin/winvm post-update audit --json`
3. `bin/winvm post-update repair --json` on an exact candidate
4. PowerShell over `bin/winvm ssh`
5. Guest-agent IP discovery and file transfer
6. Explicit outer recovery only when separately authorized

Do not otherwise weaken authentication or disable Windows security controls to
recover access. See [auto-logon.md](auto-logon.md) when the user explicitly
authorizes automatic login for a dedicated test appliance.

On the Linux/libvirt route, explicit outer recovery does not require a visible
virt-manager or SPICE window. The guarded provider can capture the exact
running KVM domain to a private PNG and can send bounded named-key, US-ASCII,
and absolute-tablet events through QEMU. Private inventory prohibits that
route during ordinary work; temporarily arming it remains a separate recovery
decision and every command still requires the exact target-use claim.

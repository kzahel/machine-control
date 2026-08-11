# Fresh Windows Guest Bootstrap

This runbook establishes a durable command channel first, then adds semantic
desktop automation. It records the failure modes discovered while bootstrapping
a Windows 11 ARM64 guest in UTM 4.7.5 without retaining machine identifiers or
credentials.

## 1. Prepare the Guest

Create or import a Windows 11 VM in UTM using the QEMU backend. Complete
Windows setup, install UTM Windows Guest Tools, and log into an administrator
account. Confirm the provider can see the running VM:

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
2. Installs the staged key in the administrator authorized-keys file.
3. Restricts its ACL to Administrators and SYSTEM.
4. Enables public-key authentication and disables password/keyboard-interactive
   authentication.
5. Selects Windows PowerShell as the default SSH shell.
6. Creates an explicit inbound TCP/22 firewall rule.
7. validates the SSH configuration and starts `sshd` automatically.
8. Writes `C:\Users\Public\winvm-openssh-report.json`.

Current Windows media may install `sshd.exe` without first creating
`ProgramData\ssh\sshd_config`. The bootstrap initializes that file from the
capability's installed `sshd_config_default` before applying and validating the
key-only policy. It also generates the capability's missing server host keys
before fail-closed configuration validation.

## 3. Configure the Stable SSH Alias

Print the OpenSSH client block with the Windows account name:

```bash
bin/winvm ssh-config WINDOWS_USER
```

Add it to `~/.ssh/config`. The ProxyCommand starts/resumes the VM, discovers
its current shared-network address through the guest agent, waits for TCP/22,
and connects to it. `HostKeyAlias` binds the host key to the stable alias
instead of a replaceable DHCP address.

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

### UI automation disappears after reboot

This is expected until an interactive Windows login exists. SSH starts before
login, but the relay intentionally has no credential. Use UTM's visible console
for the login, then `bin/winvm doctor`. A dedicated test appliance may instead
use explicitly authorized guest-local auto-logon; never place that credential
in this repository or command output.

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

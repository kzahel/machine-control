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

If the VM or SSH alias differs from the defaults, copy `config.example` to
ignored `config.local` and edit it.

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

## 4. Install Interactive UI Automation

Keep the Windows desktop logged in, then run:

```bash
bin/winvm deploy-ui
bin/winvm doctor
```

The deployer installs `Microsoft.WinAppCli`, copies the relay files to the
current Windows user's Local AppData, and registers `WinVM UI Relay` as a
non-elevated interactive-logon scheduled task.

## 5. Remove Bootstrap Staging Files

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
probe files. Verify side effects before trusting guest-agent execution. This
project deliberately switches to SSH rather than relying on it.

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
2. PowerShell over `bin/winvm ssh`
3. Guest-agent IP discovery and file transfer
4. `bin/winvm screenshot`, `type`, `key`, `scan`, and `click`
5. The smallest necessary manual action in UTM

Do not otherwise weaken authentication or disable Windows security controls to
recover access. See [auto-logon.md](auto-logon.md) when the user explicitly
authorizes automatic login for a dedicated test appliance.

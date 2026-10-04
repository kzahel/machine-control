# Experimental native Windows VirtualBox adapter

Status: Windows and Linux guest administration and resident control are
live-tested on a Windows Home x64 controller. This is an
explicit opt-in adapter for privately provisioned candidates, not an accepted
factory, base-image promotion or isolated-workspace implementation.
Windows desktop/UAC and unlock tests passed, but shutdown and media-free
cold-start attempts subsequently stalled; reliable Windows lifecycle acceptance
is blocked. Linux passed repeated cold boots with a documented guest workaround.

Use native Windows Python, OpenSSH and VBoxManage through the common CLI.
Keep Git in WSL. The platform directories continue to own guest bootstrap,
residents and credential verification; this adapter owns host lifecycle and
transport. See [Tactical 094](../../docs/tactical/094-windows-hyperv-development-host.md)
and the [provider dossier](../../research/providers/virtualbox.md).

Native development-host package builds should pass `--git-via-wsl` to
`release/windows-package.py build`; compilers stay native while source-state
inspection uses WSL Git. Hosted CI retains its existing Git configuration.

## Private configuration

Set `MACHINE_CONTROL_VBOX_CONFIG` in an untracked registry target's environment
to an absolute JSON file path. Use `launcher: python`, the absolute path to
`adapter.py` as its command, and `controllerPlatforms: [windows]`. Disable
default targets when using a dedicated experimental registry.

The private configuration has schema `machine-control-virtualbox-target/v0`:

| Field | Required value |
| --- | --- |
| `platform`, `profile` | `windows` or `linux`, and the guest profile |
| `role` | `candidate` or `development`; immutable bases are refused |
| `uuid`, `diskUuid` | Exact VM and system-disk UUIDs |
| `library` | Absolute isolated `VBOX_USER_HOME` directory |
| `vmFile`, `disk` | Absolute registered configuration and SATA port-zero disk paths |
| `stateDirectory` | Absolute private controller state directory |
| `username`, `sshPort` | Exact account and controller-loopback NAT SSH port |
| `sshKey`, `knownHosts` | Absolute controller private-key and independently pinned host-key files |
| `credentialFile` | Canonical stored login password; required for credential handoff |
| `bootstrapMedia` | Exact seed ISO path, required for guarded detachment |
| `unlockInstance`, `unlockGrantFile`, `unlockKeyFile` | Optional installed Windows unlock instance and absolute private approval/key locators |
| `opensslDirectory` | Optional absolute directory containing native OpenSSL for the existing unlock controller |

Keep every path, identity, endpoint, key, journal and capture private. Restrict
directories and secret files with Windows ACLs before provisioning. The SSH
host key must be obtained through the authenticated bootstrap route before
first connection. SSH uses strict verification and an empty configuration
file; it does not modify or inherit the user's personal SSH configuration.
The adapter pins Windows' native OpenSSH executables by absolute path, including
when the unlock controller adds an OpenSSL directory to its process-local PATH.
Windows guests use the PowerShell 7 installation from the existing bootstrap.

## Claims and operation boundaries

Run `target doctor`, inspect `audit history` and its coverage limits, acquire
an exclusive claim, and carry both the claim and provisioning-run ID on common
CLI calls. Renew long claims and release in cleanup. Claims bind the isolated
library and exact UUID; each operation checks the registration, disk path and
disk UUID again under a controller operation lock. Private configuration and
claims are same-user state, not a security boundary against that user.

Ordinary operations include `target up`, `target shutdown`, `target status`,
`os`, `desktop`, and `desktop artifact`. Linux uses the existing target-native
resident; Windows uses the dedicated appliance runtime. This adapter never
selects the host's desktop app. Native passthrough operations include:

- `credential status --json` and `credential verify --json`: reuse platform
  verifiers, delivering the password only through standard input after
  authenticated account discovery. Status is a bounded cached observation.
- `factory-stages --json`: journal-compatible observations, explicitly keeping
  promotion and isolated workspaces unqualified.
- `push SOURCE ABSOLUTE_GUEST_DESTINATION`: authenticated guest file transfer;
  Windows uses SFTP to preserve binary bytes independently of PowerShell stdin.
- `unlock`: Windows only; reuses the existing signed-challenge controller and
  installed optional unlock service. It reads the canonical password only
  after authorization and native credential-field discovery. Installation and
  explicit account/controller approval are prerequisites, not implicit effects
  of this command. The appliance runtime and ordinary desktop app stay separate.
- `login`: Windows cold login only, with no existing interactive user. Resolves
  the authenticated account's display name and a unique visible stock password
  field before opening the canonical credential file. Reuses the appliance
  runtime's dedicated standard-input/login-pipe transport and independent
  broker validation. A bounded generation-bound resident Enter may reveal the
  non-credential curtain; uncertain account or field discovery refuses.
- `detach-bootstrap-media`: stopped candidates only, exact seed identity and
  verified credential handoff required.

Explicit recovery requires a disruptive claim: `screenshot NEW_ABSOLUTE_PATH`,
`acpi-shutdown`, `force-stop`, `recovery-key enter|tab|escape`, and
stopped-candidate `candidate-hardware`. Recovery keys are bounded virtual
keyboard input for observed recovery screens, never a password transport.
ACPI delivery does not claim shutdown; inspect power afterward. Normal shutdown
waits up to fifteen minutes for Windows power-off (two minutes for Linux),
rechecking the claim during the wait, and never silently force-stops. Callers
must allow the complete wait rather than killing the adapter at two minutes.
Hardware experiments accept only `--cpus 1..4`,
`--x2apic on|off`, and `--serial-log NEW_ABSOLUTE_PRIVATE_PATH`. Disabling
x2APIC explicitly retains ordinary APIC for 64-bit guests. `--rtc-use-utc on|off`
sets and reads back the candidate's virtual hardware clock convention; align
the guest's own time configuration before changing it. Provider captures
and serial logs are private recovery evidence, not ordinary test routes.
`--paravirt-provider none|default|hyperv` selects the guest-facing interface
with readback; it does not enable, disable or reconfigure the host hypervisor.

Initial VM creation and Windows console bootstrap still use private exact-UUID
factory scripts and need manual journal notes. No implicit fallback from SSH
to host input exists. Snapshots, derived workspaces,
promotion, remote hosting and ARM controllers require further qualification.

Run the bounded regression tests with:

```text
py -3 -m unittest discover -s providers/virtualbox-windows/tests -v
```

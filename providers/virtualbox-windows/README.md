# Experimental native Windows VirtualBox adapter

Status: Linux guest administration and resident control are live-tested on a
Windows Home x64 controller. Windows qualification is in progress. This is an
explicit opt-in adapter for privately provisioned candidates, not an accepted
factory, base-image promotion or isolated-workspace implementation.

Use native Windows Python, OpenSSH and VBoxManage through the common CLI.
Keep Git in WSL. The platform directories continue to own guest bootstrap,
residents and credential verification; this adapter owns host lifecycle and
transport. See [Tactical 094](../../docs/tactical/094-windows-hyperv-development-host.md)
and the [provider dossier](../../research/providers/virtualbox.md).

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

Keep every path, identity, endpoint, key, journal and capture private. Restrict
directories and secret files with Windows ACLs before provisioning. The SSH
host key must be obtained through the authenticated bootstrap route before
first connection. SSH uses strict verification and an empty configuration
file; it does not modify or inherit the user's personal SSH configuration.

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
- `push SOURCE ABSOLUTE_GUEST_DESTINATION`: authenticated guest file transfer.
- `detach-bootstrap-media`: stopped candidates only, exact seed identity and
  verified credential handoff required.

Explicit recovery requires a disruptive claim: `screenshot NEW_ABSOLUTE_PATH`,
`acpi-shutdown`, `force-stop`, and stopped-candidate `candidate-hardware`.
ACPI delivery does not claim shutdown; inspect power afterward. Normal shutdown
never silently force-stops. Hardware experiments accept only `--cpus 1..4`,
`--x2apic on|off`, and `--serial-log NEW_ABSOLUTE_PRIVATE_PATH`. Disabling
x2APIC explicitly retains ordinary APIC for 64-bit guests. Provider captures
and serial logs are private recovery evidence, not ordinary test routes.

Initial VM creation and Windows console bootstrap still use private exact-UUID
factory scripts and need manual journal notes. No implicit fallback from SSH
to host input exists. Windows protected login, snapshots, derived workspaces,
promotion, remote hosting and ARM controllers require further qualification.

Run the bounded regression tests with:

```text
py -3 -m unittest discover -s providers/virtualbox-windows/tests -v
```

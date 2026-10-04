# Experimental native Windows VirtualBox adapter

Status: Windows and Linux guest administration and resident control are
live-tested on a Windows Home x64 controller. This is an
explicit opt-in adapter for privately provisioned candidates. Guarded base
promotion receipts are implemented; complete factory and isolated-workspace
integration remain unqualified.
Windows desktop/UAC, cold login and repeated lifecycle acceptance now pass
under a declared compatibility profile with a bounded shutdown scheduling
assist. A protected stopped Windows base and accepted full-copy development
VM are retained. Linux passed repeated cold boots with a guest workaround.

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
| `role` | `candidate` or `development`; a protected-base receipt overrides this role and refuses ordinary mutation |
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
| `shutdownRescheduleAfterSeconds` | Optional Windows compatibility experiment: `0` disables it; `15..120` seconds permits one bounded pause/resume during shutdown |
| `sshConnectTimeoutSeconds` | Optional SSH handshake limit, `5..60` seconds; defaults to `5`, with no automatic command retry |

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
  promotion incomplete until a protected base verifies, and isolated workspaces unqualified.
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

The explicit `shutdownRescheduleAfterSeconds` profile requires a disruptive
claim before issuing shutdown. After Windows accepts native shutdown, the
provider waits for the configured interval, then pauses and resumes scheduling
at most once if the VM is still running. A `finally` path resumes a VM paused
by that operation. It continues waiting for Windows to reach power-off and
never substitutes a power cut. Doctor reports the opt-in outer lifecycle
route, and each successful lifecycle receipt records whether it was used.
This bounded compatibility path is distinct from an unassisted shutdown and
from ordinary desktop tests, which continue to use only target-native control.

Initial VM creation and Windows console bootstrap still use private exact-UUID
factory scripts and need manual journal notes. No implicit fallback from SSH
to host input exists. Snapshots, isolated workspaces, generalized image export,
remote hosting and ARM controllers require further qualification.

## Qualification and protected bases

Under the same exact-target claim and provisioning journal, run
`testbed -- qualify --json` after cold login, resident conformance and idle
checks. Qualification independently verifies doctor readiness, Secure Boot,
TPM readiness, UAC, absent restart/servicing flags, detached installation media,
disabled automatic login, absent cached setup password and the canonical
stored password. It records a private boot identity and hardware fingerprint;
it does not claim to run the full conformance suite itself.

The following `target shutdown` records a clean lifecycle receipt only after
observing power-off. Repeat on three distinct boots. Recovery input, ACPI
recovery, force-stop and hardware experiments invalidate previous qualification
history; a newly started but unqualified boot prevents promotion.
The configured scheduler-assist policy is part of the qualification fingerprint;
three assisted successes cannot qualify a configuration with assistance disabled.
The configured SSH handshake budget is also part of that fingerprint.

`testbed -- promote-base --json` requires a disruptive claim, a stopped
candidate, three recent qualifying boots with clean shutdowns, unchanged
credentials and an unchanged final disk. It hashes the disk, VM configuration
and firmware/TPM state, then atomically creates the private protected manifest.
The operation retains the existing registered VM in place: it neither deletes
nor replaces another image. This is a same-controller appliance profile,
not a generalized export or proof of isolated-workspace support.

`testbed -- base-verify --json` checks the exact stopped identity, credential
file stamp and all three file hashes. Protected bases refuse ordinary start,
shutdown, administration, desktop, hardware, credential mutation and repeated
promotion, including when private configuration still says `candidate`.
Malformed protection records also refuse mutation. Doctor reports the base
role; factory-stage inspection checks retained file stamps. Hash verification
is the explicit stronger check. No automatic unprotect or base deletion exists.
Keep manifests and qualification receipts private and retain the same
controller state directory with the VM; these are cooperative same-user guards,
not containment against the controller account or direct hypervisor use.

Run the bounded regression tests with:

```text
py -3 -m unittest discover -s providers/virtualbox-windows/tests -v
```

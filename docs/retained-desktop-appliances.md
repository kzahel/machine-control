# Retained Windows and Linux development appliances

The existing platform factories create dedicated test appliances. Their
target-native resident starts automatically and supplies full explicitly
authorized appliance control. A workstation desktop app is an additional
product profile, with its own grants and narrower privilege. Installing that
app is not a replacement for the appliance broker or a reason to weaken its
protected-session policy.

## 1 — prepare controller storage and media

Run `storage analyze`, review ignored current and legacy factory artifacts,
and reserve space for installation, source media and divergence. Preserve
retained development/ready-base disks. Use official media and verify its exact
publisher checksum/signature. Never promote from a plausible file size alone.

Prepare the Windows canonical password file (mode 0600) and a controller
public SSH key. Use [Windows factory media preparation](../platforms/windows/docs/image-factory.md)
for its exact Pro index, no-prompt installer, seed and boot helper. Use
[Ubuntu factory preparation](../platforms/linux/docs/bootstrap.md#native-x86_64-libvirt-image-factory)
for the architecture-matched cloud image and key-only NoCloud seed.
Credential locators and private controller keys stay outside Git.

## 2 — inspect and create an unused destination

```bash
bin/machine-control --target windows testbed -- factory-stages preflight --json ...
bin/machine-control --target linux testbed -- factory-stages preflight --json ...
bin/machine-control --target windows testbed -- factory-create ...
bin/machine-control --target linux testbed -- factory-create ...
```

Precreation needs no claim on a nonexistent VM. It still uses authoritative
unused-destination guards and does not authorize existing-guest mutation.
Bind the newly created provider identity and candidate role in the controller's
private inventory. Windows exposes `target-id` and `pin-target`; Linux uses its
exact name/UUID guard. Run `target doctor`, then acquire an attributed exclusive
claim before boot or guest work. Claim IDs must accompany subsequent commands.
Renew long provisioning work and release promptly from cleanup.

## 3 — advance observed factory stages

Under the claim, use `testbed -- factory-stages --json`. Wait for installation
and guest-agent completion rather than treating a boot timeout as permission
to force-stop. Record first-logon/cloud-init attestation when offered. Establish
SSH using the seed's public key and independently pin its host key through the
exact hypervisor guest-agent channel. Keep password SSH authentication disabled.

Windows: store and verify the setup password; use the dedicated credential
rotation/login commands for subsequent changes or cold-login recovery. Linux:
configure its canonical password file, setup key and pinned known-hosts locator,
use `trust-ssh-host-key` to install the exact UUID host-key pin, select
`LINUXVM_ADMIN_TRANSPORT=ssh` on UTM when desired, then use
`credential establish --json` for the fresh locked account followed by
`credential verify --json`. Do not leave a key-only account as the password
handoff. Expose the credential locator through private inventory as well.

Run `testbed -- bootstrap --profile development`. This installs the guest
toolchain and checked-in target-native resident; use `runtime` only for a
deliberately smaller appliance. Bootstrap and startup must be verified after a
reboot, not inferred from command delivery. Follow the stage inspector's exact
shutdown/detach actions, remove credential-bearing source/copied answer media,
and test a disk-only cold boot. Use stored credentials for Windows login.
Outer input is reserved for a directly observed bootstrap/recovery gap and
requires a disruptive claim plus controller permission.

## 4 — prove and retain usable targets

Require ready common doctor, SSH administration, local/outside resident parity,
observed semantic and input effects, and capture/artifact retrieval. Protected
Windows control retains its dedicated broker and arming contract. Use the
existing common conformance runner or equivalent bounded fixtures.

Only then declare private development/ready-base bindings proven. Retain the
appliances, canonical passwords, private bootstrap key and host-key bindings.
Remove installation media and disposable staging only after proving they are
detached and not referenced. Leave the target running when requested for use;
otherwise cleanly stop it. Release claims without deleting the retained VMs.
`workspace release` must retain a persistent development instance. A cleanup
command for a temporary validation VM must never select a retained base by
name prefix or age.

[Tactical 090](tactical/090-retained-desktop-appliance-rebuild.md) records this
bring-up's implementation and bounded live evidence.

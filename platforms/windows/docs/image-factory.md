# Windows Image Factory

This factory has three related paths:

1. create an ARM64 Windows testbed base under UTM/macOS;
2. create a native x86_64 Windows testbed base under libvirt/QEMU/KVM on
   Linux; and
3. generalize and export a configured candidate as a stopped appliance.

The first path removes the undocumented manual-OOBE dependency. The second
path proves that a configured appliance can cross the Windows generalization
boundary. They do not make installation media, activation rights, credentials,
or controller authorization portable.

## Safety boundary

All generated media and exports live under ignored `.factory.local` unless
`WINVM_FACTORY_LOCAL_ROOT` selects another private location. Never commit its
contents. `winvm factory-create` requires explicit readable media and an
unregistered destination. Generalization and export require a provider UUID
pin and `candidate` role; the source role cannot authorize either operation.
Factory creation canonicalizes readable media to absolute paths before handing
them to UTM's file-URL AppleScript contract and suppresses the provider's
new-object output so the command does not disclose private target identity.

The answer-media ISO contains a plaintext one-use setup password because that
is the Windows Setup input contract. The renderer accepts that value only from
a mode-0600 file, never an argument or environment variable. Detach and
securely discard the ISO after first-logon bootstrap. The factory keeps the
controller's public SSH key, but never its private key.

## Render unattended answer media

Prepare a mode-0600 file containing one setup password and select a public SSH
key. Then run for the Windows Pro index resolved from the exact image catalog:

```bash
scripts/image-factory.sh render-seed \
  arm64 APPLIANCE_USER IMAGE_INDEX windows-11-pro PRIVATE_SECRET_FILE \
  CONTROLLER_PUBLIC_KEY PRIVATE_UTM_GUEST_TOOLS_ISO
```

For the native Linux-hosted path, use `amd64` and Fedora's separately verified
stable `virtio-win.iso`:

```bash
scripts/image-factory.sh render-seed \
  amd64 APPLIANCE_USER IMAGE_INDEX windows-11-pro PRIVATE_SECRET_FILE \
  CONTROLLER_PUBLIC_KEY PRIVATE_VIRTIO_WIN_ISO
```

The renderer XML-escapes all substituted values, rejects weak file
permissions, validates the XML when `xmllint` is present, and builds two
purpose-specific media. `winvm-seed.iso`, labeled `WINVM_SEED`, carries the
answer file, UTM's Windows drivers, one guest-tools installer, and first-logon
bootstrap. `winvm-boot.img`, labeled `WINVM_BOOT`, is a tiny unpartitioned FAT
USB volume carrying only `startup.nsh`. Live acceptance established that
Windows Setup discovers the data ISO but UEFI does not, while UEFI discovers
the direct FAT volume but Setup does not accept it as answer media. Keeping the
roles explicit avoids depending on either unsupported cross-layer behavior.

The data ISO does not include UTM's separate answer file, so Setup sees one
authoritative `Autounattend.xml`. That answer wipes only disk 0, creates
EFI/MSR/Windows GPT partitions, selects the declared image index, injects the
matching Windows 11 VirtIO drivers into both Windows PE and the offline
installed image, suppresses automatic activation, creates the administrator,
suppresses the otherwise separate OOBE network page, logs on once, installs
UTM Guest Tools silently, and invokes the seed's OpenSSH bootstrap. Offline
injection is material: WinPE storage access alone does not give Windows OOBE a
NetKVM adapter.

Windows Setup does not define an empty product-key value for guaranteed quiet
installation. For the currently supported `windows-11-pro` edition, the
renderer embeds Microsoft's public Pro KMS client setup key and sets its UI to
`Never`. This selects the catalog edition without supplying a customer key or
activating Windows; activation remains suppressed and must be observed after
installation. The renderer rejects arbitrary editions rather than accepting a
possibly private activation key on its command line.

On macOS, the FAT boot image supplies UEFI Shell `startup.nsh`. The UTM factory maps the
Windows installer as the first filesystem, the data seed as a second CD, and
the boot image as a USB filesystem. The script refreshes mappings, prefers an
installed Windows Boot Manager on any later filesystem, and otherwise launches
the prepared installer's firmware-visible `EFI/BOOT/BOOTAA64.EFI`. This avoids
both an interactive firmware-shell stop and Windows media's `Press any key`
prompt without forcing Setup media again during installation reboots. The
prepared installer exposes the no-prompt loader in its firmware-visible boot
image. Preparation first proves that the official ISO contains both expected,
equal-size Microsoft-signed loaders and that the embedded payload is exactly
the prompted loader; media validation is not an assumption about every ISO.

The checked-in AppleScript configuration surface does not expose UTM's Windows
wizard flags for TPM 2.0 and preloaded Secure Boot keys. The answer media uses
the same Windows Setup hardware-check bypasses shipped on UTM's guest-tools
media only for that ARM64 QEMU recipe. The `amd64` renderer omits every
hardware-check bypass. Its libvirt factory requires native KVM, Q35 UEFI with
enrolled Secure Boot keys, TPM 2.0, at least 8 GiB RAM, six virtual CPUs, and a
128-GiB system disk before Windows Setup starts.

Validate a separately acquired Windows ISO before creation:

```bash
scripts/image-factory.sh validate-media PRIVATE_WINDOWS_ISO
scripts/image-factory.sh prepare-install-media PRIVATE_WINDOWS_ISO
```

The preparation command works with `hdiutil` on macOS and `xorriso` on Linux.
It preserves the verified source ISO and creates an
ignored copy whose El Torito EFI image substitutes Microsoft's equal-size
`cdboot_noprompt.efi` payload for the byte-verified prompted loader. This is
necessary because UEFI maps the small El Torito image, not the ISO's main UDF
tree; the seed cannot execute a loader path that exists only in UDF. The copy
remains private, differs from Microsoft's published whole-ISO digest, and must
not be described as the unmodified download. The Windows payload and both
signed loaders come from the verified public ISO.

The repository deliberately does not download or redistribute Windows. Answer
files are associated with a particular Windows image and should be validated
against that image with Windows System Image Manager before treating a new
edition or release as adopted.

## Create the factory target

With the prepared installer and both seed media present:

```bash
bin/winvm factory-create PRIVATE_NAME \
  .factory.local/windows-install-noprompt.iso \
  .factory.local/winvm-seed.iso \
  .factory.local/winvm-boot.img
bin/winvm pin-target candidate PRIVATE_NAME
bin/winvm up
```

The Linux-hosted native x86_64 route does not need the UTM firmware-shell
image:

```bash
bin/winvm factory-create PRIVATE_NAME \
  .factory.local/windows-install-noprompt.iso \
  .factory.local/winvm-seed.iso
bin/winvm target-id
```

Write the returned exact UUID into private inventory before any accepted
target operation. Rerun common doctor, acquire a target-use claim, and carry
that claim through installation, bootstrap, media detachment, and shutdown.

The UTM recipe creates an ARM64 QEMU VM with UEFI, a 128-GiB NVMe
disk, shared networking, and removable installer, data-seed, and boot-seed
media. Media compatibility, Windows edition/index, driver availability, and
activation are caller-owned inputs and must be proven on the exact ISO.

The libvirt recipe defines but does not start a persistent native x86_64 KVM
domain. It uses CPU host passthrough, Q35, enrolled-key Secure Boot firmware,
an emulated TPM 2.0 CRB device, VirtIO QCOW2 storage and networking, a QEMU
guest-agent channel, a USB tablet, and a private SPICE display for explicit
bootstrap/recovery. Creation refuses an existing name or volume and rolls back
only its exact newly owned domain and volume after a failed definition.

Windows Setup restarts after laying down the system disk, while first logon
still needs the seed. If UEFI remains at `Start boot option`, stop the candidate
through `bin/winvm down`, run `bin/winvm factory-detach-installer`, and start it
again. At this pre-guest firmware boundary there may be no running OS capable
of shutdown; after explicit operator authorization, `bin/winvm force-stop` is
the bounded outer recovery route. That guarded transition requires exactly
three removable drives, removes only the first factory-created installer, and
independently requires both seed drives to remain. It will not guess when the
drive shape differs.

After Windows first-logon bootstrap completes, verify key-only SSH, remove the
one-use answer media and Windows ISO with `bin/winvm factory-detach-media`
while the candidate is stopped, rotate the setup credential, and install
the development appliance through its UUID-bound bootstrap:

```bash
../../scripts/bootstrap-windows.sh --testbed . \
  --profile development winvm
bin/winvm post-update audit --json
```

The unattended first-logon script makes the installed QEMU guest-agent service
automatic and establishes hardened key-only SSH. Authenticated controller
bootstrap then acquires and verifies public development packages and installs
the resident; this avoids placing mutable network packages or credentials on
one-use factory media. The runtime-only profile remains explicit. Detachment
removes every removable drive through UTM's stopped configuration API and
independently confirms that none remain.

After committing the exact controller source, finish the development-appliance
handoff with:

```bash
bin/winvm appliance-certify --json
```

This on-demand path audits without repair, proves a reboot, runs the exact
committed portable and Windows-native source inside the guest, removes its
staging, and leaves the accepted candidate cleanly stopped. It does not derive
another VM or replace the separate Sysprep/export procedure below.

## Generalize and export

Preflight the explicitly pinned candidate:

```bash
bin/winvm generalize --check
```

The preflight refuses an encrypted OS volume because Sysprep cannot generalize
it even when BitLocker protection is suspended. On a dedicated candidate,
decrypt and wait for independent `FullyDecrypted` state with:

```bash
bin/winvm generalize --decrypt
bin/winvm generalize --check
```

Preflight also names every removable, non-framework, non-resource per-user
AppX package that is not provisioned into the image. Sysprep rejects these
packages, including some Windows-serviced packages after Store updates.
Reconciliation is deliberately explicit because it removes an installed
package from the candidate:

```bash
bin/winvm generalize --remove-appx EXACT_PACKAGE_NAME
bin/winvm generalize --check
```

Record each removed application and reinstall it after OOBE if the finished
appliance requires it. The command refuses provisioned, framework, resource,
non-removable, wildcard, and non-exact targets.

The current profile is a same-controller UTM appliance: it disables guest
auto-logon, deletes the LSA auto-logon secret and SSH host identity, cleans
workflow artifacts, retains the controller's public authorized key, and runs:

```text
Sysprep /generalize /oobe /shutdown /mode:vm /quiet
```

Execute only after the candidate has passed acceptance, has no pending reboot
markers, and reports `sysprep_storage_ready`:

```bash
bin/winvm generalize --confirm-target
bin/winvm export-image PRIVATE_ABSOLUTE_OUTPUT.utm
```

Microsoft requires `/generalize` before deploying a Windows image to another
computer, and documents `/mode:vm` only for the same VM/hypervisor hardware
profile. Accordingly, this output is not claimed as a hardware-independent
Windows distribution. Boot it once with `disposable-up`; verify that Windows
enters OOBE and that the provider can stop it without persisting the first
boot, then record the observation in the adjacent private manifest:

```bash
bin/winvm image-manifest PRIVATE_ABSOLUTE_OUTPUT.utm --oobe-confirmed
```

A controller-ready derivative must then provision fresh target identity,
authorization, appliance login policy, and resident-helper readiness.

## Validation record

**Current (2026-08-10):** The seed renderer, XML validation, secret-file
permissions, manifest writer, target-role policy, and mocked provider behavior
pass on the macOS host. The UTM factory AppleScript recipe parses against the
installed UTM dictionary.

A UUID-pinned ARM64 candidate passed the full resident application acceptance
before preparation. Live preflight detected and required explicit resolution
of two real Windows image blockers:

- the OS volume was fully encrypted even though BitLocker protection was off;
  `--decrypt` reached independently observed `FullyDecrypted`; and
- six removable user packages were absent from image provisioning. Exact
  reconciliation removed `Microsoft.VisualStudioCode`, `winapp`,
  `Microsoft.WidgetsPlatformRuntime`, `Microsoft.StartExperiencesApp`,
  `Microsoft.Ink.Handwriting.Main.en-US.1.0.1`, and
  `Microsoft.Winget.Source` from this candidate. Required packages must be
  restored after OOBE.

Sysprep then completed with the declared VM profile and UTM observed a stopped
target. A roughly 53-GiB private UTM bundle and adjacent mode-0600 manifest were
exported under ignored factory storage. A disposable boot visibly reached the
Windows country/region OOBE page; it was stopped cleanly without persisting
that first boot. No screenshot, VM identity, endpoint, account, or bundle path
is committed.

### Public ISO factory acceptance

**Current (2026-08-10):** The ISO-to-new-base lane was exercised with
Microsoft's current public English Windows 11 25H2 multi-edition ARM64 ISO.
The source remained byte-for-byte unchanged throughout preparation; its
published SHA-256 was independently rechecked as
`638AA2C88E94385B00F4F178D071E3DF0B7D9E335577A83BD533B7F2EB65ADF0`
before cleanup. Catalog index 3 installed Windows 11 Pro ARM64 build 26200.
The public Pro installation-only setup key selected that edition, automatic
activation was suppressed, and the installed system remained unactivated in
notification state. No customer activation key was used.

A blank UUID-pinned candidate booted the prepared installer and split seed
media without guest input. Setup consumed `Autounattend.xml`, wiped only the
blank NVMe disk, injected storage/network/guest-agent drivers, and completed
its disk phase. At the expected UTM firmware boundary, a separately authorized
UUID-bound force stop allowed installer-only detachment; both seed media were
independently still present. The next boot completed specialization, OOBE, the
one-time local login, and guest-tools installation without host-driven guest
UI.

The run exposed one fresh-media defect rather than hiding it: Windows OpenSSH
9.5 generated host private keys with an explicit grant for the setup
administrator and refused them with service exit 1067. The bootstrap now
rebuilds those private-key ACLs from the language-independent SYSTEM and
Administrators SIDs before `sshd -t`. That exact repair started `sshd` on the
fresh target; rerunning the checked-in bootstrap produced its normal state and
OpenSSH receipts, key-only SSH survived reboot, and password authentication
remained disabled. The answer-file password was then rotated through a private
file and never appeared in a command argument or durable evidence.

MachineControl installed as an automatic LocalSystem service with a Medium
ordinary helper, pinned Cua 0.17, and the native Windows provider. Default UAC
policy remained enabled (`EnableLUA=1`, consent behavior 5, secure desktop 1).
The live protected suite confirmed both cancellation and approval on
`Winlogon`, target-native secure-desktop capture and semantics, and an
independent High-integrity effect.

Authenticated-remote and target-local runs both completed the Calculator,
Settings, Character Map, and Notepad workflow with independent effects and
owned-artifact cleanup. Current packaged Calculator exposed separate content
and `ApplicationFrameWindow` surfaces; the facade now reports both, uses the
content surface for UIA and the frame for full capture/lifecycle, and confirmed
all four window transitions. Remote Calculator compact/unchanged payload ratios
were 0.702/0.060 and target-local ratios were 0.694/0.053; Settings was
0.773/0.256 in both placements.

The installer had already been detached, so final media removal deleted the
two remaining seed devices and independently observed zero removable drives.
On the subsequent disk-only boot, key-only SSH and the resident protected
route were available before login on `Winlogon`. The rotated password passed
the stock Credential Provider in one target-native request, after which the
Medium helper returned on `Default`; system input, Run-dialog semantics, and
target-native capture remained functional.

The exact disposable candidate was stopped and UUID-confirmed before deletion.
The prior target selection and host-key file were restored byte-for-byte; the
downloaded ISO, prepared copy, both seed images, one-use credentials, captures,
and acceptance artifacts were deleted. The earlier generalized export and its
manifest were not modified and remain stopped. `tests/smoke.sh` and
`tests/image-factory.sh` pass with the final implementation.

## Authoritative references

- [Microsoft Sysprep command-line options](https://learn.microsoft.com/windows-hardware/manufacture/desktop/sysprep-command-line-options?view=windows-11)
- [Microsoft answer files overview](https://learn.microsoft.com/windows-hardware/customize/desktop/wsim/answer-files-overview)
- [Microsoft Windows 11 Arm64 ISO download](https://www.microsoft.com/software-download/windows11arm64)
- [Microsoft Windows 11 x64 ISO download](https://www.microsoft.com/software-download/windows11)
- [Fedora VirtIO Windows drivers](https://docs.fedoraproject.org/en-US/quick-docs/creating-windows-virtual-machines-using-virtio-drivers/)
- [Microsoft Windows Setup configuration passes](https://learn.microsoft.com/windows-hardware/manufacture/desktop/windows-setup-configuration-passes?view=windows-11)
- [UTM scripting reference](https://docs.getutm.app/scripting/reference/)
- [UTM scripting cheat sheet](https://docs.getutm.app/scripting/cheat-sheet/)

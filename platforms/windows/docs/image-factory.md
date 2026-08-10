# Windows Image Factory

This factory has two related paths:

1. create a Windows testbed base from explicit local installation media and a
   locally rendered answer-media ISO; and
2. generalize and export a configured candidate as a stopped UTM appliance.

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
them to UTM's file-URL AppleScript contract.

The answer-media ISO contains a plaintext one-use setup password because that
is the Windows Setup input contract. The renderer accepts that value only from
a mode-0600 file, never an argument or environment variable. Detach and
securely discard the ISO after first-logon bootstrap. The factory keeps the
controller's public SSH key, but never its private key.

## Render unattended answer media

Prepare a mode-0600 file containing one setup password and select a public SSH
key. Then run, for Windows ARM64 image index 1:

```bash
scripts/image-factory.sh render-seed \
  arm64 APPLIANCE_USER 1 PRIVATE_SECRET_FILE CONTROLLER_PUBLIC_KEY \
  PRIVATE_UTM_GUEST_TOOLS_ISO
```

The renderer XML-escapes all substituted values, rejects weak file
permissions, validates the XML when `xmllint` is present, and builds an ISO
with volume label `WINVM_SEED`. It copies UTM's Windows drivers and one
guest-tools installer from explicit local media, but not UTM's separate answer
file, so Setup sees one authoritative `Autounattend.xml`. That answer wipes
only disk 0, creates EFI/MSR/Windows GPT partitions, selects the declared image
index, injects the matching Windows 11 VirtIO drivers, suppresses automatic
activation, creates the administrator, logs on once, installs UTM Guest Tools
silently, and invokes the seed's OpenSSH bootstrap.

The checked-in AppleScript configuration surface does not expose UTM's Windows
wizard flags for TPM 2.0 and preloaded Secure Boot keys. The answer media uses
the same Windows Setup hardware-check bypasses shipped on UTM's guest-tools
media for this QEMU recipe. This is an explicit compatibility compromise for
the dedicated test appliance, not a claim that the VM satisfies Microsoft's
Windows 11 hardware baseline.

Validate a separately acquired Windows ISO before creation:

```bash
scripts/image-factory.sh validate-media PRIVATE_WINDOWS_ISO
```

The repository deliberately does not download or redistribute Windows. Answer
files are associated with a particular Windows image and should be validated
against that image with Windows System Image Manager before treating a new
edition or release as adopted.

## Create the factory target

With the Windows and seed ISOs present:

```bash
bin/winvm factory-create PRIVATE_NAME PRIVATE_WINDOWS_ISO \
  .factory.local/winvm-seed.iso
bin/winvm pin-target candidate PRIVATE_NAME
bin/winvm up
```

The current UTM recipe creates an ARM64 QEMU VM with UEFI, a 128-GiB NVMe
disk, shared networking, and removable Windows/seed media. Media compatibility,
Windows edition/index, driver availability, and activation are caller-owned
inputs and must be proven on the exact ISO.

After Windows first-logon bootstrap completes, verify key-only SSH, remove the
one-use answer media from the stopped VM configuration, rotate the setup
credential, and install MachineControl through its UUID-bound bootstrap.

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

No compatible Windows installation ISO was present locally, so the
ISO-to-new-base lane has not been executed. Its exact remaining live boundary
is media validation, `factory-create`, Windows Setup/image-index compatibility,
first-logon OpenSSH bootstrap, answer-media removal, and subsequent product
installation on that newly created target. The repository does not claim this
lane is proven until explicit licensed media is supplied and that sequence
passes.

## Authoritative references

- [Microsoft Sysprep command-line options](https://learn.microsoft.com/windows-hardware/manufacture/desktop/sysprep-command-line-options?view=windows-11)
- [Microsoft answer files overview](https://learn.microsoft.com/windows-hardware/customize/desktop/wsim/answer-files-overview)
- [Microsoft Windows Setup configuration passes](https://learn.microsoft.com/windows-hardware/manufacture/desktop/windows-setup-configuration-passes?view=windows-11)
- [UTM scripting reference](https://docs.getutm.app/scripting/reference/)
- [UTM scripting cheat sheet](https://docs.getutm.app/scripting/cheat-sheet/)

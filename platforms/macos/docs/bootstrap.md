# Fresh Guest Bootstrap And Recovery

This guide records every layer needed to turn a Tart macOS VM into an
agent-operable testbed. It covers prepared images, vanilla IPSW guests,
host permissions, the guest agent, semantic Accessibility, verification, and
lost-password recovery.

## Bootstrap Outcome

A complete guest has:

- a stable Tart VM name and graphical window;
- a logged-in, non-root desktop user;
- the Tart guest daemon and interactive-user agent;
- working `tart exec` and agent-based IP discovery;
- Xcode Command Line Tools;
- the deployed and ad-hoc signed MacVM UI app;
- explicit Accessibility permission for that app identity;
- explicit Screen Recording permission for that app identity; and
- a warning-free `bin/macvm doctor` result.

The public CLI never stores the guest password. A controller's private
inventory may declare a host-local password file so a VM-creation or recovery
task can hand the credential to later sessions without placing it in Git.

## Host Preparation

Install Tart and clone this repository:

```bash
brew install cirruslabs/cli/tart
cd ~/code/machine-control/platforms/macos
```

Copy `config.example` to ignored `config.local` before a lifecycle mutation.
Set `MACVM_NAME` and `MACVM_EXPECTED_NAME` to the same exact local VM name and
set `MACVM_TARGET_ROLE=candidate`. The mutation guard is on by default, so an
unconfigured public example cannot start or stop a VM. Do not put a password
in that file.

Before creating or changing a candidate, inspect the current path:

```bash
bin/macvm bootstrap-stages preflight --kind prepared --json
# Or use --kind vanilla for an IPSW guest.
```

For an existing exact candidate, run common doctor and acquire its exclusive
claim, then inspect again with `bin/macvm bootstrap-stages --kind prepared
--json` under that claim. The report reads Tart inventory, host capture/input
permission, guest administration, the private credential file's presence and
mode, build tools, resident readiness, Accessibility, and Aqua session state.
It uses stable stage names and evidence codes. Run each suggested command
explicitly and recheck; the inspector does not create or change a VM. `kind`
describes the path chosen by the operator, not a fact inferred from the VM.
Setup Assistant and TCC remain visible consent surfaces. The report names
their gates without acting on them; an agent may choose each authorized action
and recheck it. The `administrator-authorization` stage names the setup or
Command Line Tools gate without accepting a password in the report.
If a direct guest probe sees an unlocked Aqua session while the running
resident reports `unknown`, the report suggests a guarded resident restart.
It still treats the desktop as unverified until doctor observes the result.

The first screenshot and input operation may cause host macOS to request:

- Screen Recording for the invoking terminal or agent host; and
- Accessibility/input-posting permission for the invoking terminal or agent
  host.

Grant those through host System Settings, then rerun:

```bash
bin/macvm doctor
```

## Prepared Cirrus Image

This is the preferred path because non-vanilla Cirrus images already include
the Tart guest agent:

```bash
tart clone ghcr.io/cirruslabs/macos-tahoe-base:latest tahoe-base
# Configure tahoe-base as the exact candidate in config.local first.
bin/macvm up
bin/macvm exec /usr/bin/sw_vers
bin/macvm deploy-ui
bin/macvm authorize-ui
```

Cirrus's prepared-image convention uses a short account name of `admin` and
an initial password of `admin`; the full name may appear as “Managed via
Tart.” Treat that as a public bootstrap credential, not a durable secret.
For a retained VM, write that initial value to the credential file reported by
`bin/machine-control inventory credentials macvm`; if it is changed, replace
that file in the same task. Verify the stored value against the guest login
before using it for authorization. Do not ask the user for this documented
default when the file is present and verified. Never place the value in a shell
argument, repository file, log, or ordinary request.

Continue at [Grant guest Accessibility](#grant-guest-accessibility).

### Image security posture

**Current (2026-09-10), source-reviewed:** Cirrus's
[base-image workflow](https://github.com/cirruslabs/macos-image-templates/blob/main/.github/workflows/base.yml)
explicitly disables SIP after cloning its published vanilla image. This is an
image-build choice, not a requirement imposed by Tart. Do not use the prepared
base's convenience as evidence for a stock protected macOS profile.

The published
[Tahoe vanilla template](https://github.com/cirruslabs/macos-image-templates/blob/main/templates/vanilla-tahoe.pkr.hcl)
does not contain the base workflow's SIP-disable step, but does disable
Gatekeeper and configure automation conveniences. A registry `vanilla` image
is therefore a candidate for a SIP-enabled test, not proof of stock security
posture. It also differs from a fresh IPSW guest: Setup Assistant has already
been completed, and SSH is enabled, although the Tart guest agent is absent.

**Proposal:** For protected-profile testing, clone a published vanilla image
and independently verify `csrutil status` inside the running guest, or create
a fresh guest from Apple IPSW media. Record Gatekeeper state separately with
`spctl --status`; preserve or restore its normal enabled setting when testing
distribution/loading behavior representative of a personal Mac. Record the
actual OS build, plug-in signature, and enabled protection state with each
result. Do not disable SIP to turn a failed protected-profile test into a pass.
The [authorization experiment](../experiments/authorization-unlock/README.md#sip-enabled-guest-test)
defines the bounded screen-unlock test. Its
[SIP-enabled follow-up](../../../docs/tactical/033-macos-sip-authorization-unlock.md)
verified a published vanilla guest with SIP enabled, enabled Gatekeeper using
the normal administration command, and proved plug-in unlock with both on.
The existing guest Screen Sharing service allowed normal consent bootstrap
through a headless client without opening or controlling a host desktop
window; it was disconnected before the native unlock tests.

## Vanilla IPSW Image

Use this path when the guest must be built from Apple installation media:

```bash
tart create --from-ipsw=latest macos-clean
tart set macos-clean --disk-size 80
MACVM_NAME=macos-clean MACVM_EXPECTED_NAME=macos-clean \
    MACVM_TARGET_ROLE=candidate bin/macvm up
```

Set the disk size before the first boot. In the fresh Tahoe acceptance run,
Tart's 50 GB default left only 18.55 GB free after Setup Assistant, while
Apple's Command Line Tools installer required 24.27 GB. An 80 GB virtual disk
left about 61 GB free after the macOS volume was expanded. Increasing an
already installed macOS VM's Tart disk size alone does not expand its APFS
container; follow [Tart's recovery resize procedure](https://tart.run/faq/#disk-resizing)
and verify the guest volume size before retrying installation.

The fresh guest's Command Line Tools installation included an SDK newer than
its running macOS release. The deployment commands select the SDK matching
the guest's macOS major version when it is installed; this avoided a linker
failure in the fresh acceptance run.

`macvm up` launches the graphical VM and reports its power state. It does not
require guest-agent IP discovery to succeed. Check `macvm ip` or doctor
separately when guest administration is needed. It enables suspend support
and mounts this repository read-only as `macvm-testbed`.

Guest system-key capture is enabled only when
`MACVM_CAPTURE_SYSTEM_KEYS=true` is set for `macvm up`. Set it before starting
the VM when Setup Assistant or the consent flow needs guest Command-key
shortcuts. This flag does not itself prove that a synthesized modifier reached
the guest.

Agent-based IP discovery will fail before the guest agent exists, even while
the VM is running. Use only the outer path during this phase:

```bash
MACVM_NAME=macos-clean bin/macvm screenshot
MACVM_NAME=macos-clean bin/macvm click X Y
MACVM_NAME=macos-clean bin/macvm drag X1 Y1 X2 Y2
MACVM_NAME=macos-clean bin/macvm type 'text'
MACVM_NAME=macos-clean bin/macvm key enter
```

### Complete Setup Assistant

Use a screenshot before every coordinate action. Create a local administrator
account and record its credential in a distinct owner-only host-local file
before entering it into Setup Assistant. Set `MACVM_ADMIN_SECRET_FILE` to that
file and use `bin/macvm type-secret` for both password fields after observing
each field's focus. It does not print the password or take it as an argument.
Set `MACVM_GUEST_USER` to the new short account name. A retained VM must have
this credential path registered in the controller's private inventory; check
it with `bin/machine-control inventory credentials macvm` before ending setup.
Do not put the password in this repository.

Until the Tart-window synthetic-key route proves shifted characters on the
current host, use a generated initial password made of lowercase ASCII letters
and digits. This avoids an unobserved case change during account creation.
Verify the stored credential with a subsequent guest login and administrator
authorization. Keep the file owner-only and replace it atomically on rotation.

After the desktop appears, open Terminal through Finder's Applications →
Utilities folder or Finder search, then double-click Terminal. `macvm click X
Y double` can open the observed Finder item. In the fresh Tahoe run, outer
`cmd-space`, `cmd-n`, Shift, and shifted punctuation arrived without their
modifiers, even with Tart system-key capture enabled. Use a screenshot to
verify each action rather than assuming that a modifier took effect.

For the default case-insensitive fresh macOS volume, the bootstrap command can
be entered using only unshifted characters:

```bash
MACVM_NAME=macos-clean bin/macvm type "/bin/bash /volumes/'my shared files'/macvm-testbed/guests/macos/bootstrap/bootstrap-guest.sh --install-homebrew"
MACVM_NAME=macos-clean bin/macvm key enter
```

For an observed initial administrator sheet, the recorded password can use the
same one-shot outer path while its exact VM window is foreground. If macOS
rejects that physical input, stop and request direct user entry. Do not ask
for the password in chat or pass it as a CLI argument.

### Install The Guest Agent

The read-only share should appear inside the guest at:

```text
/Volumes/My Shared Files/macvm-testbed
```

In guest Terminal, run:

```bash
/bin/bash "/Volumes/My Shared Files/macvm-testbed/guests/macos/bootstrap/bootstrap-guest.sh"
```

The script checks the graphical-user boundary, requests one normal `sudo`
authorization, verifies Xcode Command Line Tools, installs
`cirruslabs/cli/tart-guest-agent`, and registers both official service shapes:

- a root launch daemon with `--run-daemon` for disk maintenance; and
- a logged-in-user LaunchAgent with `--run-agent` for clipboard, RPC exec,
  and agent IP resolution.

If Homebrew is absent, the script stops and prints the official installer.
Inspect and run it deliberately, or rerun with `--install-homebrew` to allow
the script to invoke that network installer.

If the repository share is absent, shut down normally and restart through
`macvm up`; do not make a writable copy of the host repository merely to
bootstrap the guest.

Back on the host, verify the new boundary:

```bash
MACVM_NAME=macos-clean bin/macvm exec /usr/bin/id
MACVM_NAME=macos-clean bin/macvm ip
MACVM_NAME=macos-clean bin/macvm deploy-ui
```

## Grant Guest Accessibility

Run:

```bash
bin/macvm authorize-ui
```

`deploy-ui` compiles and ad-hoc signs
`~/Applications/MacVM UI.app`. The helper triggers macOS's normal
Accessibility prompt. Use the outer path to click **Open System Settings**.
If the prepared image's 1024×768 display clips the Accessibility list, check
the exact candidate with `tart get VM_NAME --format json`, then, while holding
its disruptive claim, run
`tart set VM_NAME --display 1280x900 --no-display-refit`. Tart can resize the
running guest. Capture a new screenshot before clicking the now-visible row.
In Privacy & Security → Accessibility:

1. Find the automatically registered **MacVM UI** row.
2. Enable its switch.
3. If macOS asks to modify settings on the prepared base, inspect the password
   sheet and focused field, then use `bin/macvm type-secret` under the exact
   disruptive claim. The command reads the declared owner-only credential file
   after checking the selected Tart window is foreground, and posts physical
   keyboard events without putting the password in arguments or output. Submit
   with `bin/macvm key enter`, then recheck `bin/macvm ui health` for
   `accessibilityTrusted: true`. Do not capture a filled password field or
   retry a failed submission automatically.
4. If the row is absent, click `+` and choose
   `/Users/ADMIN_SHORT_NAME/Applications/MacVM UI.app`, substituting the guest
   short account name configured as `MACVM_GUEST_USER`.
5. Rerun `bin/macvm authorize-ui` and `bin/macvm doctor`.

The physical-keyboard route passed the fresh prepared image's initial
Accessibility sheet. If a later sheet rejects that route, stop and request
direct user entry; do not weaken TCC or guess another password. Once the stable
resident is trusted, matching normal Aqua administrator sheets use the bounded
one-shot path documented in
[macOS UI automation](ui-automation.md#administrator-authorization-sheets).

After Accessibility, run `bin/macvm doctor`. If capture is unavailable, the
stage report suggests a display capture request; invoke it deliberately to
open macOS's Screen Recording prompt:

```bash
bin/macvm control '{"operation":"capture","scope":"display"}'
```

In **Privacy & Security → Screen & System Audio Recording**, enable **MacVM
UI**. Restart the resident with `bin/macvm ui resident-restart`, then recheck
doctor. The fresh prepared run needed this process restart before the new
capture grant became visible to its resident.

System-key shortcuts require the VM to have been started through `macvm up`
or another `tart run --capture-system-keys` invocation. If Command-Shift-G is
consumed by the host, shut the guest down normally and restart it through the
CLI before repeating the consent flow.

Never use `sqlite3`, filesystem replacement, recovery-mode copying, or any
other technique to modify the TCC database. The visible consent is part of the
testbed contract.

## Verification

Run the full diagnostic:

```bash
bin/macvm doctor
```

Then exercise each independent layer:

```bash
bin/macvm exec /usr/bin/sw_vers
bin/macvm screenshot
bin/macvm ui apps
bin/macvm ui windows --app Finder
bin/macvm ui tree --app Finder --interactive --depth 6
```

For reversible input verification, launch TextEdit, inspect its tree, create a
new untitled document, type a unique marker, inspect it, then close without
saving. Do not use an existing user document as a smoke fixture.

## Routine Restart And Suspend

Use guest shutdown when an OS restart boundary matters:

```bash
bin/macvm shutdown
bin/macvm up
```

Use suspend for routine lab parking when the VM was started by `macvm up`:

```bash
bin/macvm suspend
bin/macvm up
```

A Tart suspend snapshot is local to the physical host. It is not a backup,
portable image, or authority for provider-session ownership.

A snapshot can be restored only while the host user's console session is
unlocked. On a controller that may be locked when the VM is next started, set
`MACVM_SUSPENDABLE=false` and park the VM with `shutdown`; doctor then omits
`suspend` and reports why. To cold boot a VM whose snapshot cannot be
restored, accepting the loss of its suspended memory:

```bash
bin/macvm discard-suspended-state
bin/macvm up
```

## Lost Password

Do not guess indefinitely or place candidates in commands.

For a disposable prepared image, the safest recovery is to clone a new VM
under a new name, verify it, and deliberately move only required project
artifacts. Do not delete the old VM until the user confirms the replacement.

For a guest with irreplaceable state:

1. Stop it normally when possible.
2. Start it interactively with `tart run --recovery VM_NAME`.
3. Use macOS Recovery's password-reset utility or Recovery Terminal under the
   user's direct supervision.
4. Restart normally and re-run `doctor`; TCC and keychain-backed state may
   require fresh consent or repair.
5. Replace the private inventory's declared host-local credential file with
   the recovered password and verify it with `inventory credentials macvm`.

Password reset can affect the login keychain. Preserve the VM first with a
named Tart clone or export when its state matters, and do not perform the
reset autonomously.

## Rebuilding And Updating

After updating Tart, the guest agent, macOS, or the UI helper:

```bash
bin/macvm bootstrap --profile development
bin/macvm post-update audit --profile development
```

Bootstrap verifies Xcode/Swift plus the declared profile tools, deploys the
checked-in resident and maintenance support idempotently, and installs the
stable resident as a per-user Aqua LaunchAgent. It does not launch an
interactive installer, install Homebrew, or change consent. Missing tools are
reported as a bounded failure. Runtime omits development-tool readiness;
development additionally requires Git and Python for exact-source checks.

The post-update audit is read-only and refuses a stopped VM before its selected
guest transport can start anything. It verifies the guest-agent daemon and
interactive agent, logged-in Aqua session, signed resident bundle, resident
LaunchAgent/socket, semantic and capture consent effects, target-native status,
and profile tools. macOS does not expose one reliable local pending-reboot
marker, so that check is explicitly optional and not observable rather than
silently reported clear.

If audit identifies a launchd/startup failure on the exact retained candidate:

```bash
bin/macvm post-update repair --profile development
# Request a reboot only when it is actually intended:
bin/macvm post-update repair --profile development --reboot
```

Repair redeploys the same signed application identity and checked-in support,
then starts or restarts only the enumerated existing launchd jobs. It does not
edit TCC or acquire tools. A missing guest command transport remains a separate
bootstrap/recovery boundary because the operation cannot repair the route it
needs to run.

For the heavier exact-source, reboot, native-check, cleanup, and clean-shutdown
proof, start from a clean commit and run:

```bash
bin/macvm appliance-certify --profile development
```

`deploy-ui` still accepts `--force`. A changed or forced ad-hoc build keeps the
`com.kzahel.macvm-testbed.ui` bundle identifier, but macOS may retain the old
code requirement with a misleading enabled switch. If semantic control loses
trust after a rebuild:

1. select the stale **MacVM UI** row and remove it with `-`;
2. rerun `bin/macvm authorize-ui`;
3. click **Open System Settings** and enable the newly registered row; and
4. rerun `bin/macvm doctor`.

Do not weaken the diagnostic or patch TCC state.

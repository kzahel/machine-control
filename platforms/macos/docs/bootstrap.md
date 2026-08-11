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
- explicit Accessibility permission for that app identity; and
- a warning-free `bin/macvm doctor` result.

The CLI never needs or stores the guest password.

## Host Preparation

Install Tart and clone this repository:

```bash
brew install cirruslabs/cli/tart
cd ~/code/machine-control/platforms/macos
```

Copy `config.example` to ignored `config.local` only when the VM name or
defaults differ. Do not put a password in that file.

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
bin/macvm up
bin/macvm exec /usr/bin/sw_vers
bin/macvm deploy-ui
bin/macvm authorize-ui
```

Cirrus's prepared-image convention uses a short account name of `admin` and
an initial password of `admin`; the full name may appear as “Managed via
Tart.” Treat that as a public bootstrap credential, not a durable secret.
Change it for any non-disposable guest and never place it in a shell command,
repository file, or agent message.

Continue at [Grant guest Accessibility](#grant-guest-accessibility).

## Vanilla IPSW Image

Use this path when the guest must be built from Apple installation media:

```bash
tart create --from-ipsw=latest macos-clean
MACVM_NAME=macos-clean bin/macvm up
```

`macvm up` launches the graphical VM with:

- suspend support;
- guest system-key capture; and
- this repository mounted read-only as `macvm-testbed`.

It may eventually report that agent-based IP discovery failed. That is
expected before the guest agent exists; the VM remains running. Use only the
outer path during this phase:

```bash
MACVM_NAME=macos-clean bin/macvm screenshot
MACVM_NAME=macos-clean bin/macvm click X Y
MACVM_NAME=macos-clean bin/macvm drag X1 Y1 X2 Y2
MACVM_NAME=macos-clean bin/macvm type 'text'
MACVM_NAME=macos-clean bin/macvm key enter
```

### Complete Setup Assistant

Use a screenshot before every coordinate action. Create a local administrator
account and record its credential in the user's approved password manager,
not in this repository or the agent transcript.

After the desktop appears, open Terminal through Spotlight:

```bash
MACVM_NAME=macos-clean bin/macvm key cmd-space
MACVM_NAME=macos-clean bin/macvm type Terminal
MACVM_NAME=macos-clean bin/macvm key enter
```

The user may need to enter the new password directly for administrator
actions. Agents must not ask for it in chat or pass it as a CLI argument.

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
In Privacy & Security → Accessibility:

1. Find the automatically registered **MacVM UI** row.
2. Enable its switch.
3. If macOS asks to modify settings, enter the guest administrator password
   and submit the authorization directly in the Tart window.
4. If the row is absent, click `+` and choose
   `/Users/ADMIN_SHORT_NAME/Applications/MacVM UI.app`, substituting the guest
   short account name configured as `MACVM_GUEST_USER`.
5. Rerun `bin/macvm authorize-ui` and `bin/macvm doctor`.

An authorization sheet may reject synthesized mouse and keyboard events even
when ordinary guest UI accepts them. That is a secure-input boundary, not an
outer-control failure. The user performs any password submission directly;
the agent resumes with the remaining non-secret UI.

This direct-user requirement applies here because MacVM UI does not yet have
Accessibility permission. Once the stable resident is trusted, matching normal
Aqua administrator sheets use the bounded one-shot path documented in
[macOS UI automation](ui-automation.md#administrator-authorization-sheets).

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

Password reset can affect the login keychain. Preserve the VM first with a
named Tart clone or export when its state matters, and do not perform the
reset autonomously.

## Rebuilding And Updating

After updating Tart, the guest agent, macOS, or the UI helper:

```bash
bin/macvm deploy-ui
bin/macvm doctor
tests/smoke.sh
```

`deploy-ui` compares the installed sources and skips compilation and signing
when the app is already current. `--force` always rebuilds. A changed or forced
ad-hoc build keeps the `com.kzahel.macvm-testbed.ui` bundle identifier, but
macOS may still retain the old code requirement with a misleading enabled
switch. If semantic control loses trust after a rebuild:

1. select the stale **MacVM UI** row and remove it with `-`;
2. rerun `bin/macvm authorize-ui`;
3. click **Open System Settings** and enable the newly registered row; and
4. rerun `bin/macvm doctor`.

Do not weaken the diagnostic or patch TCC state.

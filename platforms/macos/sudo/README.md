# Native administrator authentication

`mc-sudo [--timeout SECONDS] -- COMMAND [ARGUMENTS...]` runs one command
through the installed `/usr/bin/sudo` with a native AppKit password dialog.
The CLI is Rust; a small Swift bridge owns process inspection, code identity,
and the secure password field. The desktop app bundles both executables in
`Contents/Resources` and signs them with the app publisher.

The dialog shows the resolved executable, separate quoted arguments, working
directory, and observed requester process ancestry. Default authentication
wait is 120 seconds (allowed range 1–300). Cancel, timeout, loss of the unlocked
console session, or wrapper termination ends the prompt. A bad password fails
without opening another dialog. Standard input/output and command exit status
are inherited; arguments are never expanded through a shell.

The password goes from the native secure field to sudo's private askpass pipe.
No password crosses Rust, YA, JSON, a WebView, arguments, environment, logs,
or a credential store. Native string copies cannot guarantee complete memory
zeroization. Do not place other secrets in command arguments: those arguments
are deliberately displayed and already observable in process listings.

## Authority

Sudo's existing policy and authentication remain authoritative. `-A -k`
ignores existing authentication timestamps and creates no new timestamp for
this invocation. Existing NOPASSWD rules still work without a prompt. This
installs no root daemon, setuid binary, sudoers rule, or passwordless grant.
The timeout bounds authentication, not the authenticated command's runtime.
The command and its descendants can have full root authority, including
persisting changes; approval does not revoke their effects afterwards.

The helper accepts context once over a private mode-0700 Unix socket directory.
Both sides authenticate kernel peer PID, exact installed executable, signed
code identity and publisher, and the wrapper → system sudo → askpass chain.
System sudo is unreadable by ordinary users on modern macOS; its identity uses
kernel signing flags, root-owned non-writable setuid path, and effective UID.
Direct askpass calls fail before presenting a dialog. Debug/ad-hoc builds can
run for development; release and YA installation checks require publisher
signatures. The process tree is informative. An agent with a same-user shell
is not contained by this wrapper or protected from other same-user code.

When authentication is required, locked, logged-out, headless, or non-console
sessions refuse. The prompt is
local to the Mac; a remote YA browser does not receive or approve it. Other OS
implementations and Touch ID are not provided by this slice.

## Build and validation

Run `cargo test --locked` and `cargo clippy --locked --all-targets -- -D warnings`
from this directory. `desktop/src-tauri/build.rs` builds the correct target
architecture; the desktop signing pipeline signs both native resources before
the enclosing app. `cargo build --release --target x86_64-apple-darwin` checks
the Intel build on an Apple silicon development host with that Rust target.

The dedicated-appliance fixture is built with
`python3 tests/macos/build-sudo-fixtures.py --output BUILD_DIRECTORY` from the
repository root. Supply a Developer ID identity to test release signatures.
Never install the AX credential driver on a personal workstation. Its transient
app uses the appliance's existing Machine Control consent identity.

After doctor and claim acquisition, run `tests/macos/sudo-conformance.py` with
`--target`, `--claim`, `--helpers`, `--driver-app`, and the canonical
`--secret-file` resolved through `inventory credentials`. The file must be
owner-only. It is streamed only after exact signed helper/dialog/secure-field
discovery. The harness temporarily overrides two exact commands to require a
password, validates sudoers, and removes the rule and fixtures in `finally`.
The caller owns power restoration and claim release.

Current status and limits: [native sudo topic](../../../topics/native-sudo.md).

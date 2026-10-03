# Make the Windows desktop executable discoverable to agents

Status: implemented; native Windows x64 developer acceptance passed.
Signed release acceptance and ARM64 installed acceptance remain open.

Owning topic: [Installed agent CLI](../../topics/installed-agent-cli.md).
Related: [Native distribution](../../topics/native-distribution.md),
[Windows platform report](../../research/platforms/windows.md), and
[Python packaging](../../research/providers/python-build-standalone.md).

## Objective

An unfamiliar agent found the desktop executable but needed installation-path
guidance to reach the bundled CLI. The maintainer requested a plan for one
obvious automation entry point, PATH discovery, and useful output even when
the agent simply launches the application. Preserve Python as the command
implementation and normal double-click use as a desktop application.

**Baseline — source review before implementation:** The Windows GUI executable
did not forward CLI commands and its argument rejection printed Mac-oriented
usage. The installed terminal entry was `mc-cli/commands/machine-control.cmd`;
installer hooks did not register a PATH command. Offline identity read package
metadata without resolved installation paths. This was source evidence, not an
inspection of the reporting user's installed machine.

## Implemented Windows user contract

**Decision:** Make `machine-control.exe` the public Windows entry point for
both desktop launch and automation. Retain the existing bundled command for
compatibility and direct Python development.

| Invocation | Behavior |
| --- | --- |
| Double-click or ordinary graphical launch | Open or focus the operator UI as today, without creating a console window. |
| Bare `machine-control` from a shell or captured agent subprocess | Ensure the desktop app is running, print a short introduction and observed readiness/access status, then return. Do not focus an already-running app for this automation invocation. |
| `machine-control --help` | Print command help and exit without starting, focusing, or contacting the resident. Include the agent-instructions entry. |
| `machine-control agent instructions` | Print the full owned workflow and exit offline. |
| `machine-control agent identity` | Print the existing machine-readable offline client receipt, then exit. Add `--paths` for resolved installation details. |
| Other CLI commands | Forward to the bundled Python implementation, preserving arguments, streams and exit status. Do not add a banner or implicitly start the app. |
| Existing internal launch modes | Preserve startup, update, restart and background semantics; do not send their arguments to Python. |

Illustrative bare-launch output, only when these states have been observed:

```text
Machine Control is running. Desktop access is off.

Agent instructions: machine-control agent instructions
Available commands: machine-control --help
Installation details: machine-control agent identity --paths
```

Use unknown/unavailable wording when access or readiness cannot be observed.
Report launch acceptance separately from resident readiness. Bound startup
waiting, return nonzero on failure, and give an actionable diagnosis. Starting
the app does not enable access, approve grants, or acquire/borrow a target-use
claim. Existing claims and approval rules continue to govern target operations.
The bare-launch probe must stay within unclaimed read-only discovery; if richer
status requires a claim, omit that status and point to the claimed workflow.

**Decision:** Offer an installer option, initially selected, to add the desktop
installation directory to the current user's PATH. The main executable is the
command; avoid adding both it and the nested command directory. Preserve the
choice across upgrades, including passive updates. Silent installation must
have documented enable/disable behavior. Implementation uses a first-install
default of on, with `/ADDTOPATH=0|1` and the previous preference retained.

**Decision:** Include a short README beside the executable and a pointer in
`runtime`. Lead with `machine-control.exe agent instructions`, explain that
Python is bundled, and provide an absolute-path invocation example for stale
PATH environments. Explain the desktop launcher versus the resident companion.

## Completion conditions and boundaries

- Finding the main executable is sufficient to read help, instructions and
  identity and run the existing command vocabulary without system Python.
- A bare captured launch produces useful text and finishes promptly, both
  with an existing app and after starting it. The app remains usable after
  the launching command finishes normally.
- A fresh eligible Windows user environment can resolve the PATH command.
  Existing processes with stale environments can use the absolute path.
- Offline identity distinguishes the invoked installation from a source
  checkout or another installed bundle without claiming which resident is
  actually running.
- Ordinary command output remains parseable, and CLI invocations never
  enter the GUI single-instance focus path.
- Installer repair, upgrade and uninstall preserve unrelated PATH entries,
  installations and user preferences.

This slice targets the Windows desktop bundle. It does not change the
ProgramData appliance/component service into the desktop product, migrate
installations, redesign the Python client, introduce a persistent command
worker, or alter native access/authorization. Optional skills/tool integrations
and automatic modifications to global agent instructions are outside scope.
Keep macOS/Linux behavior unchanged during this slice; retain a portable
command vocabulary. Their discovery implementations are explicit follow-ups
in the owning topic's [platform tracker](../../topics/installed-agent-cli.md#agent-discovery-across-desktop-platforms),
not work completed or dropped by finishing Windows. Publication and deployment
are separate follow-up work.

## Ordered work

### 1 — establish Windows launch and output behavior

Use a bounded native command-driven probe before changing the full launcher.
Exercise PowerShell, cmd, direct subprocess capture and redirected files.
Determine how the GUI-subsystem executable receives valid inherited pipes and
attaches to a caller's console without replacing redirected handles or opening
a new console on double-click. Cover missing input handles and closed streams.

Resolve how a bare invocation distinguishes graphical use from terminal or
captured use. Do not infer agent identity from a parent process name. Preserve
explicit internal launch modes so a detached GUI child cannot recursively
invoke the bare CLI path. If handle-based detection is ambiguous in supported
launchers, document the limitation and propose an explicit launch mode for
review before changing the agreed default behavior.

Measure direct bundled-command versus main-executable invocation for help,
identity and a read-only resident operation. Record cold and repeated warm
wall-clock timings and distributions on the same machine. Dispatch before
Tauri/WebView initialization; do not promise a latency budget without evidence.
Review a material regression before proceeding with PATH rollout.

### 2 — forward commands and make bare launch finish

Add early argument routing in the desktop native entry point. Spawn the exact
bundled interpreter with its existing isolation flags and launch script using
an argument vector, not shell interpolation. Preserve stdin for existing
command protocols, stdout/stderr separation, Unicode, quoting, exit status and
cancellation. Missing payloads must fail clearly without falling back to system
Python or an older checkout.

Handle bare automation launch separately from command forwarding. Start only
the installed desktop app when absent, using a detached GUI mode with no
inherited capture pipes. Probe readiness with a deadline and account for
concurrent launch attempts, a hung existing app and another installation owning
the endpoint. Do not kill or replace an ambiguous existing resident.

The short-lived launcher must close its output and return independently of
the long-lived operator. Test shell exit, pipe EOF and representative caller
job cleanup. A successful spawn alone does not prove independence from an
agent harness's process/job lifetime; record any unsupported host behavior.
Already-running automation discovery must not focus the UI or change grants.

### 3 — identify the installation and provide nearby guidance

Extend offline identity with resolved launcher, CLI root/entry, interpreter,
installation root and bundled resident paths, distinguishing the actual
invocation from the canonical public entry point where necessary. Source
identity must remain explicitly source-based; relocated bundles resolve their
new location at runtime. Do not bake build-machine paths into signed metadata.

Keep the authenticated static receipt separate from computed diagnostic paths.
Review `client-identity-v1.schema.json` and existing consumer expectations before
choosing an additive compatible representation or a versioned change. Resolved
paths are diagnostics, not publisher verification or proof of a live resident.
Use the existing live doctor/status route for observed resident identity and
report ambiguity honestly. Keep concrete paths out of committed evidence.

**Decision from consumer review:** Existing consumers parse the receipt strictly
and compare the offline response to it exactly. Keep default `agent identity`
unchanged and expose the additional diagnostics with `agent identity --paths`.
The public launcher and adjacent guidance advertise that explicit form.

Package the two README pointers with the appropriate payload inventories and
signatures. Refresh agent guidance for explicit bare-launch startup while
retaining the rule that ordinary control commands do not start a replacement
resident. Keep help and full instructions generated from the owned CLI rather
than duplicating a Rust command catalog.

### 4 — register and maintain the user PATH command

Implement the installer option with the existing per-user NSIS installation.
Notify Windows of the environment change. Avoid duplicate entries, preserve
unrelated values and registry value types, and never rewrite PATH through a
truncating helper. Record whether this installation owns the inserted entry.
Repair must be idempotent; uninstall removes only its owned exact entry.
Handle custom paths, Unicode/spaces, opt-out, changed install locations, and
multiple installations without deleting another installation's registration.

Explain that already-running shells and agent host applications may retain
their old PATH; a new conversation alone may not refresh it. PATH enables
command lookup but does not automatically advertise the tool to an agent.
Do not terminate or restart user applications to refresh their environments.

### 5 — prove installed discovery and record acceptance

Extend the existing installed-CLI and Windows installer verification runners.
Run deterministic checks first, then command-driven native Windows acceptance
in a dedicated claimed appliance. Use its doctor, exclusive claim and cleanup
rules; preserve the original installed product, registry and power state.

Use the existing Machine Control route to arrange and observe candidate tests
where possible, invoking the candidate launcher separately. Keep a diagnostic
route available while testing app absence and launch failure; the candidate
must not be the only way to determine whether its own startup succeeded.

### 6 — hand off the remaining desktop platforms

Update the owning topic's platform tracker with actual Windows acceptance and
any outstanding Windows cells. Keep macOS and Linux marked as open follow-ups.
Record reusable contract decisions, platform-specific limitations and the next
actions for their separate implementation tacticals. Do not mark cross-platform
discovery complete or begin those implementations as part of Windows closeout.

## Validation and evidence

Cover the following against an installed candidate, not only a source build:

- Main-executable help/instructions/identity with the app stopped, running,
  unavailable, and with access off; offline commands leave app state unchanged.
- PowerShell, cmd and direct captured subprocesses, including pipelines,
  redirected stdout/stderr, argument quoting, Unicode and nonzero exits.
- Bare launch with app absent/present, concurrent launches, timeout/failure,
  caller exit, capture EOF and no unintended foreground change.
- A real forwarded CLI operation through existing doctor/claim/access flow;
  verify its independent fixture effect and refusal with access off.
- Isolated PATH and no system Python, unrelated working directory, relocated
  payload, custom install path, missing interpreter and conflicting older
  installations. Identity must identify the invoked bytes' location honestly.
- PATH opt-in/opt-out, clean install, repair, passive upgrade and uninstall;
  fresh versus deliberately stale parent environments; unrelated/pre-existing
  entries and another installation remain intact.
- Normal graphical launch, tray, startup, restart, updater and existing
  single-instance behavior remain valid.
- Current installed consumers accept the identity evolution and authenticated
  payload inventories; JSON commands contain no extra discovery text.
- Measured forwarding overhead, with methodology and cold/warm results.

Build/package checks cover x64 and ARM64; native execution evidence is recorded
separately for each architecture. Do not infer native acceptance from a build.
Use appropriate Rust/Python checks; if resident .NET code changes, also run the
required format check, contract suites and Windows publishes. GUI routing may
need bounded headed acceptance after deterministic checks; avoid manual UI work
when the existing harness can establish the behavior.

If shared Python identity/guidance or common launcher code changes, run the
relevant automated regressions and installed smoke in dedicated claimed Mac
and Linux appliances. Check existing help/instructions/identity, bundled Python,
relocated paths, clean command output, normal startup/restart and one ordinary
claimed operation. These checks preserve existing behavior; new Mac/Linux
command registration and bare-launch behavior remain outside this slice. Record
unavailable platform coverage explicitly rather than implying it passed.

## Windows reference constraints

Windows documents [environment inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables)
and [environment change notification](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange).
These support PATH discovery in refreshed environments, not retroactive updates
to every running agent process.
[AttachConsole](https://learn.microsoft.com/en-us/windows/console/attachconsole)
documents GUI-subsystem console attachment and the inherited-handle exception;
native tests must establish the complete launcher/pipe behavior.

## Result

**Current — implemented and native-tested on Windows x64:** The main EXE is
an early CLI dispatcher over the pinned bundled interpreter. It preserves
command streams, arguments and exit status without initializing Tauri for CLI
commands. Bare terminal/captured launch and `--start` ensure the same installed
app is running, print bounded guidance and leave access approval unchanged.
Graphical launch remains available through `--gui`; internal background launch
does not focus an existing instance. Installer PATH choice, ownership-aware
registration, adjacent README pointers and opt-in resolved identity are present.

The native candidate is an unsigned developer NSIS package built from the
implementation commit `83797eb`. It is not the published 0.5.3 package. No
release, signing, channel promotion or public deployment was performed.

### Acceptance recorded

| Surface | Evidence and scope |
| --- | --- |
| Native build | Full x64 desktop and NSIS build; native `cargo fmt --check`, Clippy with warnings denied, and all four Rust tests passed. Resident and medium fixture x64 publishes succeeded; resident source was unchanged. |
| Offline EXE | Help, instructions and exact receipt identity passed with the operator stopped; no system Python on child PATH, unrelated working directory, invalid Python environment variables, relocated Unicode bundle and missing-interpreter refusal were covered. |
| Streams and shells | Captured stdout/stderr, piped PowerShell, cmd batch, redirected file, Unicode/quoted/empty/trailing-backslash arguments, stdin and exit status 37 passed. An owned real console independently observed help in its buffer. |
| Startup and lifetime | Two concurrent bare launches, repeated launch and `--start` passed. The operator survived normal actor exit and closure of a kill-on-close job allowing explicit breakaway. Repeated automation discovery preserved foreground focus. The launcher uses its installation as the app working directory so it cannot pin an agent's temporary directory. |
| Native control | Exact local doctor and a separate local claim preceded access-off refusal and granted fixture control through the main EXE. The fixture's independent counter and captured-artifact SHA-256 confirmed effects; claims were released and access stopped. `--gui` exercised the existing single-instance operator window. |
| Installed lifecycle | Custom directory with spaces/Unicode, PATH opt-in/out, repair preference retention, no duplicate entry, fresh environment resolution, deliberately stale parent environment, and uninstall restoring the original PATH passed. Original product registration was restored. |
| PATH edge cases | Native isolated-registry tests covered long values, registry type, unrelated/user-owned equivalents, and empty versus absent PATH. A directory containing a PATH delimiter refuses registration while allowing explicit opt-out and uninstall. |
| Failure contracts | Relocated missing interpreter and another resident image refusal were covered. Deterministic tests cover readiness deadline failure and a caller job refusing breakaway; the latter is not a live restrictive-job acceptance claim. |
| Compatibility | Default identity remains exactly the static receipt required by existing strict consumers. `--paths` adds runtime diagnostics only when requested. 151 common client tests and 68 release/packaging tests passed (one Windows registry test skipped on the Mac runner and separately passed natively); Mac and Linux relocated installed-CLI offline smoke passed. |

Ten sequential identity calls per route in the final full acceptance sample
measured EXE first/warm-median **278.38/278.15 ms**, versus legacy command
**288.31/284.59 ms**. Nine calls after the first supplied each median; EXE warm
samples ranged 273.80–294.02 ms, legacy 279.72–298.10 ms. Earlier idle runs
varied by a few milliseconds in either direction. This establishes no material
forwarding regression for this VM and operation; it is not a cold-cache,
help-command or resident-operation benchmark, or a latency guarantee.

The acceptance scripts live under `tests/windows/discovery*`. The installer
runner restores registry state in `finally`, waits for the real NSIS uninstall
process (not its temporary launcher), and retains private recovery metadata.
Native console creation avoids inherited log handles and reserves sufficient
scrollback for the oracle. The original installation's file hashes and count
were independently checked after lifecycle testing. All 2,373 original files
matched, original registration was restored, task artifacts and candidate
processes were removed, the canonical credential locator remained ready, and
the appliance returned to its original powered-off state. The exclusive
controller claim was released. Machine-specific evidence and registry backups
stay outside this public repository.

### Remaining release gates and follow-ups

- Full ARM64 desktop/package build and native ARM64 installed acceptance remain
  open. The new launcher module type-checked for x64 and ARM64; that does not
  establish full ARM64 packaging or execution.
- Signed installer/catalog verification and a real passive updater cycle must
  run in the next release. The native lifecycle evidence here covers a developer
  installer and silent repair; it does not establish signed upgrade acceptance.
- Explorer double-click, logon startup, tray and restart/update UI need the
  existing release regression pass. This slice exercised explicit graphical
  single-instance opening and background startup, not every lifecycle trigger.
- Windows GUI-subsystem commands can return an interactive shell prompt before
  finishing. Scripted PowerShell callers should pipe output or use a waiting
  process API. Bare context detection cannot infer intent when a launcher hides
  all handles; `--start` and `--gui` select the desired behavior explicitly.
- A host job that forbids process breakaway receives startup failure. Supporting
  such a host requires its process-lifetime policy to permit independent apps;
  silently claiming successful detached startup is not acceptable.
- Mac/Linux offline bundled-CLI regressions passed. Full native GUI/lifecycle
  and claimed-control regressions on those platforms were not run in this
  Windows slice. Their new discovery implementations remain open in the
  [topic tracker](../../topics/installed-agent-cli.md#agent-discovery-across-desktop-platforms).

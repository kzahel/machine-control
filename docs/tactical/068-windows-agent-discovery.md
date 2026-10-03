# Make the Windows desktop executable discoverable to agents

Status: active. Windows implementation and incremental commits authorized;
publication remains separate.

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

**Current — source review:** The Windows GUI executable does not forward CLI
commands. Its argument rejection prints Mac-oriented usage. The installed
terminal entry is `mc-cli/commands/machine-control.cmd`; installer hooks do
not register a PATH command. Offline identity reads package metadata without
resolved installation paths. This is source evidence, not a fresh inspection
of the reporting user's installed machine.

## Proposed user contract

**Proposal:** Make `machine-control.exe` the public Windows entry point for
both desktop launch and automation. Retain the existing bundled command for
compatibility and direct Python development.

| Invocation | Behavior |
| --- | --- |
| Double-click or ordinary graphical launch | Open or focus the operator UI as today, without creating a console window. |
| Bare `machine-control` from a shell or captured agent subprocess | Ensure the desktop app is running, print a short introduction and observed readiness/access status, then return. Do not focus an already-running app for this automation invocation. |
| `machine-control --help` | Print command help and exit without starting, focusing, or contacting the resident. Include the agent-instructions entry. |
| `machine-control agent instructions` | Print the full owned workflow and exit offline. |
| `machine-control agent identity` | Print machine-readable offline client identity and resolved installation details, then exit. |
| Other CLI commands | Forward to the bundled Python implementation, preserving arguments, streams and exit status. Do not add a banner or implicitly start the app. |
| Existing internal launch modes | Preserve startup, update, restart and background semantics; do not send their arguments to Python. |

Illustrative bare-launch output, only when these states have been observed:

```text
Machine Control is running. Desktop access is off.

Agent instructions: machine-control agent instructions
Available commands: machine-control --help
Installation details: machine-control agent identity
```

Use unknown/unavailable wording when access or readiness cannot be observed.
Report launch acceptance separately from resident readiness. Bound startup
waiting, return nonzero on failure, and give an actionable diagnosis. Starting
the app does not enable access, approve grants, or acquire/borrow a target-use
claim. Existing claims and approval rules continue to govern target operations.
The bare-launch probe must stay within unclaimed read-only discovery; if richer
status requires a claim, omit that status and point to the claimed workflow.

**Proposal:** Offer an installer option, initially selected, to add the desktop
installation directory to the current user's PATH. The main executable is the
command; avoid adding both it and the nested command directory. Preserve the
choice across upgrades, including passive updates. Silent installation must
have documented enable/disable behavior. Confirm the default during
implementation review rather than treating it as shipped policy.

**Proposal:** Include a short README beside the executable and a pointer in
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

Planning only. No launcher, installer, identity schema or package behavior has
changed through this tactical. Console-mode detection, caller-job lifetime,
measured overhead and identity compatibility remain implementation gates.

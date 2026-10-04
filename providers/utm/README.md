# UTM CLI diagnostics

The Windows and Linux UTM shell providers and shared UTM workspace provider
run `utmctl` through `cli.py`. Logging is automatic for calls from this
checkout; an older installed/distributed copy must be updated separately.
Direct `utmctl`, AppleScript, and the Python factory-stage probes are outside
this wrapper's logging coverage. The factory-stage probes do share the
automation-health guard described below.

On macOS the private log folder is
`~/Library/Logs/MachineControl/providers/utm/`. `calls.jsonl` rotates to
`calls.1.jsonl` and `calls.2.jsonl` at 1 MiB per segment (up to one extra row).
Other POSIX fixture hosts use
`${XDG_STATE_HOME:-~/.local/state}/machine-control/utm/`.
Tests can override the directory with `MACHINE_CONTROL_UTM_DIAGNOSTICS_DIR`.
Directories are mode 0700; files are mode 0600. Nothing is uploaded.

Each call records intent, child PID after launch, and result with a correlation
ID, UTC timestamp, source adapter, allowlisted command category, UTM bundle
version/build, macOS version, wrapper/caller PID, duration, exit status or
signal, and closed error
categories. Match the child PID and time against macOS reports in
`~/Library/Logs/DiagnosticReports/utmctl-*.ips`. A missing result is an unknown
outcome, not permission to replay a mutating command. Rotation can remove
older correlation records.

Arguments, VM names/IDs, paths, environment, stdin, stdout, and raw stderr are
never persisted. Stderr is streamed to its original recipient and scanned in
bounded memory. A category is a diagnostic hint: guest-controlled text can
match a marker. Exit zero still does not prove a guest effect. Existing
callers retain responsibility for independently observing effects.

The wrapper does not retry commands, change authorization, or repair UTM.
Before connecting to a real UTM app bundle it performs a bounded read-only
AppleScript inventory-health check. An unavailable bridge, stopped app, or
explicitly unready library returns exit 69 without launching `utmctl`; the
result log records the refusal. The probe uses raw UTM dictionary codes and
passes the bundle path as data. It does not activate or start the application.
CLI help bypasses the probe. This gate does not add a timeout to the actual
UTM operation. TERM/INT/HUP are forwarded to the child, which is reaped. Existing
bounded process-group runners remain responsible for timeouts and hard kills;
SIGKILL cannot be handled by the wrapper. Logging failure warns on stderr and
allows the original operation to proceed, without retrying it. This is
best-effort diagnostics, not a security audit or a same-user trust boundary.

## ScriptingBridge failure

**Current — live-tested failure:** UTM 4.7.5's bundled `utmctl` on macOS 26.6.2
can abort even on read-only `list`. The observed sequence is:

1. Failed to get the application's scripting definition.
2. `NSInvalidArgumentException` for `-[SBApplication virtualMachines]`.
3. `SIGABRT` (signal 6; shell exit status 134).

Existing status-call crash stacks reach the same VM-list lookup. Apple's
`sdef` can read the installed dictionary in this state, so a missing dictionary
file does not explain the observed failure. Direct AppleScript inventory and
a background LaunchServices reopen also returned error `-600` (application
not running) despite a live UTM process. A process sample showed an idle main
event loop, so a CPU spin or obvious main-thread blockage was not observed.
The exact reason that macOS cannot address the live application remains open.
This is a controller CLI failure and does not by itself establish that the
guest or UTM's VM process crashed.

**Current — mitigated:** The health guard detects this observed state and
refuses before the crashing CLI runs. The common doctor reports automation
unavailable and leaves guest power state unknown. Windows/Linux library
recovery now distinguishes `empty`, `not_running`, and `library_unready`
from `unavailable`; an arbitrary failed VM status no longer triggers reopen
plus twenty CLI retries. A missing VM in a nonempty library is not evidence
that the library is unloaded.

Run `python3 providers/utm/automation.py /Applications/UTM.app/Contents/MacOS/utmctl`
for the read-only health state, or use common `target doctor`. Normal wrapper
calls now demonstrate a refusal in the broken state. Do not bypass the guard
or repeatedly run raw `utmctl` to reproduce the crash.

**Open:** This prevents the observed crash loop; it does not restore the
broken application endpoint. A clean UTM restart is a recovery candidate only
after all UTM guests are independently verified stopped and active users are
coordinated. Neither the guard nor doctor quits UTM, resets registration,
changes sandbox/TCC policy, or replays operations. The app can fail between
preflight and dispatch, so the guard is not a guarantee against all upstream
crashes. Match any remaining crash with its diagnostic PID. Raw Apple reports
contain private machine data and must not be committed or uploaded unreviewed.

See the [provider dossier](../../research/providers/utm.md) for upstream
architecture, evidence, and remaining investigation.

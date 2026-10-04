# UTM CLI diagnostics

The Windows and Linux UTM shell providers and shared UTM workspace provider
run `utmctl` through `cli.py`. Logging is automatic for calls from this
checkout; an older installed/distributed copy must be updated separately.
Direct `utmctl`, AppleScript, and the Python factory-stage probes are outside
this wrapper's coverage.

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

The wrapper does not retry commands, change authorization, add timeouts, or
repair UTM. TERM/INT/HUP are forwarded to the child, which is reaped. Existing
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
file does not explain the observed failure. The exact sandbox/ScriptingBridge
failure remains unresolved. This is a controller CLI failure and does not by
itself establish that the guest or UTM's VM process crashed.

For a deliberately bounded reproduction, invoke the wrapper with source
`diagnostic` and the installed `utmctl` path followed by `list`, capturing its
exit status. This may produce another macOS crash dialog. Do not loop it or
replay lifecycle mutations. Inspect the resulting metadata plus the matching
Apple report locally; raw reports contain private machine data and must not
be committed or uploaded unreviewed. Do not disable crash reporting, re-sign
UTM, weaken sandbox/TCC settings, or restart running VMs as an inferred fix.

See the [provider dossier](../../research/providers/utm.md) for upstream
architecture, evidence, and remaining investigation.

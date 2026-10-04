# Scoped target tasks

`machine-control --target ALIAS run … -- PROGRAM ARG…` runs a bounded local
task while owning its target-use claim. The runner performs read-only doctor
and exact-identity claim status, acquires with your attribution, renews while
the task runs, stops remaining task processes, and releases in cleanup.
An off or suspended target can pass preflight; an invalid doctor or unresolved
identity cannot. The adapter rechecks identity when acquiring the claim.

```bash
bin/machine-control --target windows run \
  --reason 'inspect the application desktop' \
  --claimant-authority example-agent --claimant-id task-42 \
  -- bin/machine-control desktop applications
```

Use truthful, non-secret attribution. Optional claim flags are `--duration
30m`, `--session-id`, `--label`, repeatable `--metadata KEY=VALUE`, and
`--disruptive`. Outer input still requires explicit disruptive use and every
platform's existing focus, attendance, and recovery guards. The runner does
not grant host input merely because it holds a claim.

The program runs on the controller without shell interpolation. To execute
guest administration, invoke `bin/machine-control os -- …` inside the task.
To run multiple commands, supply a script. Nested common-client commands
inherit the selected target and claim; there are no IDs to parse. They reject
conflicting selection, nested runs, and claim/workspace management because
the parent owns that scope. Use lower-level manual claim commands when you
need to transfer ownership between independent processes.

## Workspaces and lifecycle

```bash
bin/machine-control --target macos run --intent isolated \
  --reason 'exercise a disposable guest' \
  --claimant-authority example-agent --claimant-id task-42 \
  -- python3 path/to/guest-test.py
```

`--intent persistent|isolated|candidate` requests a workspace instead of a
plain claim. The runner retains both the returned handle and claim, passes
both to task operations and renewal, and releases that exact workspace under
its claim. Workspace release implements the provider's retain/discard policy.
The runner never substitutes plain claim release after failed workspace
cleanup. Workspace scopes currently support ordinary use only; combining
`--intent` with `--disruptive` fails before acquisition.

A plain scope owns the claim, not target power state. Your task must arrange
its required lifecycle cleanup. A task that starts an initially off or
suspended persistent target must park it through the platform's routine down
action before returning, unless leaving it running was explicitly intended.
A task inheriting a running target must not silently stop it. Claim release
never implies target shutdown. The runner does not escalate a failed routine
shutdown into a force-stop.

## Results and recovery

Task stdin, stdout, and stderr are inherited. The runner writes one minimized
`machine-control-run/v0` acquired record and a final record to stderr, mixed
with any task stderr. The [audit schema](../contracts/run-result-v0.schema.json)
contains logical selection, opaque IDs, renewal count, task outcome, exit
status, and separate claim/workspace cleanup states. It omits command
arguments, private configuration, credentials, and raw management diagnostics.
Task output retains the task's own disclosure responsibilities.

The same minimized summaries are now persisted in the controller's
[target operation journal](target-operation-audit.md), alongside claim
transitions and nested common CLI commands. Retained history remains queryable
after release; stderr is still the task's immediate result channel.

The task's exit code is preserved when cleanup succeeds. Handled POSIX signals
return `128 + signal`; orchestration or cleanup failure returns nonzero.
`outcome` describes task execution; always check `exitCode`, `errorCode`, and
`cleanup` as well. A completed task with unresolved release is not a successful
run. `not_acquired` means no allocation was attempted or a validated refusal
was returned. `unresolved` means acquisition or cleanup may have taken effect
without a verified receipt. An unknown acquisition may have no reported ID.

On unresolved cleanup, inspect claim status and workspace inventory through a
fresh, unscoped common-client invocation. Use the returned IDs and existing
receipt-bound recovery procedure; do not guess a handle, steal another holder,
or blindly repeat acquisition. The runner does not reacquire after a failed
renewal. Expiry is a fallback for exclusivity, not workspace destruction.

Management calls have a 120-second ceiling. Renewal gets a shorter deadline
within the remaining lease and begins after one third of that lease. Failure
stops the task before attempting release. A timed-out or malformed acquisition
is reported unresolved unless a usable receipt permits verified cleanup.

## Process and selection boundaries

POSIX tasks use a new process group. SIGINT, SIGTERM, and SIGHUP are handled;
cleanup forwards the signal, permits a short grace period, then kills remaining
group members. Even successful tasks have remaining descendants stopped before
release. Windows uses a Job Object with kill-on-close and a gated launcher:
the workload starts only after job assignment. Windows cleanup terminates the
job rather than promising console-dependent graceful signal delivery. See
Microsoft's [job object semantics](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects).

The resolved registry is copied into a private temporary scope, so rewriting
the original registry cannot retarget nested commands. POSIX scope files use
mode `0600` in a `0700` directory; Windows uses the user's temporary directory
and inherited access controls. Files remain available until task cleanup and
are removed afterward. Platform configuration referenced by that registry
still belongs to its private inventory; adapters retain responsibility for
exact-identity rechecks.

This is cooperative cleanup, not a same-user security sandbox. Detached
services, guest jobs, and processes that deliberately leave the task's POSIX
group need task-owned cleanup. SIGKILL, controller failure, or power loss
cannot run `finally`; claim expiry and private workspace receipts remain the
recovery backstops. Do not put credentials in task arguments or metadata.

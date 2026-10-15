# Use Machine Control

Use the target specified in the task. Follow any required control route.

If Python `mc` tools are already loaded and support the selected target and
operation, use them. Calls block; do not `await`. Variables persist. The server
manages doctor, claims and renewal; do not pass it an existing claim. Observe
after UI changes, verify effects, and call `mc.close()` in cleanup. See
[session scope](../docs/agent-session.md) for supported capabilities.

Otherwise, use the CLI from the repository root. Replace `TARGET` with the
selected machine:

```sh
bin/machine-control --target TARGET target doctor
bin/machine-control --target TARGET claim acquire --duration 15m --reason 'Perform the requested task'
```

Read the returned claim ID and pass `--claim CLAIM_ID` on every target operation.
Check `grant status`; a claim is not a grant. Stop on denied authorization.
For an existing workspace, use its returned claim rather than acquiring another.
Follow the [CLI guide](../docs/cli-guide.md) for renewal and the selected
[platform guide](../platforms/README.md) for platform-specific operations.

## Observe, act, verify

Discover actual application identities, then inspect the relevant UI. `APP`
is an observed application identity; `LABEL` is the control text to find:

```sh
bin/machine-control --target TARGET --claim CLAIM_ID desktop applications
bin/machine-control --target TARGET --claim CLAIM_ID desktop snapshot --target APP --projection compact --query LABEL
```

The global `--target` selects the machine; the snapshot's `--target` selects
the app. Use references from the observation to act. Observe again after UI
changes and use fresh references. Verify the application effect, not just
whether the input call succeeded.

Use subcommand `--help` for exact grammar. Quote text and key chords such as
`'cmd+['`. If shortening commands with a shell function, forward arguments with
`"$@"` and define the function in each separate shell call.

Keep observations focused. An empty query may need greater `--max-depth`;
menus may need `--projection full`. Parse complete captured CLI stdout rather
than a truncated tool display. Preserve route, effect, uncertainty and
truncation metadata when filtering results.

## Cleanup

Release owned claims even when the task fails:

```sh
bin/machine-control --target TARGET --claim CLAIM_ID claim release
```

A workspace release needs its handle and claim. Leave borrowed claims to their
owner. Record material friction with `usage note --kind friction`, supplying
the note on stdin; use `fallback` for an authorized route change and finish
with a `summary` note. Keep secrets out of notes.

For YA delegation, use the [session runbook](../docs/ya-agent-sessions.md).
For Claude with the installed Sky runtime, use the
[Computer Use guide](claude-computer-use.md).

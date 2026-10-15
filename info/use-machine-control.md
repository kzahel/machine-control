# Give an agent a useful Machine Control entry point

**Proposal:** this concise entry guide incorporates observed instruction
friction. It has not been evaluated as an agent prompt. The frozen experiment
uses its own unchanged discovery and quickstart treatments.

Point a session at this file with the task and selected target:

> Read `info/use-machine-control.md` in the Machine Control checkout. Use it
> for the requested task on the selected target, verify the actual effect,
> and clean up your owned session and claims. Report any missing capability.

## Choose an available interface

Read [session scope](../docs/agent-session.md). If the persistent Python `mc`
tools are already loaded, configured for this target and qualified for the
requested placement/capabilities, use their tool description. Calls block;
there is no `await`. Variables persist. Use truthful published session
attribution, observe changed UI before acting, and call `mc.close()` in final
cleanup. The server owns its doctor, claim, renewal and release. Do not pass
it an existing global claim.

Reading this file does not load MCP tools. When they are absent or the task
needs a capability outside that facade, use the existing CLI and selected
[platform guide](../platforms/README.md). Follow the
[CLI guide](../docs/cli-guide.md) for readiness, claims, grants, renewal and
cleanup. Preserve any explicit route restriction in the task. A borrowed claim
remains owned by its coordinator; a workspace release needs its returned
handle and claim. Keep target control inside the target's native provider.

## Avoid common CLI discovery mistakes

These are syntax examples, not actions to run blindly. `TARGET`, `APP`,
`CLAIM_ID` and `LABEL` are placeholders for the selected machine, an observed
application, the live claim and a relevant control label.

```sh
bin/machine-control --target TARGET --claim CLAIM_ID desktop applications
bin/machine-control --target TARGET --claim CLAIM_ID desktop snapshot --target APP --projection compact --query LABEL
```

The global machine target and the command's application target are different.
Discover application identities rather than guessing a test browser's bundle
identifier. `desktop applications` lists apps; `desktop application list` does
not. Use offline subcommand `--help` for grammar before retrying guessed forms.

Quote text and key chords, especially shell metacharacters such as `'cmd+['`.
Use a shell function with `"$@"` if shortening commands; define it in each
separate shell call. A trap in an earlier completed shell cannot clean up a
later call.

Prefer bounded relevant observations. An empty shallow query does not prove
a control is absent; inspect app identity, depth and projection. Menus may
need the full projection. Compact output can still be truncated. Parse complete
captured CLI stdout, not a truncated tool display, and retain route, effect,
uncertainty and truncation metadata in any summary. Use fresh action references
after UI changes and independently verify effects.

Record material friction through `usage note --kind friction`; it requires a
kind and reads the note body from stdin. Use `fallback` for an authorized route
change and finish with a `summary` note after friction. Keep secrets out of
notes. Release owned claims promptly even when the task fails.

For delegated agent work, follow the [YA session runbook](../docs/ya-agent-sessions.md).
YA owns coordination; selecting a target does not require spawning an agent on
it. For the optional installed Sky route in Claude, use the separate
[Claude Computer Use guide](claude-computer-use.md).

# Genuine Sky through an external agent host

**Current, bounded live-tested:** YA-hosted Opus 5.5 at medium/normal completed
TextEdit save and menu/conversion in separate disposable Mac guests, with
independent file effects, two screenshots per workflow and explicit runtime
close. Two earlier adapter-startup failures are retained in
[Tactical 127](../../../docs/tactical/127-opus-sky-computer-use.md).

Experiment-only adapter for the installed unified Computer Use runtime. It
forwards the genuine `js`/`js_reset` tools, documentation, images and native
refusals; it does not delegate decisions to a Codex model. `sky_close` releases
the child runtime explicitly. Closed sessions never restart automatically.

The controller supplies the exact installed `.mcp.json` and preauthorizes
specific fixture bundle IDs. The normal runtime still performs its app-policy
lookup and emits app-access elicitation. Only matching connector/app metadata
is accepted by this experiment host; all other requests are declined. This
does not create a persistent Always allow decision or same-user containment.

```sh
python3 tests/experiments/sky-external/bridge.py \
  --config /private/selected-unified-computer-use/.mcp.json \
  --allow-app com.apple.TextEdit --evidence /private/sky-run
```

Configure this command as a Claude stdio MCP server in the disposable guest.
The runtime and its OS permissions must already work there. No proprietary
code/assets are included, no vendor binaries are patched, and installation
discovery must resolve one exact active runtime rather than choosing the newest
cache directory. Approval adaptation is deliberately narrow; general user
approval integration remains host work.

Merge this entry into the guest's existing Claude configuration (the tested YA
route reads `~/.claude.json`); preserve other settings and keep the file private:

```json
{
  "mcpServers": {
    "sky_experiment": {
      "command": "/absolute/path/to/python3",
      "args": [
        "/absolute/checkout/tests/experiments/sky-external/bridge.py",
        "--config", "/private/selected-unified-computer-use/.mcp.json",
        "--allow-app", "com.apple.TextEdit",
        "--evidence", "/private/sky-run"
      ]
    }
  }
}
```

Start a new YA Claude session after configuring the server. The tested profile
is `claude-opus-5-5`, medium effort, normal speed, with model traffic through
the separately configured AAR route. YA owns those credentials/session settings;
the bridge neither reads model credentials nor starts a Codex reasoning model.
Its native runtime may still depend on the installed Codex app-server executable.

For a reproducible isolated run, the harness performs registration, a real
initialize/list/close preflight, fixture setup and model-profile verification:

```sh
python3 tests/experiments/route_comparison.py \
  --target TARGET --provider claude --model claude-opus-5-5 --effort medium \
  --route sky-external --task textedit-save \
  --credential-file /private/base-login.secret \
  --gateway-credential-file /private/scoped-aar.secret
```

Select the private inventory provider and SSH options as in the runbook. The
harness's unattended agent permission mode is for disposable fixtures; it does
not replace the runtime's app eligibility or the bridge's app approval scope.

The existing harness exposes `--provider claude --route sky-external`, limited
to explicit `--task textedit-save` or `--task textedit-menu`. It retains model
qualification, tokens, fixture oracles, runtime provenance and private bridge
evidence. Use the ordinary private target/credential/AAR options from the
[runbook](../../../docs/comparison-experiments.md). This route is outside the
frozen baseline; its live qualification is tracked in
[Tactical 127](../../../docs/tactical/127-opus-sky-computer-use.md).

Recommended bounded task instruction:

> Use the sky_experiment MCP js tool for all UI work. Start with exactly one
> call: `var app = await cua.getApp("com.apple.TextEdit")`. Read the returned API
> documentation, then use fresh observations to choose actions. Inspect a
> screenshot. Key names are case-sensitive: use documented names such as
> `Return`. Preserve native refusals and stop if blocked. Do not use shell
> mutation, another GUI route or a nested agent. Verify the requested result,
> then call `sky_close`.

This is a qualification recipe, not a general installation or supported Sky SDK.

Troubleshooting:

- No tools: inspect the private protocol events. An optional `server/discover`
  probe must receive method-not-found without killing the following handshake.
  Allow deferred MCP discovery to finish before declaring the server absent.
- `app is not defined`: declare the binding with `var`; implicit assignment is
  not the JS prototype's persistent-variable convention.
- Native key refusal: use the returned API's exact spelling; lowercase `return`
  failed while `Return` worked in the live save trial.
- Native approval/permission refusal: stop and report it. Do not patch the
  service, alter OS permissions, auto-accept other apps, or switch UI routes.
- Closed runtime: start a new explicitly authorized session. This adapter does
  not recycle the client to clear a user stop or replay an action.

General per-app approval UI, a real physical-stop/revocation matrix, multiple
concurrent callers, other runtime revisions and other applications remain
unqualified. The separate locked-use feature was not exercised by this adapter.

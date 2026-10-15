# Genuine Sky through an external agent host

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

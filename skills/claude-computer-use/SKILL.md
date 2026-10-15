---
name: claude-computer-use
description: Configure and use the installed genuine OpenAI Computer Use runtime from a Claude MCP host on macOS, with explicit application scope and runtime cleanup. Use when asked for Claude-to-Sky control or its setup.
---

# Claude through genuine Computer Use

Use the repo's experimental stdio adapter so Claude receives native tool
documentation, observations and inline screenshots and chooses each action.
No nested Codex reasoning agent is needed. This skill needs the complete
Machine Control checkout: its helper reuses the qualified experiment adapter.
Keep it in place; reading this file directly works without global installation.

## Resolve the execution host and scope

The MCP process and native runtime run on the Mac being controlled. A Claude
session elsewhere needs its host's supported remote MCP transport or a session
on that Mac; a local config path does not target a remote VM. For a managed
test target, follow the checkout's doctor, claim and cleanup instructions.
The adapter itself does not acquire an MC target claim.

Use task context to identify the authorized apps and their exact bundle IDs.
Ask only when the target or scope cannot be resolved. Resolve the exact active
unified Computer Use installation's `.mcp.json` from the host/plugin registry
or a supplied path. It must contain `mcpServers.cua_repl`; do not select the
newest cache directory or substitute a different Sky client protocol.

The genuine runtime, signed launcher dependencies and OS consent must already
work there. Missing installation or permission is a concrete setup blocker;
the helper does not install vendor assets or change OS permissions.

## Prepare a scoped server

From the checkout root, using real absolute paths and a new private directory:

```sh
python3 skills/claude-computer-use/scripts/prepare.py \
  --runtime-config /private/selected-unified-computer-use/.mcp.json \
  --allow-app com.apple.TextEdit \
  --output-dir /private/claude-sky-session \
  --probe
```

The helper validates configuration, writes a private `mcp.json`, and with
`--probe` performs genuine initialize/list/close without requesting an app.
It leaves a private `probe.json` outcome and native diagnostics. A passed
probe proves startup and tool shape, not application permission or task success.
Without `--probe`, it only validates files/configuration. It never edits the
Claude profile or starts a model session.

`--allow-app` is repeatable for apps already authorized by the task. The
adapter automatically accepts only runtime app-access requests whose
connector and exact app metadata match that list; all other requests are
declined. This replaces an interactive app-approval prompt for that scope,
not native eligibility checks. It is not a sandbox or a global Always allow
setting. Do not expand the list just to make a refused action pass.

Only TextEdit save and menu/conversion have live qualification. Using another
authorized app is experimental; verify its effects and report its coverage
separately. No wildcard app approval is supported by the helper.

## Load it in Claude

If the current host already exposes the matching `sky_experiment` tools, use
them after confirming the configured target/scope. Allow supported deferred
tool discovery to complete before declaring them missing.

For a new Claude Code CLI session, the locally inspected CLI supports:

```sh
claude --mcp-config /private/claude-sky-session/mcp.json
```

Give that session this skill path and the actual task. Do not launch a nested
reasoning session merely to hide a missing tool from the current session.
For another host/version, inspect its supported configuration interface first.
The tested YA route reads the guest's private Claude configuration: merge the
generated `mcpServers.sky_experiment` entry while preserving other settings,
then start a new YA Claude session. YA owns model, effort, speed and AAR
credentials; none belong in this helper's arguments or evidence.

If the host cannot load this server into the active session, finish setup and
report the exact config path and new-session step. Reading the skill does not
hot-load MCP. Do not silently change global configuration or disable the
host's tool permission checks. Each live server needs its own generated
configuration/evidence directory; do not share one between concurrent sessions.

## Operate and finish

1. The first `js` invocation must contain exactly one documented entry call,
   with an explicit persistent binding when selecting an app, for example:
   `var app = await cua.getApp("com.apple.TextEdit")`.
2. Read the returned API documentation before further calls. Use that API,
   fresh observations and screenshots to choose actions. Declare variables;
   implicit `app = ...` failed in the qualification. Key names are
   case-sensitive (`Return`, not `return`).
3. Keep GUI work on this selected route. Forwarded native refusals and user
   Stop are final for that attempt; do not reset/restart to clear them or
   switch providers to evade them. The adapter does not automatically restart.
4. Verify the requested application effect. A successful call is not proof.
   Where authorized and available, use an independent read-only file or app
   oracle. Inspect actual image output, not just its presence in JSON.
5. Call `sky_close` after verification or a blocked task, including on failure.
   It releases the runtime and makes this server terminal. Start another
   explicitly authorized session for later work; do not reuse closed handles.

Missing tools, optional discovery probes, key errors and private evidence are
described in the [adapter runbook](../../tests/experiments/sky-external/README.md).
For startup failure, report the failing stage and private diagnostic path;
do not print raw app-access requests or runtime logs into a public issue.
Physical Stop/revocation, multiple callers, other versions and locked use
remain unqualified for this adapter. See
[Tactical 127](../../docs/tactical/127-opus-sky-computer-use.md) for the exact
live evidence; the skill adds packaging, not broader runtime acceptance.

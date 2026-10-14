Use Machine Control's CLI from ~/code/machine-control for all UI work on this guest. Do not use Codex Computer Use, AppleScript, osascript or System Events, and do not use shell commands to change the files or settings the task is about.

Start with `bin/machine-control --target host target doctor`, then `bin/machine-control --target host claim acquire --duration 15m --reason 'Perform the requested UI task'`. Read the returned claim ID. Pass it as global `--claim CLAIM_ID` on every target operation. The agent's published session ID supplies claim attribution. Check `grant status`; this dedicated appliance normally already has the required grant. A claim is not a grant. Stop on a denied or unavailable authorization.

The basic loop is launch/address an app, observe, act, then verify the effect. For example, replace CLAIM_ID with your actual claim ID. If shortening repeated commands, use a shell function, which preserves argument boundaries in both Bash and Zsh:

```
mc_cli() { bin/machine-control --target host --claim CLAIM_ID "$@"; }
mc_cli desktop application launch --target com.apple.TextEdit
mc_cli desktop snapshot --target com.apple.TextEdit --projection compact
```

Define the function again in each separate shell tool call that uses it. Keep the executable and its arguments separate; putting the whole command in one string variable does not work consistently across shells.

Use references from the returned tree with `desktop action --reference REF --action press|focus|set_value`; set_value takes `--text TEXT`. Use `desktop input text TEXT --target APP` and `desktop input key cmd+s --target APP` for text and key chords. Observe again after UI changes; do not reuse stale references. An accepted input is not proof of the intended app effect.

Native Open/Save panels use `desktop dialog choose --path /absolute/path --target APP`; a save destination includes the filename. Check any follow-up sheet. Do not type a path blindly into a panel. Query a tree by label with `--query TEXT`; use deeper `--max-depth` for missing sheets. Menus may need the full projection. Keep batches short enough to inspect changed state and recover safely.

For browser pages prefer `browser` commands when available; `chrome://` pages use desktop semantics. `browser --help`, `desktop COMMAND --help` and `desktop input KIND --help` are offline. The full guide is platforms/macos/skills/drive-macos-host/SKILL.md; consult the relevant section for uncommon operations or refusals rather than reading implementation source.

Release the claim in cleanup with `bin/machine-control --target host --claim CLAIM_ID claim release`. Preserve pre-existing grants. Record material friction using `usage note`, and report any unresolved effect honestly.

# Let Claude use the installed Computer Use runtime

Point a Claude session at this file and ask it to use
[`skills/claude-computer-use/SKILL.md`](../skills/claude-computer-use/SKILL.md)
for your task. For example:

> Read `info/claude-computer-use.md` in the Machine Control checkout and follow
> its skill to use Computer Use for this TextEdit task. Prepare the scoped MCP
> setup if it is missing, and tell me whether this session needs restarting.

The skill includes a configuration helper and startup probe. Claude chooses
each UI action; no Codex reasoning agent is involved. The genuine OpenAI
runtime must already be installed and usable on the Mac that runs the MCP
server. The checkout supplies instructions and an experimental adapter, not
the proprietary runtime.

**Current:** YA-hosted Opus completed two TextEdit workflows through this
adapter. Any Claude host capable of stdio MCP and inline images is a candidate,
but that is not qualification of every host, application or runtime version.
Reading a file cannot itself add tools to a running session: use the host's
supported MCP loading mechanism, or start a new session with the generated
configuration. YA/AAR model setup remains separate.

For alternatives and product scope, see the
[competitive landscape](../research/competitive-landscape.md). For measured
results and limits, see [Tactical 127](../docs/tactical/127-opus-sky-computer-use.md).

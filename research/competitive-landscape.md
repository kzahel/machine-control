# Computer-use competitive landscape

Review date: 2026-10-15. Status: **Current** evidence map, not a performance
ranking. This comparison covers agent-facing computer control and the recently
identified Claude/Sky integrations. The [adjacent-project ledger](adjacent-projects.md)
covers browser testing, mobile frameworks, hosted fleets and benchmarks.

## Different routes behind similar names

“Claude computer use” can mean three mechanically different things:

1. Claude chooses each action through OpenAI's installed native runtime.
2. Claude delegates a whole task to a Codex reasoning agent.
3. Claude calls an independent implementation of desktop control.

Only the first holds the native provider approximately constant for an
Opus-versus-Sol experiment. The second adds another model and its context,
cost and decisions. The third compares both the provider and its interface.
Even the first needs matched runtime, permissions, instructions and fixtures.

| Project / route | Who chooses UI actions; implementation | Declared license | Evidence and main boundary |
| --- | --- | --- | --- |
| [OpenAI Computer Use / Sky](providers/sky-computer-use.md) | Calling model; proprietary native runtime and host integration | Proprietary; installation does not grant redistribution rights | Bounded native source/interface review and live workflows; product consent, app policy and installed runtime compatibility matter |
| [songkeys/claude-codex-computer-use](https://github.com/songkeys/claude-codex-computer-use) | Claude; bridge to installed native MCP client through signed launcher, without a Codex reasoning session | MIT LICENSE inspected; OpenAI runtime remains separate | `source-reviewed` bridge, not locally run; automatically accepts elicitation and recycles after idle/user-stop results in the reviewed source. Those policies are not adopted here |
| [promptadvisers/claude-mods-computer-use-threads](https://github.com/promptadvisers/claude-mods-computer-use-threads) | Claude; direct native tools through a mod-enabled Claude runtime | MIT LICENSE inspected; proprietary runtime separate | `upstream-claimed`, README/design reviewed; documents app approval UI and caller leases. Mod runtime compatibility with YA is unproved; its session-coordination feature is a separate concern |
| [leeguooooo/computer-use](https://github.com/leeguooooo/computer-use) | Codex reasoning agent receives delegated tasks from Claude through a broker | README declares MIT; no root LICENSE found in reviewed tree | `upstream-claimed`, current README reviewed; archived broker rewrite. Historical patch/hook instructions describe a removed design and are not a current setup recipe |
| [MC external Sky experiment](../tests/experiments/sky-external/README.md) | Opus through YA; small owned adapter forwards genuine unified-runtime JS tools, docs and images | Owned adapter under repository terms; proprietary runtime not bundled | `live-tested` for two TextEdit workflows with independent file effects; exact app approval scope, explicit close, no automatic restart. Other apps, physical Stop and general installation remain unqualified |
| [Open Claudex / OpenCodexLabs](https://github.com/OpenCodexLabs/open-codex-computer-use) | Calling MCP agent; independent Swift macOS execution layer | [MIT](https://github.com/OpenCodexLabs/open-codex-computer-use/blob/main/LICENSE), inspected | `upstream-claimed`, README/license triage only; claims background input, virtual cursor and post-action state. Alpha status and native versus WebView/Electron limitations are upstream descriptions, not local acceptance |
| [QwenLM/open-computer-use](https://github.com/QwenLM/open-computer-use) | Calling MCP agent; independent accessibility-based service for macOS, Windows and Linux | [MIT](https://github.com/QwenLM/open-computer-use/blob/main/LICENSE), inspected | `upstream-claimed`, README/license triage only; CLI/MCP, persistent call sequences and image-budget controls are useful comparison candidates. No local live qualification |
| [iFurySt Open Computer Use](providers/open-computer-use.md) | Calling agent; independent native CLI/MCP providers | MIT with third-party notices | `source-reviewed` at the existing spike pin; platform depth and limits belong to its dossier. Do not transfer that review to a similarly named repository or newer lineage without checking revisions |
| [Cua](providers/cua-driver.md) | Calling agent; replaceable desktop provider within a broader ecosystem | See dossier for component-specific terms | Adopted MC provider in bounded routes; both a component and a direct alternative. Its broader SDK/sandbox scope prevents treating every competitor as GUI-only |
| [Machine Control](../README.md) | Calling agent through CLI/MCP/owned facade; native and replaceable providers | See repository [license](../LICENSE) and provider dossiers | Whole target/control package: desktop access, devices, VM lifecycle, readiness, claims, recovery and audit. Platform and facade maturity vary; measured GUI gaps remain |

The [Sky dossier](providers/sky-computer-use.md#other-model-bridges-2026-10-15)
owns genuine-runtime integration findings. The
[spike review](../../machine-control-spike/docs/sky-other-agent-bridges.md)
owns exact third-party pins and inspection depth. None of these third-party
bridges was installed or adopted. README demos and compatibility tables are
not independent effect or non-interference evidence.

## What this means for Machine Control

**Decision:** compete on the complete, extensible, provider-agnostic target
workflow as well as control quality. “Works with Claude” alone is not a durable
differentiator: both independent providers and genuine-runtime bridges can do
that. Machine Control also owns target preparation, ordinary remote native
control and cleanup, while YA owns model sessions and delegation.

**Current:** authorized system surfaces and implemented locked use belong in
the product comparison. Ordinary app menus must be distinguished from global
status items/tray and protected UI. Python-session method coverage must be
distinguished from existing product capabilities. The
[positioning and gap roadmap](../topics/computer-use-positioning.md) owns these
claims and priorities; this landscape does not create a second roadmap.

**Open:** compare providers on identical tasks and authority: completion with
independent effects, stale-reference handling, cursor/focus disturbance,
denial/Stop/cleanup behavior, tool calls, elapsed time and tokens. Separate cold
startup from warm operation, and cached input from uncached input and output.
The [capability baseline](../docs/evidence/agent-capability-comparison-2026-10.md)
and [bounded Opus/Sky qualification](../docs/tactical/127-opus-sky-computer-use.md)
are distinct evidence sets; two successful qualification workflows do not
establish reliability or performance superiority.

**Proposal:** next competitive experiments should test instruction packaging
and a matched provider/model matrix before adding more adapters. A source
review of an independent provider is worthwhile when it could close a measured
gap such as compact observations or background input. Broad installation of
every discovered repository would not resolve those questions.

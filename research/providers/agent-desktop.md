# agent-desktop

Upstream: [lahfir/agent-desktop](https://github.com/lahfir/agent-desktop)

Declared license:
[Apache-2.0](https://github.com/lahfir/agent-desktop/blob/main/LICENSE) for the
repository.

Last corpus review: 2026-08-05.

## Evidence by platform

| Platform | Level | Evidence and limit |
| --- | --- | --- |
| macOS | `source-reviewed` | Native adapter, semantic contract, window/surface model, input policy, screenshots, traces, and tests were inspected. |
| Windows | `source-reviewed` as unsupported | Current adapter implements empty/default traits and reports platform unsupported. |
| Linux | `source-reviewed` as unsupported | Current adapter implements empty/default traits and reports platform unsupported. |

No exact review pin has yet been added to `machine-control-spike`.

## Architecture and depth

agent-desktop defines a particularly strong agent-facing contract: compact
progressive snapshots, drill-down, snapshot IDs and qualified refs, structured
errors, semantic versus physical action policy, windows and surfaces, menu
bars, sheets, popovers, alerts, per-window capture, traces, sessions, and
multi-agent namespaces.

The release/project shape may suggest broader platform ambitions, but the
current Windows and Linux adapters are stubs. Treating artifact availability as
backend support would therefore be incorrect.

## North Star fit

The contract is useful input for token-efficient semantics, surface identity,
structured refusal, traces, and concurrent-agent isolation. The current code
is a macOS provider/contract reference rather than a cross-platform spine.

## Current disposition

**Proposal:** Reuse contract lessons where they improve the common facade.
Evaluate the macOS backend only if it provides a measured advantage over Cua
or Peekaboo.

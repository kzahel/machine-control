# Computer Use positioning and gap roadmap

Topic: `computer-use-positioning`

Status: current product positioning and evidence-led roadmap. The Python MCP
candidate is one interface within Machine Control, not the whole product.

## Positioning

**Decision:** Machine Control is a provider-agnostic machine and testbed control
package: provision/select a target, establish readiness and authority, operate
its apps/browser/system surfaces, verify effects, and release or recover it.
It combines desktop and device control with VM lifecycle, disposable workspaces,
credentials, diagnostics and audit. YA owns agent coordination; Machine Control
does not need an in-target agent to provide ordinary remote native control.

Its advantage over Codex Computer Use is ownership and breadth: users can choose
their model/host, extend the implementation, and authorize system surfaces that
a fixed vendor product may exclude. Less restricted means a wider explicitly
authorized surface, not absent claims, permissions, revocation or effect checks.
Sky remains a valuable optional provider and quality benchmark.

| Dimension | Current Machine Control position | Comparison boundary |
| --- | --- | --- |
| Agent/provider choice | CLI and MCP can serve different hosts; Sol and Opus completed the same corpus | Third-party Sky bridges can also enable other models; provider independence is architectural, not an exclusive feature claim |
| Complete test workflow | Target selection, VM bring-up, doctor, claims, isolated workspaces, teardown and recovery | Compare this package with Computer Use's GUI execution scope, not just tool-call latency |
| System surfaces | Native routes include Windows taskbar/system shell and macOS Dock/menu bar/Control Center | Distinguish system tray/status extras from ordinary app menus: Sky app menus worked in our tests; exact policy/coverage comparisons need matching fixtures |
| Authorized administration | Typed protected/appliance routes and bounded administrator-sheet operations exist, with profile-specific authority | OpenAI's documented product excludes OS security approval, administrator authentication and terminal automation; this is a product-policy distinction, not proof of a native technical limit |
| Locked use | Implemented opt-in macOS covered control with bounded physical/VM evidence; separate appliance/protected routes also exist | Not a missing product feature. Python-facade integration and each platform/profile's acceptance are separate questions |
| Browser/device reach | Existing browser extension/CDP and platform/device providers | Missing methods in the thin Python facade do not imply missing product capabilities |
| Extensibility | Owned source, provider adapters, contract and conformance fixtures | Sky's proprietary runtime and integration can change independently; do not redistribute its assets |
| Ordinary Mac desktop efficiency | Persistent Python improves over CLI on corpus medians | Sky still leads in several native observation/input behaviors; neither breadth nor openness erases those gaps |

Evidence owners: [system map](../SYSTEM-MAP.md),
[locked use](macos-locked-use.md), [Mac resident](macos-resident-control.md),
[browser control](browser-control.md), [provider landscape](provider-landscape.md),
[Sky dossier](../research/providers/sky-computer-use.md), and the
[seven-scenario comparison](../docs/evidence/agent-capability-comparison-2026-10.md).
Those records retain platform, revision and evidence limits.
The administrative comparison uses OpenAI's current
[documented Computer Use restrictions](https://learn.chatgpt.com/docs/enterprise/chatgpt-work-local-security#computer-use-and-application-approvals),
not an attempted bypass or a claim about every internal service operation.

## Roadmap ordered by evidence and impact

| Priority / work | Gap and expected benefit | Acceptance gate |
| --- | --- | --- |
| 1 — Stable native element identity | Mac snapshots rotate references; Python must issue fresh numbers/full trees, increasing tokens and recovery | Preserve identity across unchanged reads, insertions and reordering; refuse replacement/stale references before dispatch; never match identity by label or position |
| 1 — Compact observations and diffs | Repeated trees, action metadata and shallow-query misses inflate model work | Correct bounded diffs, explicit truncation and menu queries; measure serialized bytes, normalized tokens and task failures, including unchanged reads |
| 1 — Background input and app menus | Current pointer routes can disturb focus/cursor; accepted background menu actions can lack effects | Independent sentinel, pointer/text/menu callbacks, actual app effects and sampled interference across representative native/Electron apps; report any foreground fallback |
| 2 — Notification-assisted settling | Python polls; identical samples do not prove asynchronous completion | Delayed, burst and continuous updates with bounded deadlines and explicit effect predicates; compare AX calls, latency and missed changes |
| 2 — Session lifecycle cost | Current Python includes a ten-second admission notice plus doctor/claim/audit, unlike direct-socket JS | Separately measure cold admission, warm operations, renewal and cleanup; compare equal enforcement, never remove authority checks merely to improve a score |
| 2 — Agent instructions and output ergonomics | Discovery, shell grammar and repeated queries consume calls | Frozen instruction A/B, token/call/time distributions and held-out workflows; no tuned-task generalization claim |
| 2 — Expose existing product breadth | Python lacks browser-specific, protected/locked-use and some richer input operations already present elsewhere | Typed integration through existing owners; explicit unsupported capability reporting; locked/remote/browser acceptance distinct from ordinary local MCP tests |
| 3 — Rich desktop interaction | Drag, selection, clipboard-preserving paste, transient UI and capture composition need facade/native coverage review | Feature inventory first, then deterministic effects, clipboard restoration, coordinate/staleness checks and denied-operation tests |
| 3 — Packaging and portability | Python is a source candidate; installed/shell/remote and broader platform acceptance remain | Installed import/startup, cancellation/cleanup, remote parity and platform-specific conformance, including failure paths |
| Parallel research — Opus with genuine Sky | Separate provider quality from model choice; offer a useful optional route | YA launches exact Opus profile; genuine unmodified runtime, normal app policy, bounded approvals, inline media, independent file/UI oracle, stop/cleanup evidence |

**Decision:** compare JS and Python over the same enforcement and observation
contract before choosing a model-facing language on performance grounds. The
current JS experiment skips controller claims/audit and silently rebound numbers
in three passing window trials. Python's stronger lifecycle is promising, but
is not proof of language superiority or finished product support.

**Open:** establish a matched system-surface matrix: ordinary app menu, macOS
status item/Control Center/Dock, Windows tray/taskbar, administrator UI and
locked use. Record policy refusal separately from absent semantics, failed
delivery, wrong effect and model failure. Never summarize this as “Sky cannot
use menus” or “Machine Control can control everything.”

The [Opus/Sky experiment](../docs/tactical/127-opus-sky-computer-use.md) owns
the bounded integration work; [Tactical 123](../docs/tactical/123-persistent-agent-session.md)
owns the supported session and [Tactical 125](../docs/tactical/125-agent-capability-baseline.md)
owns the existing comparison and instruction evaluation.

**Current:** Opus through YA now passes two bounded TextEdit workflows using
the genuine installed runtime, with images, scoped app approval and explicit
cleanup. Two adapter-startup failures were diagnosed and retained. This proves
a useful optional route and reinforces why provider independence is a package
design advantage rather than a claim that Sky can only ever serve OpenAI models.
It does not yet establish a general-purpose bridge or comparative performance.

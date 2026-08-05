# Provider Landscape

Topic: `provider-landscape`

Status: active cross-provider decision concern. Detailed project facts and
platform comparisons live in the [research corpus](../research/README.md).

## Scope

This topic owns decisions that emerge from looking across reusable providers:
whether a common spine is desirable, how platform-specific depth composes with
it, which candidates deserve experiments, and which common contract lessons
must survive provider choice.

It does not own provider-by-provider source notes, license records, platform
matrices, exact source pins, or experiment logs. Those belong respectively in
[`research/providers/`](../research/providers/README.md),
[`research/platforms/`](../research/platforms/README.md), and
`machine-control-spike` or an authoritative testbed.

## Settled direction

**Decision:** Preserve both research axes:

- provider-first research asks whether a library already supplies a flexible,
  reusable architecture across several platforms; and
- platform-first research asks which route is deepest and most reliable for a
  particular operating system or device family.

One library everywhere is an optimization, not a requirement. Prefer a common
provider when it is strong enough to reduce adapter, contract, and agent-skill
fragmentation. Retain or introduce a platform-specific adapter when it provides
materially better semantics, capture, input, system-surface coverage,
reliability, or authority.

**Decision:** The project owns the stable target-oriented contract and its
conformance suite. An upstream project may implement most of that contract,
but it does not thereby inherit testbed lifecycle, cross-host coordination,
protected authority, recovery, or the right to hide route/fidelity changes.

## Current synthesis

**Current:** The recent Cua spike—not an old generation of Cua—found that Cua
Driver is a strong normal-user desktop-core candidate and recommended
provisional adopt-and-extend. A same-version source review immediately after
the spike reinforced capabilities already present in the audited revision; it
did not discover a newly transformed product. See the
[Cua dossier](../research/providers/cua-driver.md) and exact
[spike recommendation](../../machine-control-spike/docs/phase-1-recommendation.md).

**Decision:** Use Cua as the leading common Windows/macOS/Linux desktop-plane
candidate. Validate the remaining Windows product surface rather than rerunning
the completed Cua fit, macOS, and Windows investigations wholesale.

**Current:** The strongest complementary references are:

- [WinApp](../research/providers/winapp.md) for the adopted Windows UIA route;
- [Open Computer Use](../research/providers/open-computer-use.md) for a compact,
  agent-neutral, three-desktop Computer Use surface;
- [Touchpoint](../research/providers/touchpoint.md) for a small common facade;
- [Peekaboo](../research/providers/peekaboo.md) for deep macOS exact-window,
  system-surface, and fixture design;
- [kwin-mcp](../research/providers/kwin-mcp.md) for isolated KWin/Wayland test
  sessions; and
- [Agent Device](../research/providers/agent-device.md) for the adopted iOS
  semantic route and compact device workflow.

The [provider index](../research/providers/README.md) records the wider set,
license posture, and actual evidence level.

## Common exact-window requirements

**Decision:** “Window control” is not one capability flag. Conformance must
test independently:

1. native window identity, owner binding, and recreation;
2. semantic scope and snapshot/reference lifetime;
3. compositor/window capture versus a desktop crop, including occlusion,
   minimization, other virtual desktops/Spaces, and protected content;
4. semantic or pixel action binding to the same window and coordinate epoch;
5. direct semantic, process-targeted background, foreground, or desktop-wide
   delivery and its cursor/focus/z-order effects; and
6. independent application, semantic, pixel, focus, and leaked-input evidence.

Application/title discovery may resolve an exact target but is not itself a
stable action identity. Transient UI can be desktop- or shell-owned, so the
contract also needs explicit scopes for menu bars, taskbars/Dock, notification
areas, menus/popovers, dialogs/sheets, and protected desktops.

## Conformance fixture direction

**Decision:** Keep deterministic fixture conformance and real system-surface
acceptance separate. Fixtures should cover native and embedded-web controls,
multiple windows and processes, dialogs, menus, popovers, tooltips, layered or
compositor-backed windows, text/keys/scroll/drag/clipboard/window lifecycle,
and application-owned effect canaries. Foreground sentinels and physical-cursor
observers must detect leaked input and focus theft.

Cua's cross-platform fixture catalog and Peekaboo's native macOS Playground are
the leading models. The project should own the acceptance cases so the same
case can compare Cua, WinApp, Touchpoint, Peekaboo, or a future adapter.

## Research backlog

**Current:** The
[adjacent-project ledger](../research/adjacent-projects.md) keeps pinned
benchmarks, platform frameworks, and discovered providers visible without
pretending they have all received equivalent investigation. Promote one to a
provider dossier only when a measured gap or distinctive architecture
justifies source review.

**Open:** Decide, after the Windows vertical slice, whether the common desktop
plane should directly depend on Cua, wrap multiple upstream providers, extract
a smaller resident core, or maintain a derivative. API shape alone is not
enough evidence.

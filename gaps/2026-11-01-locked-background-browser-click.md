# Locked-console background browser click has no observed effect

Topic: `browser-control`

Status: **Current — physical recovery verified after development-provider reload.**
Private usage notes and claim audit events retain exact attribution and
evidence. The historical worker revision was not captured, so the exact old
implementation and responsible patch remain unpinned.

**Current (2026-11-02), bounded physical `live-tested` recovery:** the same
static and focus-sensitive fixtures first failed with the existing unpacked
provider: legacy three-part references, hidden page visibility and zero native
pointer/click callbacks despite acknowledged delivery. Reload initially failed
because Chrome rejected a generated `__pycache__` directory. After moving only
that cache out and using Chrome's explicit Retry, the reloaded worker reports
an executing-operation digest matching current source and four-part references.
Both new background fixtures produce one trusted click and independent HTTP
effect while the OS stays locked; typing, capture and tab-selection checks
also pass. This is recovery of the reported physical symptom, not proof that
the focus/layout fix alone explains the old static failure. [Tactical 147](../docs/tactical/147-physical-browser-provider-validation.md)
owns the maintenance, diagnostic additions and cleanup evidence.

**Current (2026-11-02), related defect repaired in unreleased source:** a VM
fixture reproduces clicks at obsolete coordinates when virtual focus triggers
page layout changes. Ordinary static fixtures passed. This isolates one
failure class; it does not independently establish the cause of the original
static-page physical failure. [Tactical 146](../docs/tactical/146-background-browser-click-reproduction.md)
owns the before/after regression, deployment comparisons and remaining limits.

## Observations

During locked-console checks, the existing Chrome extension/native-messaging
route opened an owned localhost fixture in a new background tab. The connected
extension reported version 0.8.4; the exact installed desktop and browser build
and loaded extension artifact were not pinned for this investigation.

With both the lid closed and, in a separate task, the lid open,
`browser.click` on a fresh snapshot's button reference returned
`delivery: confirmed`, `effect: unverifiable` and
`uncertainty: no_independent_state_change`. Fresh page reads and capture still
showed the original button label. Neither uncertain click was replayed, and
the tab was not brought to the foreground as a workaround.

The lid-open fixture had a click handler that changed its label and sent a
dedicated HTTP POST. After the click and subsequent observations, the DOM label
was unchanged and the server's click counter remained zero. Text entry in the
same background tab did produce the exact expected DOM value and independent
HTTP POST body. Navigation, semantic inspection and page capture also worked.
Independent IOKit readback confirmed that the console remained locked.

The earlier lid-closed fixture's HTTP GET marker also accepted favicon
requests, so that marker is not a valid click oracle. Its unchanged label is
supporting observation only; the corrected lid-open POST counter supplies the
independent negative effect evidence.

A separate lid-open covered desktop fixture passed native semantic-button,
pointer-button and keyboard effects, capture and completion relock. This
finding concerns the background browser route, not a general pointer failure.
All owned fixtures, tabs and servers were cleaned up and claims released.

## Interpretation and next evidence

**Open:** the exact historical executing worker and why it remained different
from source on disk. Reload changes code and provider/attachment state together;
the physical recovery does not isolate their individual contributions or prove
which earlier patch fixes the static case. There is no matched physical
unlocked-console or foreground-tab comparison. An acknowledged input call alone
remains insufficient evidence of an effect.

- Pin the installed desktop, browser and loaded extension artifacts; compare
  their background-input preparation with the accepted source route.
- Reproduce with an owned fixture under matched locked/unlocked console and
  active/inactive-tab conditions. Any foreground cell must be explicit.
- Observe actual pointer callbacks, hit target, DOM state and independent HTTP
  effects alongside tab selection, OS focus/cursor and virtual-focus state.
- Add a regression for the isolated cause without automatically replaying
  uncertain input or silently activating a tab.

The [browser topic](../topics/browser-control.md) owns current direction; the
[provider dossier](../research/providers/chrome-extension.md) retains the
separate VM acceptance and installed-provider qualification limits.

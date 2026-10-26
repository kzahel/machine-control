# 140 — Background browser control and extension release

Owning topic: [browser control](../../topics/browser-control.md).

Status: implementation and validation complete; publication uses tag-driven CI.

## Objective and completion conditions

The user reported that browser automation repeatedly foregrounded windows and
interrupted their work, requested background defaults and explicit foreground
use, and authorized implementation and a new Chrome Web Store release. The
preceding investigation also found a browser-root queue that could remain
blocked after a tab-close promise stopped settling.

- New tabs preserve the user's selected tab by default, including CDP clients.
- Browser input produces independently observed page effects without taking
  OS focus or moving the cursor; unavailable preparation never activates Chrome.
- Known foreground commands require explicit opt-in, which does not survive
  reconnect or authorize queued activation after withdrawal.
- Release explicitly clears virtual page focus or reports uncertain cleanup.
- A pending tab close cannot indefinitely block discovery or a new connection;
  timed-out work remains bounded, fenced and unreplayed.
- Tests, reproducible packaging and the existing tag-driven CI submit the
  extension for automatic publication after Google's review.

## Boundaries

No personal browser automation, desktop publication, new permissions, copied
third-party code, automatic modal acceptance or synced-group deletion. The
presentation opt-in is cooperative task policy, not an operator-only permission
or containment of arbitrary scripts, website popups or native desktop control.
Native Chrome group-modal qualification remains separate.

## Ordered work

### 1 — preserve the user's working foreground

Default ordinary/CDP creation to background. Add explicit one-shot and
connection-local presentation choices. Prepare browser input with virtual page
focus rather than selecting a tab or raising its window; clear that override
before debugger release and retain uncertain-reset metadata.

### 2 — bound browser-level lifecycle operations

Keep discovery and close independent of serialized management changes. Bound
request deadlines, retained requests and unsettled physical calls. Fence the
owning connection on timeout and recheck generation/presentation before effects.

### 3 — validate and submit the extension

Use source regressions and a claimed Mac appliance with a disposable, separately
identified Chrome for Testing profile, a native focus sentinel and independent
HTTP effects. Reap owned processes, restore suspended power and release the
claim. Test package import closure and use the existing release script once.

## Validation and final result

The initial inactive-tab control acknowledged a click without its HTTP effect.
An explicit focus-emulation control produced click/text effects while the native
sentinel retained foreground/key-window state, text and cursor position.
The integrated source/unpacked route passes 17 live checks under standing
appliance authority: background creation, independent click/text effects,
PNG capture, unchanged native foreground/key-window/text/cursor state and
selected user tab, hidden visibility restoration, explicit one-shot and stream
foreground choices, and reconnect reset. The original DOM-focus cleanup oracle
was corrected: Chrome can retain `document.hasFocus()` after injected input
while the page has returned to hidden visibility. The page's own HTTP reports
provide the non-invasive visibility oracle. Raw diagnostics stay private.

All 29 extension tests pass, including store-package import closure, bounded
physical management slots, stalled-close discovery/reconnect, no replay,
foreground withdrawal, failed reset metadata and generation fences. Six browser
CLI tests, Python/JavaScript syntax, whitespace and repository portable checks
pass. No native resident or Windows runtime implementation changed.

The sentinel samples at 20 ms; shorter transient changes are not excluded.
The Mac source/unpacked route does not establish Windows/Linux live behavior,
physical workstation coverage, installed store-copy operation or Google review
completion. The existing publishing authentication check has passed in
[CI run 38857438805](https://github.com/kzahel/machine-control/actions/runs/38857438805).
The release uses `providers/chrome-extension/release.py 0.8.2`, which atomically
pushes main and `extension-v0.8.2`. CI owns exact-source tests, reproducible ZIP
packaging and automatic store submission; Google owns review and delivery.
Owned test browser/sentinel processes were verified absent, private evidence
was retained, task staging was removed and the VM's initial suspended state
was restored before releasing its exclusive claim.

### CI packaging follow-up

The user requested monitoring through green CI. The 0.8.2 release
[run 40302039402](https://github.com/kzahel/machine-control/actions/runs/40302039402)
passed all extension tests but failed clean-source verification before upload:
the workflow created `dist/extension` inside the checkout, so its own generated
ZIP made `sourceDirty` true. The workflow now packages under `RUNNER_TEMP`,
preserving the clean-source guard. Extension 0.8.3 replaces the failed release;
the 0.8.2 tag and failed run remain intact. Browser runtime code is unchanged.

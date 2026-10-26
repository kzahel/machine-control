# Machine Control Chrome extension

Topic: [`browser-control`](../../topics/browser-control.md)

This MV3 extension is the browser provider for a Machine Control resident on
the same computer. It connects to the resident only through Chrome native
messaging (`org.machine_control.browser`), and it acts only on requests the
resident forwards. The resident checks the person's `browser` grant before
forwarding; the extension badge shows `ON` while that grant is active (`DEV`
for the broader `devtools` grant) and
detaches its debugger sessions when the grant ends.

Operations use `chrome.debugger` (CDP) on individual tabs:

| Resident operation | Effect |
| --- | --- |
| `browser.tabs` | List tabs |
| `browser.wait` | Wait until a tab finishes loading and is not discarded |
| `browser.navigate` | Load an `http`, `https`, or `about:blank` URL in a tab or a new tab |
| `browser.snapshot` | Compact accessibility tree with generation-bound references |
| `browser.click` | Trusted mouse click at an element's center |
| `browser.type` | Focus an element and insert text |
| `browser.key` | Press Enter, Tab, Escape, Backspace, or an arrow key |
| `browser.capture` | Viewport PNG stored as a resident artifact |
| `browser.upload` | Attach local files to a file input, or to the chooser an upload button opens, without the OS file dialog |
| `browser.cdp` | Raw DevTools protocol with parameters (`devtools` grant); `Page.disable` is reserved to preserve dialog recovery |
| `browser.eval` | Evaluate JavaScript in a tab and return the value (`devtools` grant) |
| `browser.endpoint` | Report the local DevTools WebSocket endpoint template (`devtools` grant) |
| `browser.release` | Detach all debugger sessions; refuses promptly while an observed dialog needs handling |
| `browser.dialog` | Observe dialog type/message/id; explicitly accept or dismiss the current id |

The guarantees below require the matching new native relay and extension
0.8.1 or later. Older store workers and mixed-version combinations do not inherit this
qualification; coordinated app/store rollout remains separate.

**Current source:** ordinary requests serialize per tab with eight
active slots and 64 retained requests. Discovery, dialog handling, grant
fencing and release have independent bounded execution. Queued requests expire
without dispatch; a dispatched timeout reports unknown effects and blocks that
tab until recovery. Confirmed detachment frees abandoned slots even when an
old Chrome callback never returns. Unconfirmed detachments remain tracked for
the next release. Unsettled raw attachments retain a separate eight-slot
bound and fence reuse until their late result and cleanup settle, even when
an earlier detach reported absence. Release reports `released: false` with
`pendingAttachments` or `unconfirmedDetaches` instead of claiming completion.
If Chrome never settles an attach callback, that tab and its slot stay fenced;
a browser restart discards that broken provider state. Other established routes
and operator consent remain independent. Release does not replay work or
withdraw operator consent.

Dialog handling requires the freshly observed dialog id and an explicit choice;
it never automatically accepts a beforeunload prompt. A null dialog means no
opening event was observed, not proof that no modal exists. Status reports
`open` or `not_observed`, plus `observerState: ready|pending|failed`. Basic
debugger attachment is separate from event readiness: `Page.enable` can itself
wait behind a modal that predates reattachment. Ordinary operations and stream
opening require event readiness; explicit per-request raw
`Page.handleJavaScriptDialog` can use the independent basic attachment.
This raw recovery requires DevTools authority and never runs implicitly.
Release refuses with `dialog_open` while an observed dialog is open, preserving
its attachment for an explicit decision. Handle it first, then release. Chrome
may not hand that dialog to a new debugger session. Completed release invalidates
old dialog IDs; Stop and authority loss always detach even with a dialog open.
Dialogs on already-uncertain attachments cannot block a detach retry; release
names them in `abandonedDialogs`. A dialog can still open after release from
page work that was already dispatched. `observedDialog: null` means unobserved,
not proof of absence. A refusal
to handle it is not proof the page has no dialog. Optional favicon work is
bounded, waits for event readiness, and cannot prevent debugger detachment.

## Background operation

Extension 0.8.2 creates ordinary and browser-root CDP tabs in the background
by default. The source CLI sends `active: false` explicitly so it also avoids
selecting tabs with older extensions. `--background` remains accepted;
`browser navigate --new-tab --foreground --url URL` explicitly selects a new
tab. Tab selection and bringing the OS window forward are separate effects.

Browser input uses `Emulation.setFocusEmulationEnabled` before dispatch,
without selecting the tab or focusing its window. This emulates a focused,
visible page for website scripts; it changes page focus/visibility semantics
while attached. Release explicitly clears the override with a bounded command
before detach rather than depending on debugger teardown.
This does not undo the DOM element focus produced by typing: in the Mac
fixture `document.hasFocus()` could remain true after normal hidden visibility
returned, while the user's foreground application remained unchanged.
An uncertain reset is reported as `virtualFocusResetUnconfirmed` on release
and `virtualFocus: reset_unconfirmed` in tab enumeration. Unsupported preparation
refuses; the extension never substitutes foreground or desktop input.

Known CDP presentation commands (`Page.bringToFront`, `Target.activateTarget`,
and explicitly foreground target creation) require opt-in. For a one-shot
`browser.cdp`, send `allowForeground: true` (source CLI: `--foreground`).
For a retained CDP connection, send
`MachineControl.setForegroundAllowed` with `{"allowed":true}` before explicit
foreground commands, and `{"allowed":false}` to end that mode. Each new
connection starts with foreground disabled; queued activation rechecks the
mode at dispatch. This opt-in is cooperative task policy, not a new grant or
containment of arbitrary scripts, page popups, desktop access or a same-user
shell. It does not implement an operator-only foreground permission.

Older installed CLIs can still express the one-shot opt-in through their
typed raw request transport, for example `desktop raw` with
`{"operation":"browser.cdp","tabId":7,"method":"Page.bringToFront","allowForeground":true}`.
Use an actually observed tab ID; the example ID is non-authoritative.

Browser-root management has a five-second deadline and at most 64 retained
requests, eight unsettled management dispatches and eight independent discovery
dispatches. Discovery and tab close do not wait on the mutation queue.
A management timeout ends its owning connection with an unknown-effect reason;
late continuations are fenced and no action is replayed on reconnect. Unsettled
Chrome calls retain their physical slots until they finish. Chrome's native
saved-group confirmation remains distinct from `browser.dialog`; automatic
confirmation or synced-group deletion is not introduced.

Controlled tabs show an owned blue pointer over their site favicon. Newly
created agent tabs join a blue **Machine Control** group in their own window;
existing and pinned tabs keep their grouping. Listing tabs alone adds no marker.
`browser.tabs` reports `groupId` and `controlIndicator` (`none`, `active`, or
`unavailable`), so restricted-page omissions remain visible to callers.

Release, ended/replaced grants, native disconnect, and worker recovery restore
site icons and remove unchanged owned grouping. Site icon updates and user
renames, recolors, moves, shared groups, and added tabs are preserved. The icon
expires independently after ten seconds without a worker heartbeat. Indicators
use the authorized per-tab debugger in an isolated world; no page content
scripts or broad host permissions are added. They are visible status, not an
authorization boundary or a marker of completed work.

The toolbar button opens a read-only side panel (`panel.html`) showing the
connection, access, controlled tabs and a live feed of agent operations. The
feed stays in worker memory and omits typed text, scripts, CDP parameters and
page content. A store install opens the same page once as setup guidance.

## Web Store release

Store releases go to item `epejchbeajneooefnklikkfhbaeadkpc` through
[`chrome-extension.yml`](../../.github/workflows/chrome-extension.yml),
following the same pattern as the author's other extensions:

1. Add a `## [<version>]` section to [`CHANGELOG.md`](CHANGELOG.md) and commit.
2. From a clean, current `main`, run `providers/chrome-extension/release.py
   <version>`. It bumps `manifest.json` when the version is newer (or keeps an
   already-prepared untagged version), commits, and atomically pushes `main`
   and `extension-v<version>`.
3. CI runs the browser tests, then `package.py DIR`, which writes a
   reproducible ZIP without the development `key` plus `build.json` (version,
   store ID, source revision, clean-tree flag and SHA-256), refusing a dirty
   source. Only then does it authenticate with Google and run
   [`store/publish-store.mjs`](store/publish-store.mjs). The publisher checks
   the revision, checksum and pinned store identity in
   [`store/identity.json`](store/identity.json) (item ID and the public key the
   store signs with), cancels an older pending submission once if needed,
   uploads and submits with review enabled. A GitHub release (never marked
   latest; the site and updater select only `desktop-v*` tags) keeps the ZIP,
   build record and store receipt.

Google still reviews and publishes; a green workflow means submitted, not
delivered. Listing, screenshots, privacy and permission justifications remain
dashboard forms. Verify store authentication without changing anything with
`gh workflow run chrome-extension.yml --ref main -f mode=check`.

Authentication uses GitHub OIDC through Google workload identity federation;
no private key or refresh token is stored. The `chrome-web-store` environment
admits only branch `main` and tags `extension-v*` and holds the variables
`CWS_WIF_PROVIDER`, `CWS_SERVICE_ACCOUNT` and `CWS_PUBLISHER_ID`. Its provider
condition pins this repository's immutable IDs, the environment's immutable
OIDC subject, this workflow's `workflow_ref` and those refs; only that subject
may impersonate the store service account. The concrete Google resources are
deliberately not recorded in this public repository.

`store/render.sh CHROMIUM OUTPUT_DIR` renders screenshots and the promo tile
from the real panel with fictional mock data, and
[`store/listing.md`](store/listing.md) holds listing text and review answers.
[Tactical 117](../../docs/tactical/117-chrome-web-store-extension.md) owns the
release sequence.

Run lifecycle checks with `node --test tests/browser/*.test.mjs`. The headed
[`indicators-live.py`](../../tests/browser/indicators-live.py) runner exercises
real Chrome for Testing and a native resident inside a claimed Mac appliance;
its caller owns target selection, claims, grant approval, and power cleanup.

References look like `TAB:GENERATION:NODE`. Taking a new snapshot or loading a
new page makes older references stale.

## Development install

The manifest carries a fixed public `key`, so the unpacked extension always
has the ID `ncbfifkjllmnkkjmomjohinigfgdocjc`. The Chrome Web Store release
has the ID `epejchbeajneooefnklikkfhbaeadkpc`; native hosts register and
accept both.

1. Install Machine Control.app (`platforms/macos/resident/scripts/install-user.sh`).
2. Register the native host for the browser profile:
   `platforms/macos/resident/scripts/install-browser.sh`. Chrome reads
   user-level hosts from its user data directory, so a separate profile or
   Chrome for Testing needs `--browser-dir DIR`.
3. In `chrome://extensions`, enable Developer mode and choose
   **Load unpacked** with this directory.

Branded Chrome ignores `--load-extension`; Chrome for Testing accepts it,
which is how automated tests load the extension in disposable VMs.

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
| `browser.cdp` | Any DevTools protocol method with its parameters (`devtools` grant) |
| `browser.eval` | Evaluate JavaScript in a tab and return the value (`devtools` grant) |
| `browser.endpoint` | Report the local DevTools WebSocket endpoint template (`devtools` grant) |
| `browser.release` | Detach all debugger sessions |

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

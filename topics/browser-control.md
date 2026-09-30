# Browser Control

Topic: `browser-control`

Status: developer preview extension accepted with Chrome for Testing in a
disposable Tart guest; not yet used with the controller user's own Chrome.
[Tactical 050](../docs/tactical/050-macos-host-control-mvp.md) owns the first
slice.

## Scope

Semantic control of the user's own running Chromium-family browser, with
existing profiles and sign-ins, through the same target selection, grants,
and result vocabulary as desktop control. This applies to physical hosts
([`host-control`](host-control.md)) and to browsers inside VM guests.

## Current

**Current:** [`platforms/chromeos/cdp.py`](../platforms/chromeos/cdp.py) is a
standard-library CDP client. It lists targets, reads a page's full
accessibility tree, finds nodes, and clicks. It depends on ChromeOS's
developer configuration enabling a fixed remote-debugging port. Its desktop
functions borrow ChromeOS accessibility extensions and do not apply
elsewhere; the page-level logic is reusable.

**Current (2026-09-30):** The [Machine Control extension](../providers/chrome-extension)
connects through native messaging to the resident on macOS. In a Tart guest,
Chrome for Testing loaded it unpacked; after a `browser` grant was approved,
typing and clicking produced the fixture page's own text change, a link
navigated, `file:` URLs were refused, and capture produced an artifact. A
same-user process claiming the provider role was refused by the resident's
code-identity check. Chrome for Testing showed no debugger info bar, so its
removal on revocation was not visually confirmed.

**Current (reported by the controller user):** Browser extensions coupled to a
particular assistant product did not work from agents running under
YepAnywhere.

## Decisions

**Decision:** The first route is a Machine Control Chrome extension, loaded
unpacked during development, with a possible Chrome Web Store release later.
Rejected or deferred alternatives:

- Remote-debugging ports: current Chrome refuses them on the default profile,
  and a separate profile lacks the user's sign-ins.
- Chrome's user-consented attach to a running browser: a candidate fallback,
  not yet evaluated.
- Desktop accessibility and input alone: always available, but coarse.

**Decision:** The extension reaches the resident only through Chrome native
messaging, not a localhost port. A small native host shipped in the
application bundle is registered for the extension's fixed ID; Chrome checks
the origin and starts the host, which relays to the resident socket. The
resident accepts the browser-provider role only from a peer whose code
identity matches that bundled host.

**Decision:** The extension uses `chrome.debugger` to attach CDP to individual
tabs, plus `chrome.tabs` for tab lifecycle. Chrome's own “being debugged” bar
is an intended visible indicator. A fixed manifest `key` keeps the unpacked
extension ID stable across checkouts.

**Decision:** Browser operations require the `browser` grant scope in the
resident's grant broker. The extension badge mirrors grant state but does not
enforce it.

## Open

- **Open:** The operation vocabulary: tabs, navigation, a compact accessibility
  snapshot, element actions, text entry, and capture. It should share
  reference and staleness rules with the desktop contract rather than exposing
  raw CDP.
- **Open:** Whether an arbitrary CDP escape hatch is ever exposed, and under
  what grant.
- **Open:** Windows and Linux native-messaging registration, and other
  Chromium browsers.
- **Open:** Web Store publication, which changes the extension ID and install
  flow.

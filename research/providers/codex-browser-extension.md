# Codex / ChatGPT browser extension

## Identity and license

**Current:** OpenAI's browser extension is an optional product-coupled reference
for visible browser control. The downloaded package is named ChatGPT; official
[browser-extension documentation](https://learn.chatgpt.com/docs/chrome-extension)
describes its use from ChatGPT and Codex desktop chats.

**Current:** No top-level source license or manifest license declaration was
found in the reviewed distribution. Component notices do not establish reuse
rights for the application's code or artwork. Treat it as a proprietary
behavior reference; Machine Control has not copied its source or assets.
The exact package version, download provenance, hashes, source symbols, and
license inspection live in the
[spike review](../../../machine-control-spike/docs/codex-browser-indicators.md).

## Architecture and evidence

**Current (2026-10-02, `source-reviewed`):** The MV3 background worker combines
tab/session leases, native messaging, CDP, tab-group management, and content
script publication. This investigation reviewed the tab indicators and their
lifecycle, not the extension's entire security or transport design.

| Capability and route | Evidence | Boundary |
| --- | --- | --- |
| Colored groups using Chromium tabs/tabGroups APIs | `source-reviewed` | New agent tabs and claimed child tabs; existing user-tab takeover does not invoke grouping |
| Per-tab favicon marking through an injected content script | `source-reviewed` | Active ownership and unseen deliverable/handoff status; original favicon availability required by the reviewed publisher |
| Agent cursor overlay in page content | `source-reviewed` | Session messages and a non-intercepting page overlay; not an OS window-frame indicator |
| Browser/platform support | `upstream-claimed` | Official documentation lists desktop/browser availability; no platform live tests in this review |

**Current:** These are source findings from a downloaded distribution. The
extension was not installed or executed for this review. Browser focus, tab
strip rendering, navigation reliability, and restart cleanup remain untested.

## Visible control behavior

**Current:** Newly created agent tabs use `chrome.tabs.group` and
`chrome.tabGroups.update`, with a session title or the default `ChatGPT` and a
random Chrome group color. The group manager tracks only its own groups.
Existing user tabs are claimed without changing their group. The
[May 21 official changelog](https://learn.chatgpt.com/docs/changelog)
also describes moving existing-tab takeover and handoff toward icons to reduce
clutter. This does not imply all preexisting managed groups are removed at
handoff.

**Current:** The icon is the page's favicon. The background obtains a 32-pixel
original from Chrome's extension-local favicon endpoint and sends a state
message. The content script changes page icon links to an SVG data URL:

- active ownership: a pointer over the faded site icon;
- deliverable: a green dot over the site icon;
- handoff: a yellow dot over the site icon.

**Current:** Active means a session owns the tab, not that it is selected in
Chrome. Final dots are recorded only for tabs not already visible and clear
when the user activates the tab or focuses its window with that tab selected.
Navigation and site icon changes trigger republication. Original link values
are restored only while the links still contain an extension-generated marker,
preserving a site's newer icon. Cleanup and missing-icon failures are
best-effort, with explicit time/size bounds.

**Current:** A separate content overlay displays an animated agent cursor and
ignores pointer events. The toolbar action uses its own title/text badges and
static manifest icon. These are distinct from favicon markers and group colors.

Chrome documents the public primitives:
[tab groups](https://developer.chrome.com/docs/extensions/reference/api/tabGroups),
[favicon retrieval](https://developer.chrome.com/docs/extensions/how-to/ui/favicons),
and [toolbar actions](https://developer.chrome.com/docs/extensions/reference/api/action).

## Fit and next evidence

**Proposal:** Reimplement the interaction pattern with owned code and artwork:
named colored groups for new agent tabs, per-tab markers for existing controlled
tabs, and restoration tied to Machine Control's resident authorization and
provider lifecycle. The extension is inspiration, not a required provider or
dependency on an in-target Codex agent.

**Open:** Content injection/permission scope, missing icons and restricted
pages, grouped/pinned/shared tabs, navigation, worker restart, and cleanup after
revocation/disconnect need a bounded Chrome for Testing fixture. Indicators
must mirror actual controlled-tab state rather than the global browser grant;
they are not an authorization boundary. The
[browser-control topic](../../topics/browser-control.md) owns that proposal.

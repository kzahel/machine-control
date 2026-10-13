# 117 — Chrome Web Store extension

Status: active. Step 1 is submitted for review; later steps are proposed.
Owning topic: [browser control](../../topics/browser-control.md).
Provider dossier: [Chrome extension](../../research/providers/chrome-extension.md).

## Objective and completion conditions

Publish the Machine Control extension on the Chrome Web Store so a person can
install it without Developer mode, receive automatic updates and see what an
agent is doing. The extension gains a user surface: a read-only side panel
showing connection, access, controlled tabs and a live activity feed, plus
first-run setup guidance. Complete when:

- the store item is published (unlisted, then public) and installs on
  branded Chrome;
- released desktop apps on macOS, Windows and Linux register both the
  unpacked development ID and the store ID, so a store install connects
  without manual steps;
- the side panel lets a person inspect agent activity live and stop browser
  access without the extension ever granting or extending it; and
- desktop installers can offer the store extension, and a test appliance can
  force-install it by Chrome policy.

## Boundaries

- The resident remains the only authority. The extension may report state and
  request revocation; it never grants, extends or widens access. A compromised
  extension page can at most end access.
- The activity feed stays in extension memory and records operation names, tab
  references, outcomes and counts; never typed text, scripts, CDP parameters or
  page content.
- Chrome for Testing in VMs keeps loading the unpacked development copy; its
  fixed `key` and ID remain supported indefinitely.
- No Edge Add-ons or other-browser store work until the Chrome release has held
  across several desktop releases.
- The store publisher account, review correspondence and any private
  deployment state stay out of Git.

## Ordered work

### 1 — publish the side panel MVP unlisted

- Icons derived from the desktop app's command-key glyph, with a heavier-stroke
  variant for 16–48 px toolbar sizes.
- `panel.html` side panel opened from the toolbar button: connection pill,
  setup steps with download links when the app is absent or rejects this copy,
  access summary, controlled tabs (click to focus) and a live, coalesced
  activity feed. The same page opens once as a welcome tab after a store
  install; unpacked and policy installs stay quiet.
- `package.py` builds the upload without the development `key`;
  `store/render.sh` renders store screenshots and the promo tile from the real
  panel with fictional mock data; `store/listing.md` holds listing text,
  permission justifications and test instructions.
- Allow the store origin `chrome-extension://epejchbeajneooefnklikkfhbaeadkpc/`
  beside the development origin in Mac, Windows and Linux native-host
  registration and origin checks; Windows ownership checks accept manifests
  written by earlier releases.
- Extend the site privacy page with an extension section.
- Create the store item, complete listing, privacy and distribution forms,
  and submit unlisted.

### 2 — ship desktop releases that accept the store ID

Include step 1's host changes in the next desktop release. Store installs
cannot connect to earlier releases: their host manifests list only the
development origin, and the Windows and Linux hosts also refuse other origins
themselves. Until then the panel reports the refusal and asks the person to
update the app. Verify a store install connects on each platform.

### 3 — add a revoke-only Stop control

Add a typed extension-to-resident `browser.stop` message that ends browser and
devtools access exactly as the app's Stop does, plus a side-panel button and a
`commands` keyboard shortcut. Resident tests must prove the message cannot
grant, extend or select scopes. Show grant expiry and requester label when the
resident sends them.

### 4 — deepen live inspection

Turn the activity feed into an inspector: per-entry tab jump, a short-lived
viewport thumbnail for captures the agent already took, DevTools stream
activity counts and a compact timeline. Keep the payload rule from the
boundaries and add a per-session clear on grant end.

### 5 — install without manual setup

Have the desktop installers pre-register the store item through Chrome's
external-extension mechanism (Windows registry, macOS preferences JSON, Linux
external-extension JSON) so Chrome offers it on next start. Add an appliance
recipe that force-installs the store ID by `ExtensionInstallForcelist` on a
dedicated test VM, with doctor reporting extension presence and version.

### 6 — go public

After the store ID has held across a few desktop releases, define a
protocol-compatibility window (extension and app update independently) and
surface version skew in the panel, then switch visibility to public. Consider
Edge Add-ons afterwards.

## Validation

- `node --test tests/browser/*.test.mjs`, including the panel port: state
  reaches only same-extension panels and typed text never appears in activity.
- `python3 bin/check` and Windows `bin/check --native`; Windows x64/ARM64
  publishes; Mac `swift build`.
- Unpacked 0.8.0 loaded in branded Chrome on the Mac host connects through the
  existing development ID, and the side panel shows live access and activity.
- After store approval: install the store copy on each desktop platform with a
  release from step 2 and record connection, panel and indicator behavior.

## Result

**Current (2026-10-13):** Step 1 implementation is complete and the item was
created through Machine Control itself. Chrome refuses extension debugging
on Web Store pages, so the dashboard was driven through the Mac desktop
accessibility, keyboard and pointer route. Store review and steps 2–6 remain.
Friction found while doing so:

- Pointer input was refused as reaching a Machine Control window when a
  hidden-behind app window's bounds contained the point, even though Chrome
  was frontmost there.
- Accessibility press on Chrome's web radio buttons selected the wrong option
  and did not toggle web checkboxes; pointer clicks did.
- Open-panel Go To sheets lost the first typed characters; typing `/` or `~`
  first to open the sheet, then path segments, was reliable.

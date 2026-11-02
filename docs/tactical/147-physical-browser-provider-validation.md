# Validate the physical browser provider and repaired input

Owning topic: [browser control](../../topics/browser-control.md).

Status: **physical recovery verified; source diagnostics and packaging tested**.
Physical follow-up to
[Tactical 146](146-background-browser-click-reproduction.md).

## Objective and completion conditions

The user authorized proceeding with physical locked-console validation,
committing the result and recommending the next investigation.

- Reproduce the original static-page failure using owned background tabs.
- Identify the actual live provider, separately from installed files/version.
- Reload only the selected unpacked provider through normal Chrome controls.
- Verify independent static and focus/layout click effects, text, capture,
  tab-selection preservation and OS lock before accepting recovery.
- Add portable diagnostics/regressions if the missing live identity prevents
  reliable attribution. Close owned tabs, covered ownership and claims.

## Boundaries

Use the existing browser/profile because the reported behavior requires it;
never launch the primary browser with an isolated or temporary profile.
Limit page actions to owned fixtures and native extension maintenance to the
selected unpacked extension. Use a finite covered owner for native setup;
retain approval and task-end relock. No account authentication, whole-browser
restart, unrelated extension change, host-app replacement or store publication.
Concrete identities, page captures, logs and attribution remain private.

## Ordered work

### 1 — observe the failing live provider

Collect independent fixture events, DOM geometry/visibility, reference shape,
native-host origin and signed runtime/browser versions before any reload.

### 2 — report executing implementation identity

Expose bounded provider identity through existing granted tab discovery,
including a digest of executing operation code rather than a fetch of files
that may have changed since the worker started. Keep identity diagnostic;
it confers no authority and does not establish an application effect.

### 3 — reload and validate the intended provider

Use Chrome's normal native extension controls under covered ownership. Observe
reconnection and fresh identity/references, then run new owned static and
focus-sensitive fixtures without replaying uncertain input.

### 4 — verify cleanup and commit

Run focused regressions, verify relock, close owned tabs/server and release the
claim. Update the gap/topic/provider evidence and commit the bounded result.

## Validation and final result

The existing provider reproduced the reported symptom in two new owned
background tabs: static and focus-sensitive buttons produced no pointer,
mouse or click callbacks and no HTTP effect, although geometry hit testing
identified the button and text insertion worked. The provider emitted legacy
three-part references and left page visibility hidden. Its native-host origin
identified the unpacked development extension, rather than the store copy.
That behavior differs from current source; the old executing bytes were not
captured and its exact revision remains unknown.

A finite covered owner used native Chrome controls to open only the selected
extension's details and request Reload. The semantic action ran, but Chrome
displayed **Failed to load extension** because of a generated `__pycache__`
directory. An initial inference from the unchanged native connection that
Reload had not executed was corrected in the private journal. The cache's
timestamp predates this investigation; its creator is not established, and
the current common check runner already disables bytecode writing.

Only the ignored generated cache was moved to private evidence. Chrome's
explicit Retry loaded current operations. Supporting `browser.tabs` now
reports extension/protocol identity and a SHA-256 digest of the executing
operation closure, not files fetched from disk. The physical digest matches
source and references now carry the authority epoch. This is diagnostic
identity, not authentication, a whole-module/import hash or proof of effects.

Two fresh background fixtures then passed one trusted pointer/click sequence
and one independent HTTP effect each, including a target moved by 180 CSS
pixels on focus. Text, PNG capture and selected-tab preservation also passed;
IOKit independently reported locked throughout the browser-only checks. These
before/after tests use the same existing browser/profile. They establish
recovery after code reload and provider-state reset together, not which
historical patch alone explains the old static failure.

The development packager adds a fresh runtime-only unpacked output, preserving
the manifest key while excluding helper/cache files. It refuses existing
output and does not alter source. A polluted-source fixture verifies that
boundary, and direct CLI generation passes. This new generated-directory mode
is not an automatic migration of the existing source-directory installation.

All 30 extension tests pass, including executing-code identity and polluted
source packaging. Repository portable checks, whitespace and link validation
also pass.
The owned maintenance tab and fixture servers are closed. A bounded cleanup
owner ended `completed` with observed relock, no remaining covers/session and
the original approval retained; the host claim is released. The earlier
five-minute maintenance owner ended by normal expiry with independent relock.
No native app replacement, whole-browser restart, other-extension change,
account authentication or store publication occurred. The selected unpacked
development worker is now running the repaired source.

Broader sites, store-installed delivery, other physical configurations and
cross-platform execution remain separately qualified. The next substantial
investigation is the physical covered-editing/guardian sequence, beginning
with live resident identity and independent model/save/reload effects.

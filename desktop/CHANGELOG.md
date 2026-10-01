# Desktop changelog

## [Unreleased]

## [0.4.4]

- Add Windows Chrome extension setup and scoped browser control.
- Keep browser scripts and raw DevTools behind a separate approval scope.
- Refuse stale browser references after grant or provider changes and report
  uncertain delivery when a browser request times out.
- Preserve startup and browser registration during updater replacement; remove
  only the owning installation's browser registration on ordinary uninstall.

Windows browser support uses the bundled unpacked extension. File upload,
raw CDP WebSockets, and browser-level attachment are not available on this
Windows candidate. Public Windows publication remains a separate gate.

## [0.4.3]

- Refuse Cua stale-element errors even when its CLI exits successfully.
- Keep capture-superseded actions from reporting accepted delivery on Windows.

Windows signed preview acceptance requires independent application effects.

## [0.4.2]

- Verify installed Windows files using paths relative to the product root,
  including controllers whose temporary directory uses a Windows short alias.
- Reject incomplete, duplicate, or unsafe installed payload inventories.

This candidate continues the signed Windows VM acceptance work. Publication
remains a separate gate.

## [0.4.1]

- Guard Windows taskbar and tray controls owned by Explorer.
- Refuse operator clicks through transparent provider cursor overlays.
- Report Windows local host grant state through the common CLI.

This Windows acceptance candidate also exercises the signed upgrade from 0.4.0.
Windows publication remains gated by installed acceptance.

## [0.4.0]

- Windows desktop preview with shared settings and tray controls.
- Native scoped approvals, expiry, Stop, and session revocation on Windows.
- Bundled ordinary-user runtime with signed installers and update packages.
- Windows startup preference and supervised resident lifecycle.

Windows signed candidates precede public release. Grants apply to all callers
running as the same user. Protected desktops and browser integration are outside
the Windows preview; architecture-specific acceptance is recorded separately.

## [0.3.5]

- Reliable Restart and relaunch after signed updates.

When updating from 0.3.3 or 0.3.4, reopen Machine Control if it closes after
installation. Those versions can install the update but miss automatic relaunch.

## [0.3.4]

- Settings and Check for Updates in the menu bar.
- Production update checks and signed installation with access off.
- Bounded update checks with concise status and retry messages.

Grants apply to all callers running as the same user. Native acceptance covers
ARM64 Tart; physical Mac and Intel runtime acceptance remain open.
Windows and Linux desktop apps are not available yet.

## [0.3.3]

- First public Mac desktop preview for Apple silicon and Intel.
- Compact Access, Permissions, Activity, and Settings tabs.
- Visible approval, scope and duration controls, and Stop access.
- Developer ID signing, notarization, and authenticated update packages.
- Tagged releases with required changelogs and latest Mac download links.

Grants apply to all callers running as the same user. Live native acceptance
covers ARM64 Tart; physical Mac and Intel runtime acceptance remain open.
Windows and Linux desktop apps are not available yet. The in-app update feed
is not deployed; install new versions from the download page.

# Machine Control Chrome extension changelog

Store releases are tagged `extension-v<version>`; see
[Web Store release](README.md#web-store-release).

## [0.8.4] - 2026-10-27

- Declare local file URL access so Chrome exposes the "Allow access to file
  URLs" switch required for file uploads. Users still enable it explicitly
  on the extension's details page.

## [0.8.3] - 2026-10-26

- Build the store upload outside the checkout so generated ZIPs do not fail
  clean-source verification. Replaces the 0.8.2 release attempt, which failed
  before store upload; includes all of its browser-control changes below.

## [0.8.2] - 2026-10-26 (CI failed before store submission)

- Open agent tabs in the background by default, including browser-level CDP.
- Deliver browser input using virtual page focus without selecting tabs or
  bringing browser windows forward; refuse when that preparation is unavailable.
- Require explicit opt-in for known CDP foreground commands, reset it on
  reconnect and fence queued activation after withdrawal.
- Bound browser-level management, keep discovery independent of stalled tab
  close, and fence timed-out connections without replaying uncertain actions.
- Include the 0.8.1 request, dialog and cleanup hardening in the store update.

## [0.8.1] - Bundled development update

- Bound ordinary requests per tab, preserve request authority across waits,
  cancel abandoned queued work and report uncertain dispatched effects.
- Keep discovery, grant fencing, dialog recovery and debugger release
  responsive despite a stalled page. Release confirmed detached queue slots.
- Expose typed dialog state and handling; bound optional indicator work and
  serialize cleanup across grant changes and reconnects.
- Reserve Page-domain events for dialog recovery, including streamed CDP.

## [0.8.0] - 2026-10-13

First Chrome Web Store submission (unlisted), uploaded from the dashboard.

- Icons and a read-only side panel: connection, access, controlled tabs and
  a live activity feed that omits typed text, scripts and page content.
- Setup guidance after a store install.

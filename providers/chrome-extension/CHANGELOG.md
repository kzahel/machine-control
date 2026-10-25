# Machine Control Chrome extension changelog

Store releases are tagged `extension-v<version>`; see
[Web Store release](README.md#web-store-release).

## [0.8.1] - Unreleased

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

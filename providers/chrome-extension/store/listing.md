# Chrome Web Store listing

Item ID: `epejchbeajneooefnklikkfhbaeadkpc`. Category: Developer Tools.
Language: English. Visibility: unlisted until desktop releases register the
store ID (see [Tactical 117](../../../docs/tactical/117-chrome-web-store-extension.md)).
Regenerate screenshots and the promo tile with `store/render.sh`; build the
upload with `package.py`.

## Description

Machine Control lets AI agents that you run use Chrome on your computer, only while you allow it.

This extension is the browser half of the free, open-source Machine Control desktop app for macOS, Windows and Linux. It connects only to that app on the same computer, through Chrome native messaging, and does nothing until you grant browser access in the app.

While you allow it, an agent can:
- list tabs, open pages and wait for them to load
- read a page's accessibility structure, then click, type or press keys
- take tab screenshots and attach files you name to upload fields
- with a separate DevTools grant, send DevTools protocol commands or connect Playwright and Puppeteer to your real, signed-in Chrome

You can always see what is happening:
- the toolbar badge shows ON while browser control is granted, and DEV for full DevTools access
- controlled tabs show a blue pointer icon, and new agent tabs join a blue Machine Control tab group
- the side panel shows the connection, the tabs under control and a live feed of agent actions; it never records typed text, scripts or page content

Setup:
1. Install the Machine Control app from https://machinecontrol.dev/downloads/
2. Turn on Browser in the app's setup checklist
3. Approve access when your agent asks, and stop it any time from the app

Privacy: the extension sends nothing to Machine Control servers and has no analytics. Details: https://machinecontrol.dev/privacy/

Source code: https://github.com/kzahel/machine-control

## Single purpose

Let AI agents that the user runs operate Chrome tabs through the Machine Control desktop app on the same computer, only while the user has granted browser access in that app, and show the user what the agent is doing.

## Permission justifications

- **debugger**: Chrome DevTools protocol on the tabs an agent controls is how the extension reads page structure, clicks, types, captures screenshots and attaches files. It attaches only while the user's browser grant is active and detaches when the grant ends.
- **`file:///*`**: declares local file access so Chrome exposes the "Allow access to file URLs" switch needed to attach local files to upload fields. The user must enable that switch separately; upload requests also require the desktop app's browser grant.
- **nativeMessaging**: the only connection the extension makes is to the Machine Control desktop app on the same computer, which checks the user's grant before forwarding any request.
- **tabs**: lists, opens, navigates and focuses tabs for agent requests, and shows controlled tabs in the side panel.
- **tabGroups**: puts new agent-created tabs in a visible "Machine Control" group and removes that grouping when control ends.
- **favicon**: reads site icons so a controlled tab's icon can show a pointer marker and be restored afterwards.
- **storage**: remembers which tab icons and groups the extension changed, so it can restore them after a browser or extension restart.
- **alarms**: reconnects to the desktop app after it restarts or after Chrome suspends the extension.
- **sidePanel**: shows connection state, access, controlled tabs and a live activity feed when the user clicks the toolbar button.
- **Remote code**: no. All code ships in the package; the extension loads no remote scripts. Script evaluation requested by an agent under the separate DevTools grant runs in the page through the debugger, not in the extension.

## Data usage

Declared: website content (page structure, screenshots and values an agent reads are returned to the desktop app on the user's computer, at the user's direction). Not sold, not used for unrelated purposes, not used for creditworthiness or lending.

## Test instructions

Needs the free Machine Control desktop app (https://machinecontrol.dev/downloads/). Without it, click the toolbar button: the side panel shows Not connected and setup steps. With it: open the app, turn on Browser, then run its bundled CLI: `--target host grant request --scope browser --reason test`, approve in the app, and run `--target host browser tabs`. The badge shows ON and the side panel lists each action.

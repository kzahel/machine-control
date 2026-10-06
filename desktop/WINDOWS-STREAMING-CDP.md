# Windows streaming CDP

This feature ships in public desktop 0.5.7. The resident exposes
target-loopback, per-tab and browser-level CDP WebSockets through the existing Chrome extension.
Commands and events use ordinary CDP JSON. No browser debug port or UAC helper
is required.

## Usage

Set up the extension in **Permissions**, load it in Chrome, and enable
**Browser scripts and DevTools**. Keep a live owner with `devtools` scope open
for the entire WebSocket session. Include `browser` scope when using ordinary
tab discovery or navigation through that owner.

Request `{"operation":"browser.endpoint"}` through the Python SDK's retained
`ControlSession.call` or the JSON-lines `control stream` command:

```text
machine-control --target TARGET --claim CLAIM control stream \
  --reason "Inspect browser events" --scope browser --scope devtools
```

Send the endpoint request on stdin and leave that stream open. The result's
`data.devtoolsEndpoint` is a template:

```text
ws://127.0.0.1:PORT/devtools/page/<tabId>?token=TOKEN
```

Replace `<tabId>` with the numeric ID from `browser.tabs`. Connect a tab-level
CDP client that omits the `Origin` header. Send, for example:

```json
{"id":1,"method":"Runtime.enable","params":{}}
{"id":2,"method":"Runtime.evaluate","params":{"expression":"document.title","returnByValue":true}}
```

Replies have `id` and `result` or `error`; streamed events have `method` and
`params`. Subscription lifetime belongs to that connection. A one-shot CLI
`browser endpoint` returns `retained_owner_required` when the resident requires
ownership, because ending the command would immediately invalidate its URL.

The same response's `data.browserEndpoint` addresses the browser facade:

```text
ws://127.0.0.1:PORT/devtools/browser?token=TOKEN
```

Keep the same owner alive while connecting a browser client. With Playwright
1.63, use `chromium.connectOverCDP(browserEndpoint, { noDefaults: true })` to
preserve the current profile's browser defaults, including download policy.
Use `browser.contexts()[0]` for existing tabs or `context.newPage()`; creating
an isolated context refuses. Puppeteer 25.12 uses
`puppeteer.connect({ browserWSEndpoint: browserEndpoint, defaultViewport: null })`.
Disconnect the client when finished. The facade refuses `Browser.close`.

Browser discovery exposes supported default-profile pages, omitting incognito,
privileged Chrome pages and the Web Store. Root methods support version/context
observations, target discovery, flattened attachment, new tabs, activation and
close. A logical `mc-default` context identifies the current profile; it does
not provide storage isolation. Synthetic tab wrappers support clients that
attach tabs before their pages. Related native iframe/worker sessions receive
connection-local IDs, preserved on commands, results and events. Unknown or
detached IDs refuse. A root connection excludes raw per-tab connections, and
at most 256 attached routes are retained.

Root auto-attachment cannot pause a newly created renderer before its first
script runs: facade page/tab attachments report `waitingForDebugger: false`.
Native child auto-attachment preserves Chrome's actual waiting flag. Isolated
contexts, browser-wide downloads, shutdown and unavailable CDP domains return
protocol errors. This is a supported compatibility subset; client features
outside it must be qualified separately.

The address is loopback on the **target**, even for an outside caller. An
outside client needs an authenticated forwarding tunnel to that target's
ephemeral port while retaining the same owner. Preserve the target loopback
Host header, for example by forwarding the same local port. The common facade
does not automatically create a WebSocket tunnel. A copied URL cannot open or
renew ownership. Treat its token as bearer access to the current owner's
DevTools authority; do not save it in transcripts, logs or public evidence.

## Authority and limits

Browser-only access cannot create an endpoint. Pause, Stop, expiry, lock/session
loss, owner disconnect, failed audit storage and provider-generation changes
close streams and invalidate old tokens. Resume or provider reconnect requires
a newly issued endpoint, and a new owner when ownership ended. The bridge
checks authority before commands and before forwarding replies/events.

The listener accepts only strict upgrades on IPv4 loopback and refuses every
`Origin` header, including an empty one. It bounds the handshake to 8 KiB and
five seconds, connections to eight, and each tab to one raw connection. Commands
are text objects with a unique outstanding nonnegative 32-bit integer `id`, a
`Domain.method`, optional object `params` and optional bounded `sessionId`.
Client frames are bounded below 1 MiB; native framing overhead
also counts against its 1 MiB limit. At most 16 commands may be outstanding.

Completion has a 45-second deadline. Output queues hold at most 64 frames and
16 MiB in total; a blocked send has a three-second deadline. Malformed frames,
duplicate IDs, exceeded bounds, slow consumers and uncertain completion close
the connection. Commands are never replayed automatically.

Native detach cleanup can finish shortly after socket closure. A connection
attempt to that tab may be refused until the bounded cleanup completes. Wait
for cleanup before reconnecting; never replay uncertain CDP commands.

Raw CDP replies establish provider delivery, not an independently observed
website effect. Check important effects separately. Audit history stores typed
operation, generation, hashed correlation and outcome metadata, excluding URLs,
tokens, CDP methods, parameters, page data and events. Same-user shell access is
not contained. Chrome's debugger indicator remains visible, and Chrome may
refuse restricted tabs or CDP domains.

[Tactical 099](../docs/tactical/099-windows-streaming-cdp.md) owns focused VM
per-tab evidence. [Tactical 100](../docs/tactical/100-browser-level-cdp.md) owns
browser-client qualification. Signed-release, ARM64 and physical qualification
remain separate.

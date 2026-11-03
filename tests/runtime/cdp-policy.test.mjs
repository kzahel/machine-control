import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createRequire } from "node:module";
import { ResidentCore } from "../../runtime/src/core.ts";
import { ManualClock } from "../../runtime/testing/reference-provider.ts";
import { Streams } from "../../runtime/src/streams.ts";
import { CdpBridge } from "../../runtime/node/cdp.ts";
const WebSocket = createRequire(
  new URL("../../runtime/package.json", import.meta.url),
)("ws");

test(
  "shared CDP bridge binds profiles, native owners, command IDs and Stop",
  { timeout: 10_000 },
  async (t) => {
    const clock = new ManualClock(),
      core = new ResidentCore(clock),
      streams = new Streams(core, clock);
    const work = core.connect("work", "fixture.browser"),
      personal = core.connect("personal", "fixture.browser");
    const approval = core.approve([work, personal], 60_000, {
      devtools: true,
    }).approval;
    let nativeAllowed = true;
    const sent = [],
      audits = [];
    const bridge = new CdpBridge(
      streams,
      async (phase, authority, id, delivery) => {
        audits.push({ phase, authority, id, delivery });
        return nativeAllowed;
      },
      (connection, frame, authority) => {
        sent.push({ connection, frame, authority });
        if (frame.type === "session.open")
          queueMicrotask(() =>
            bridge.receive(connection, {
              type: "session.opened",
              id: frame.id,
            }),
          );
        if (frame.type === "session.command")
          queueMicrotask(() =>
            bridge.receive(connection, {
              type: "session.result",
              id: frame.id,
              cmdId: frame.cmdId,
              result: { profile: connection.profileId },
            }),
          );
      },
    );
    t.after(() => bridge.close());
    const workEndpoint = await bridge.endpoint(
      core.fence(approval, work, "browser.cdp"),
      "work-native-owner",
    );
    const personalEndpoint = await bridge.endpoint(
      core.fence(approval, personal, "browser.cdp"),
      "personal-native-owner",
    );
    const ws = new WebSocket(workEndpoint.browserEndpoint),
      ps = new WebSocket(personalEndpoint.browserEndpoint);
    t.after(() => {
      ws.terminate();
      ps.terminate();
    });
    await Promise.all([once(ws, "open"), once(ps, "open")]);
    async function call(socket, id) {
      const message = once(socket, "message");
      socket.send(JSON.stringify({ id, method: "Browser.getVersion" }));
      return JSON.parse((await message)[0].toString());
    }
    assert.equal((await call(ws, 7)).result.profile, "work");
    assert.equal((await call(ps, 7)).result.profile, "personal");
    assert.equal(
      (await call(ws, 7)).id,
      7,
      "client IDs can be reused after completion",
    );
    const commands = sent.filter(
      (entry) =>
        entry.frame.type === "session.command" && entry.connection === work,
    );
    assert.notEqual(
      commands[0].frame.cmdId,
      commands[1].frame.cmdId,
      "provider wire IDs are never reused",
    );
    assert.equal(commands[0].authority, "work-native-owner");
    assert.ok(
      audits.some(
        (entry) => entry.phase === "result" && entry.delivery === "confirmed",
      ),
    );
    const workClosed = once(ws, "close"),
      personalClosed = once(ps, "close");
    core.stop();
    bridge.sweep();
    await Promise.all([workClosed, personalClosed]);
    const stale = new WebSocket(workEndpoint.browserEndpoint);
    await once(stale, "error");
    assert.equal(
      streams.lookup(
        new URL(workEndpoint.browserEndpoint).searchParams.get("token"),
      ),
      undefined,
    );
    const fresh = core.approve([work], 60_000, { devtools: true }).approval;
    const freshEndpoint = await bridge.endpoint(
      core.fence(fresh, work, "browser.cdp"),
      "new-native-owner",
    );
    nativeAllowed = false;
    const denied = new WebSocket(freshEndpoint.browserEndpoint);
    await once(denied, "error");
  },
);

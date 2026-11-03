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

async function fixture(t, native = async () => true) {
  const clock = new ManualClock(), core = new ResidentCore(clock), streams = new Streams(core, clock);
  const connection = core.connect("fixture", "fixture.browser");
  const approval = core.approve([connection], 60_000, { devtools: true }).approval;
  const sent = [], audits = [];
  const bridge = new CdpBridge(streams, async (...args) => { audits.push(args); return native(...args); }, (peer, frame) => {
    sent.push(frame);
    if (frame.type === "session.open") queueMicrotask(() => bridge.receive(peer, { type: "session.opened", id: frame.id }));
  });
  t.after(() => bridge.close());
  const endpoint = await bridge.endpoint(core.fence(approval, connection, "browser.cdp"), "fixture-owner");
  async function open() {
    const socket = new WebSocket(endpoint.browserEndpoint);
    t.after(() => socket.terminate());
    await once(socket, "open");
    // The provider-open acknowledgement is asynchronous to the HTTP upgrade.
    for (let i = 0; i < 10; i++) await new Promise(resolve => setImmediate(resolve));
    return socket;
  }
  return { bridge, core, streams, clock, connection, sent, audits, endpoint, open };
}

for (const [name, payload, options] of [
  ["duplicate command property", '{"id":1,"id":2,"method":"Runtime.enable"}'],
  ["escaped duplicate property", '{"id":1,"method":"Runtime.enable","params":{"a":1,"\\u0061":2}}'],
  ["unknown property", '{"id":1,"method":"Runtime.enable","extra":1}'],
  ["invalid method", '{"id":1,"method":"Runtime.enable;"}'],
  ["binary command", Buffer.from('{}'), { binary: true }],
  ["oversize command", 'x'.repeat(1024 * 1024 + 1)],
]) test(`CDP refuses ${name} before provider dispatch`, { timeout: 5000 }, async t => {
  const f = await fixture(t), socket = await f.open(), closed = once(socket, "close");
  socket.send(payload, options);
  await closed;
  assert.equal(f.sent.filter(frame => frame.type === "session.command").length, 0);
  assert.ok(!JSON.stringify(f.audits).includes("Runtime.enable"), "journal metadata excludes payloads");
});

test("CDP bounds pending commands and journals abandoned delivery", { timeout: 5000 }, async t => {
  const f = await fixture(t), socket = await f.open(), closed = once(socket, "close");
  for (let id = 0; id < 17; id++) socket.send(JSON.stringify({ id, method: "Runtime.enable" }));
  await closed;
  assert.ok(f.sent.filter(frame => frame.type === "session.command").length <= 16);
  assert.ok(f.audits.some(([phase,,, delivery]) => phase === "result" && delivery === "unknown"));
});

test("CDP rejects a duplicated outstanding client ID and wrong-session response", { timeout: 5000 }, async t => {
  const f = await fixture(t), socket = await f.open();
  const closed = once(socket, "close");
  socket.send('{"id":1,"method":"Runtime.enable","sessionId":"expected"}');
  while (!f.sent.some(frame => frame.type === "session.command")) await new Promise(resolve => setImmediate(resolve));
  const command = f.sent.find(frame => frame.type === "session.command");
  f.bridge.receive(f.connection, { type: "session.result", id: command.id, cmdId: command.cmdId, sessionId: "wrong", result: {} });
  await closed;
  const next = await f.open(), nextClosed = once(next, "close");
  next.send('{"id":2,"method":"Runtime.enable"}');
  next.send('{"id":2,"method":"Runtime.enable"}');
  await nextClosed;
});

test("CDP requires native audit acceptance before dispatch", { timeout: 5000 }, async t => {
  let begins = 0;
  const f = await fixture(t, async phase => phase !== "begin" || ++begins === 1);
  const socket = await f.open(), closed = once(socket, "close");
  socket.send('{"id":1,"method":"Runtime.enable"}');
  await closed;
  assert.equal(f.sent.filter(frame => frame.type === "session.command").length, 0);
});

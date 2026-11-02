import assert from "node:assert/strict";
import { test } from "node:test";
import { Writable } from "node:stream";
import { ResidentCore } from "../../runtime/src/core.ts";
import { ExtensionProvider } from "../../runtime/src/extension-provider.ts";
import { dispatchToProvider } from "../../runtime/src/provider-dispatch.ts";
import {
  FrameDecoder,
  encodeFrame,
  writeFrame,
  MAXIMUM_FRAME,
} from "../../runtime/node/framing.ts";
import { ManualClock } from "../../runtime/testing/reference-provider.ts";

const providerInfo = {
  extensionId: "fixture",
  extensionVersion: "0.8.4",
  protocolVersion: 1,
  operationsSha256: "a".repeat(64),
};
function fixture() {
  const clock = new ManualClock();
  const core = new ResidentCore(clock);
  const results = [],
    frames = { work: [], personal: [] },
    faults = [];
  const adapters = new Map();
  const consume = (effects) => {
    for (const effect of effects) {
      if (effect.type === "request.finished") results.push(effect.result);
      else if (effect.type === "provider.dispatch")
        dispatchToProvider(
          core,
          adapters.get(effect.command.connection),
          effect.command,
          consume,
        );
      else adapters.get(effect.command.connection)?.cancel(effect.command);
    }
  };
  const make = (profile) => {
    const connection = core.connect(profile, "chrome.extension/cdp");
    const adapter = new ExtensionProvider(core, connection, {
      send: (frame) => frames[profile].push(frame),
      effects: consume,
      fault: () => faults.push(profile),
    });
    adapters.set(connection, adapter);
    adapter.synchronize();
    return adapter;
  };
  const work = make("work"),
    personal = make("personal");
  const synchronize = () => {
    work.synchronize();
    personal.synchronize();
  };
  const approve = (profiles) => {
    const value = core.approve(
      profiles.map((adapter) => adapter.connection),
      10_000,
    );
    synchronize();
    consume(value.effects);
    return value.approval;
  };
  const request = (approval, adapter, requestId, fields = {}) =>
    consume(
      core.request(approval, {
        requestId,
        profileId: adapter.connection.profileId,
        operation: "browser.tabs",
        connection: adapter.connection,
        timeoutMs: 1_000,
        ...fields,
      }),
    );
  const sent = (profile) =>
    frames[profile].filter((frame) => frame.type === "request");
  return {
    clock,
    core,
    results,
    frames,
    faults,
    work,
    personal,
    approve,
    request,
    sent,
    synchronize,
    consume,
  };
}

test("tabs, snapshots and clicks share the core's exact-profile approval", () => {
  const f = fixture();
  f.request(undefined, f.work, "off");
  assert.equal(f.results.at(-1).errorCode, "approval_required");
  assert.equal(f.sent("work").length, 0);
  const approval = f.approve([f.work]);
  assert.equal(f.frames.work.at(-1).browser, true);
  assert.equal(f.frames.personal.at(-1).browser, false);
  f.request(approval, f.personal, "unapproved");
  assert.equal(f.results.at(-1).errorCode, "profile_not_approved");
  assert.equal(f.sent("personal").length, 0);
  f.request(approval, f.work, "tabs");
  const tabs = f.sent("work").at(-1);
  assert.equal(tabs.operation, "browser.tabs");
  assert.deepEqual(tabs.params, {});
  assert.equal(
    f.work.receive({
      type: "response",
      id: tabs.id,
      ok: true,
      data: {
        tabs: [
          {
            tabId: 7,
            title: "Fixture",
            url: "https://example.invalid/",
            omitted: "private",
          },
        ],
        providerInfo,
      },
    }),
    true,
  );
  assert.equal(f.results.at(-1).data.tabs[0].omitted, undefined);
  f.request(approval, f.work, "snapshot", {
    operation: "browser.snapshot",
    tabId: 7,
  });
  const snapshot = f.sent("work").at(-1);
  assert.deepEqual(snapshot.params, {
    tabId: 7,
    maxElements: 64,
    interactiveOnly: true,
  });
  const reference = "7:fixture-reference";
  assert.equal(
    f.work.receive({
      type: "response",
      id: snapshot.id,
      ok: true,
      data: {
        tab: { tabId: 7 },
        elements: [{ reference, role: "button", name: "Increment" }],
      },
    }),
    true,
  );
  f.request(approval, f.work, "click", {
    operation: "browser.click",
    reference: { connection: f.work.connection, target: reference },
  });
  const click = f.sent("work").at(-1);
  assert.deepEqual(click.params, { reference });
  assert.equal(
    f.work.receive({
      type: "response",
      id: click.id,
      ok: true,
      data: { tabId: 7 },
    }),
    true,
  );
  assert.equal(f.results.at(-1).delivery, "confirmed");
  assert.equal(f.results.at(-1).effect, "unverifiable");
});

test("Stop is projected to workers and late wire replies cannot resolve newer labels", () => {
  const f = fixture();
  const first = f.approve([f.work]);
  f.request(first, f.work, "reuse", {
    operation: "browser.click",
    reference: { connection: f.work.connection, target: "reference" },
  });
  const old = f.sent("work").at(-1);
  const stopped = f.core.stop();
  f.synchronize();
  f.consume(stopped);
  assert.equal(
    f.frames.work.findLast((frame) => frame.type === "grant").browser,
    false,
  );
  assert.equal(
    f.frames.personal.findLast((frame) => frame.type === "grant").browser,
    false,
  );
  assert.equal(f.frames.work.at(-1).type, "cancel");
  assert.equal(f.results.at(-1).delivery, "unknown");
  const second = f.approve([f.personal]);
  f.request(second, f.personal, "reuse");
  const fresh = f.sent("personal").at(-1);
  assert.notEqual(old.id, fresh.id);
  const count = f.results.length;
  assert.equal(
    f.work.receive({
      type: "response",
      id: old.id,
      ok: true,
      data: { tabId: 7 },
    }),
    false,
  );
  assert.equal(
    f.personal.receive({
      type: "response",
      id: old.id,
      ok: true,
      data: { tabId: 7 },
    }),
    false,
  );
  assert.equal(f.results.length, count);
  assert.equal(f.core.inspect().pendingRequests, 1);
  assert.equal(
    f.personal.receive({
      type: "response",
      id: fresh.id,
      ok: true,
      data: { tabs: [], providerInfo },
    }),
    true,
  );
  assert.equal(f.core.inspect().retainedRequests, 0);
});

test("remaining budget is rechecked before dispatch and sub-minimum work is refused", () => {
  const f = fixture();
  const approval = f.approve([f.work]);
  const queued = f.core.request(approval, {
    requestId: "delayed",
    profileId: "work",
    operation: "browser.tabs",
    connection: f.work.connection,
    timeoutMs: 500,
  });
  const command = queued.find(
    (effect) => effect.type === "provider.dispatch",
  ).command;
  assert.throws(
    () => dispatchToProvider(f.core, f.personal, command, f.consume),
    /provider_route_mismatch/,
  );
  assert.equal(f.sent("personal").length, 0);
  f.clock.advance(350);
  f.consume(queued);
  assert.equal(f.sent("work").at(-1).timeoutMs, 150);
  const before = f.sent("work").length;
  f.request(approval, f.work, "too-short", { timeoutMs: 50 });
  assert.equal(f.sent("work").length, before);
  assert.equal(f.results.at(-1).delivery, "refused");
  assert.equal(f.core.inspect().unsettledDispatches, 1);
});

test("malformed observations close only that route and retain uncertain dispatch capacity", () => {
  for (const data of [
    null,
    { tabs: [] },
    { tabs: Array(257).fill({}), providerInfo },
  ]) {
    const f = fixture();
    const approval = f.approve([f.work, f.personal]);
    f.request(approval, f.work, "malformed");
    const request = f.sent("work").at(-1);
    assert.equal(
      f.work.receive({ type: "response", id: request.id, ok: true, data }),
      false,
    );
    assert.deepEqual(f.faults, ["work"]);
    assert.equal(f.results.at(-1).delivery, "unknown");
    assert.deepEqual(f.core.inspect().connectedProfiles, ["personal"]);
    assert.equal(f.core.inspect().unsettledDispatches, 1);
    f.request(approval, f.personal, "other-route");
    assert.equal(f.sent("personal").length, 1);
  }
});

test("provider frames cannot approve work or introduce raw operations", () => {
  const f = fixture();
  assert.equal(
    f.work.receive({ type: "grant", browser: true, devtools: true }),
    false,
  );
  assert.deepEqual(f.core.inspect().approvedProfiles, []);
  const approval = f.approve([f.work]);
  assert.throws(() =>
    f.request(approval, f.work, "raw", { operation: "browser.eval" }),
  );
  assert.equal(f.sent("work").length, 0);
});

test("framing handles fragmented UTF-8 and coalesced native messages", () => {
  const frames = [
    { type: "hello", label: "Résumé 音" },
    { type: "response", id: "1", ok: true },
  ];
  const bytes = Buffer.concat(frames.map(encodeFrame));
  const received = [];
  const decoder = new FrameDecoder((frame) => received.push(frame));
  for (const byte of bytes) decoder.push(Buffer.from([byte]));
  decoder.end();
  assert.deepEqual(received, frames);
  const coalesced = [];
  const other = new FrameDecoder((frame) => coalesced.push(frame));
  other.push(bytes);
  other.end();
  assert.deepEqual(coalesced, frames);
});

test("framing refuses invalid sizes, types, UTF-8, truncation and output backlog", () => {
  const header = (size) => {
    const buffer = Buffer.alloc(4);
    buffer.writeUInt32LE(size);
    return buffer;
  };
  for (const bytes of [
    header(0),
    header(MAXIMUM_FRAME + 1),
    Buffer.concat([header(2), Buffer.from("[]")]),
    Buffer.concat([header(3), Buffer.from([0x22, 0xff, 0x22])]),
  ]) {
    assert.throws(() =>
      new FrameDecoder(() => assert.fail("invalid frame delivered")).push(
        bytes,
      ),
    );
  }
  const decoder = new FrameDecoder(() =>
    assert.fail("truncated frame delivered"),
  );
  decoder.push(header(10));
  assert.throws(() => decoder.end());
  assert.throws(() => encodeFrame({ data: "x".repeat(MAXIMUM_FRAME) }));
  const stream = new Writable({ write(_chunk, _encoding, _callback) {} });
  try {
    writeFrame(stream, { data: "x".repeat(MAXIMUM_FRAME - 32) });
    writeFrame(stream, { data: "x".repeat(MAXIMUM_FRAME - 32) });
    assert.throws(() =>
      writeFrame(stream, { data: "x".repeat(MAXIMUM_FRAME - 32) }),
    );
  } finally {
    stream.destroy();
  }
});

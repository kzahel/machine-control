import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { fileURLToPath } from "node:url";
import { PolicyHost } from "../../runtime/node/policy-host.ts";
import { FrameDecoder, encodeFrame } from "../../runtime/node/framing.ts";

test("trusted host fences references across profiles, consent and process epochs", () => {
  const frames = [];
  const host = new PolicyHost((frame) => frames.push(frame));
  assert.equal(host.wakeInMs(), null, "Off has no periodic wakeup");
  let sequence = 0;
  let authorizationGeneration;
  function call(method, params = {}) {
    const id = String(++sequence);
    host.receive({ id, method, ...(method === "request" ? { authorizationGeneration } : {}), ...params });
    const reply = frames.findLast((frame) => frame.id === id);
    if (method === "operator.approve" && reply.ok) authorizationGeneration = reply.data.generation;
    return reply;
  }
  assert.equal(call("provider.connect", { profileId: "work" }).ok, false);
  assert.equal(call("hello", { protocolVersion: 1 }).errorCode, "host_protocol_mismatch", "a legacy parent cannot arm the v2 host");
  assert.equal(call("hello", { protocolVersion: 2 }).ok, true);
  const work = call("provider.connect", { profileId: "work" }).data.connectionId;
  const personal = call("provider.connect", { profileId: "personal" }).data.connectionId;
  call("request", { connectionId: work, requestId: "off", operation: "browser.tabs", timeoutMs: 1000 });
  assert.equal(frames.findLast((frame) => frame.type === "request.finished").result.errorCode, "approval_required");
  call("operator.approve", { connectionIds: [work, personal], durationMs: 60_000 });
  call("request", { connectionId: work, requestId: "snapshot", operation: "browser.snapshot", tabId: 1, timeoutMs: 1000 });
  const sent = frames.findLast((frame) => frame.type === "provider.send" && frame.frame.type === "request");
  call("provider.frame", { connectionId: work, frame: {
    type: "response", id: sent.frame.id, ok: true,
    data: { tab: { tabId: 1 }, elements: [{ reference: "raw:1", role: "button", name: "Fixture" }] },
  } });
  const reference = frames.findLast((frame) => frame.type === "request.finished").result.data.elements[0].reference;
  const click = { operation: "browser.click", reference, timeoutMs: 1000 };
  assert.equal(call("request", { ...click, connectionId: personal, requestId: "wrong" }).ok, true);
  assert.equal(frames.findLast((frame) => frame.type === "request.finished").result.errorCode, "stale_reference");
  assert.equal(call("request", { ...click, connectionId: work, requestId: "right" }).ok, true);
  call("operator.stop");
  assert.equal(frames.findLast((frame) => frame.type === "request.finished").result.delivery, "unknown");
  call("operator.approve", { connectionIds: [work], durationMs: 60_000 });
  call("request", { ...click, connectionId: work, requestId: "old" });
  assert.equal(frames.findLast((frame) => frame.type === "request.finished").result.errorCode, "stale_reference");
  call("provider.disconnect", { connectionId: work });
  const replacement = call("provider.connect", { profileId: "work" }).data.connectionId;
  assert.notEqual(replacement, work);
  assert.equal(call("provider.frame", { connectionId: work, frame: {} }).data.applied, false);
  host.close();
  assert.deepEqual(host.core.inspect().approvedProfiles, []);
  assert.equal(host.wakeInMs(), null);
  const fresh = new PolicyHost(() => {});
  assert.notEqual(fresh.bootId, host.bootId);
  assert.deepEqual(fresh.core.inspect().approvedProfiles, []);
  fresh.close();
});

test("wire request and grant identities cannot repeat after policy restart", () => {
  function boot() {
    const frames = [], host = new PolicyHost(frame => frames.push(frame));
    let sequence = 0, generation;
    function call(method, fields = {}) {
      const id = `rpc-${++sequence}`;
      host.receive({ id, method, authorizationGeneration: generation, ...fields });
      const reply = frames.findLast(frame => frame.type === "reply" && frame.id === id);
      assert.equal(reply.ok, true);
      if (method === "operator.approve") generation = reply.data.generation;
      return reply.data;
    }
    call("hello", { protocolVersion: 2 });
    const { connectionId } = call("provider.connect", { profileId: "work" });
    call("operator.approve", { connectionIds: [connectionId], durationMs: 60_000 });
    const grant = frames.findLast(frame => frame.type === "provider.send" && frame.frame.type === "grant").frame;
    call("request", { connectionId, requestId: "same-label", operation: "browser.tabs", timeoutMs: 1000 });
    const request = frames.findLast(frame => frame.type === "provider.send" && frame.frame.type === "request").frame;
    return { host, frames, call, connectionId, grant, request };
  }
  const old = boot(); old.host.close();
  const fresh = boot();
  try {
    assert.notEqual(old.request.id, fresh.request.id);
    assert.notEqual(old.grant.grantGeneration, fresh.grant.grantGeneration);
    assert.equal(fresh.call("provider.frame", { connectionId: fresh.connectionId,
      frame: { type: "response", id: old.request.id, ok: true, data: { tabs: [] } } }).applied, false);
    assert.equal(fresh.frames.some(frame => frame.type === "request.finished"), false);
    assert.equal(fresh.call("provider.frame", { connectionId: fresh.connectionId,
      frame: { type: "response", id: fresh.request.id, ok: true, data: { tabs: [], providerInfo: { protocolVersion: 1, extensionId: "fixture", extensionVersion: "fixture", operationsSha256: "a".repeat(64) } } } }).applied, true);
  } finally { fresh.host.close(); }
});

// The same smoke runs against the bundled Node directory or Bun executable.
// Never interpret this as provider authentication or installed acceptance.
const command = process.env.MC_POLICY_COMMAND ? JSON.parse(process.env.MC_POLICY_COMMAND) :
  [process.execPath, fileURLToPath(new URL("../../runtime/node/main.ts", import.meta.url))];

function child() {
  const child = spawn(command[0], command.slice(1), { stdio: ["pipe", "pipe", "pipe"], env: {} });
  const frames = [];
  const decoder = new FrameDecoder((frame) => frames.push(frame));
  child.stdout.on("data", (chunk) => decoder.push(chunk));
  let sequence = 0;
  let authorizationGeneration;
  async function call(method, fields = {}) {
    const id = String(++sequence);
    child.stdin.write(encodeFrame({ id, method, ...(method === "request" ? { authorizationGeneration } : {}), ...fields }));
    const deadline = performance.now() + 20_000;
    while (!frames.some((frame) => frame.id === id)) {
      if (child.exitCode !== null || performance.now() > deadline) throw new Error("host_reply_missing");
      await new Promise((resolve) => setTimeout(resolve, 2));
    }
    const reply = frames.find((frame) => frame.id === id);
    assert.equal(reply.ok, true);
    if (method === "operator.approve") authorizationGeneration = reply.data.generation;
    return reply.data;
  }
  return { child, frames, call };
}

test("executable EOF revokes unsettled work and exits without live handles", { timeout: 45_000 }, async (t) => {
  const actor = child();
  t.after(() => actor.child.kill());
  await actor.call("hello", { protocolVersion: 2 });
  const { connectionId } = await actor.call("provider.connect", { profileId: "work" });
  await actor.call("operator.approve", { connectionIds: [connectionId], durationMs: 60_000 });
  await actor.call("request", { connectionId, requestId: "held", operation: "browser.tabs", timeoutMs: 1000 });
  const exited = once(actor.child, "close");
  actor.child.stdin.end();
  assert.deepEqual(await exited, [0, null]);
  const terminal = actor.frames.find((frame) => frame.type === "request.finished");
  assert.equal(terminal.result.delivery, "unknown");
  const lastGrant = actor.frames.findLast((frame) => frame.type === "provider.send" && frame.frame.type === "grant");
  assert.equal(lastGrant.frame.browser, false);
});

test("killed executable restarts empty, with no consent or request replay", { timeout: 45_000 }, async (t) => {
  const actor = child();
  t.after(() => actor.child.kill());
  const first = await actor.call("hello", { protocolVersion: 2 });
  const { connectionId } = await actor.call("provider.connect", { profileId: "work" });
  await actor.call("operator.approve", { connectionIds: [connectionId], durationMs: 60_000 });
  await actor.call("request", { connectionId, requestId: "held", operation: "browser.tabs", timeoutMs: 1000 });
  const exited = once(actor.child, "close");
  actor.child.kill("SIGKILL");
  await exited;
  const fresh = child();
  t.after(() => fresh.child.kill());
  const second = await fresh.call("hello", { protocolVersion: 2 });
  assert.notEqual(first.bootId, second.bootId);
  const state = await fresh.call("state");
  assert.deepEqual(state.approvedProfiles, []);
  assert.deepEqual(state.connectedProfiles, []);
  assert.equal(state.retainedRequests, 0);
  assert.equal(fresh.frames.some((frame) => frame.type === "provider.send"), false);
  const done = once(fresh.child, "close");
  fresh.child.stdin.end();
  await done;
});

test("executable deadline wakes revoke authority without a state polling client", { timeout: 45_000 }, async (t) => {
  const actor = child();
  t.after(() => actor.child.kill());
  await actor.call("hello", { protocolVersion: 2 });
  const { connectionId } = await actor.call("provider.connect", { profileId: "work" });
  // Emulated x64 process/pipe startup can consume seconds on ARM64 Windows.
  // Exercise expiration after dispatch, rather than assuming an IPC budget.
  const lifetime = process.env.MC_POLICY_SLOW === "1" ? 4000 : 1000;
  await actor.call("operator.approve", { connectionIds: [connectionId], durationMs: lifetime });
  await actor.call("request", { connectionId, requestId: "held", operation: "browser.tabs", timeoutMs: 10_000 });
  const deadline = performance.now() + 10_000;
  while (!actor.frames.some((frame) => frame.type === "request.finished")) {
    assert.ok(performance.now() < deadline, "Host must wake on expiry itself");
    await new Promise((resolve) => setTimeout(resolve, 2));
  }
  const terminal = actor.frames.find((frame) => frame.type === "request.finished");
  assert.equal(terminal.result.errorCode, "approval_expired");
  assert.equal(terminal.result.delivery, "unknown");
  let grant;
  do {
    grant = actor.frames.findLast((frame) => frame.type === "provider.send" && frame.frame.type === "grant");
    if (grant?.frame.browser === false) break;
    assert.ok(performance.now() < deadline, "Revocation projection must arrive independently of terminal-result framing");
    await new Promise((resolve) => setTimeout(resolve, 2));
  } while (true);
  assert.equal(grant.frame.browser, false);
  const done = once(actor.child, "close");
  actor.child.stdin.end();
  assert.deepEqual(await done, [0, null]);
});

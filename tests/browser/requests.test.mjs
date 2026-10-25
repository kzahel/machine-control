import assert from "node:assert/strict";
import { test } from "node:test";
import { RequestQueue } from "../../providers/chrome-extension/requests.js";

test("expiry refuses queued input and fences a late in-flight continuation", async () => {
  const abandoned = [];
  const queue = new RequestQueue({ timeoutMs:30, abandoned:(context) => abandoned.push(context.id) });
  let resolveHeld;
  let presses = 0;
  const first = queue.submit("first", { check() {}, prepare:() => 1, run:async (context) => {
    context.tabId = 1; context.dispatch();
    await new Promise((resolve) => { resolveHeld = resolve; });
    context.check(); presses++;
  } });
  const second = queue.submit("second", { check() {}, prepare:() => 1,
    run:(context) => { context.dispatch(); presses++; } });
  const other = queue.submit("other", { check() {}, prepare:() => 2, run:() => "progress" });
  const outcomes = await Promise.allSettled([first, second, other]);
  assert.equal(outcomes[0].reason.code, "browser_timeout");
  assert.equal(outcomes[0].reason.delivery, "unknown");
  assert.equal(outcomes[1].reason.delivery, "refused");
  assert.equal(outcomes[2].value, "progress");
  assert.deepEqual(abandoned, ["first"]);
  assert.equal(queue.active, 1, "A reply timeout cannot reclaim unresolved Chrome capacity");
  resolveHeld();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(presses, 0);
  assert.equal(queue.active, 0);
});

test("cancel and authority replacement fence requests before dispatch", async () => {
  const queue = new RequestQueue();
  let valid = true;
  let ready;
  let effects = 0;
  const first = queue.submit("one", { check:() => { if (!valid) throw new Error("old authority"); },
    prepare:() => new Promise((resolve) => { ready = resolve; }), run:() => { effects++; } });
  await new Promise((resolve) => setImmediate(resolve));
  queue.cancel("one"); valid = false; ready(1);
  await assert.rejects(first, { code:"browser_cancelled", delivery:"refused" });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(effects, 0);
  assert.equal(queue.requests.size, 0);
});

test("unresolved work retains bounded capacity instead of accumulating hung commands", async () => {
  const queue = new RequestQueue({ capacity:1, timeoutMs:20 });
  let finish;
  const hung = queue.submit("hung", { check() {}, prepare:() => 1, run:async (context) => {
    context.dispatch(); await new Promise((resolve) => { finish = resolve; }); context.check();
  } });
  await assert.rejects(hung, { code:"browser_timeout", delivery:"unknown" });
  await assert.rejects(queue.submit("extra", { check() {}, prepare:() => 2, run() {} }), { code:"browser_busy" });
  finish();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(queue.requests.size, 0);
});

test("confirmed detach recovers eight abandoned lanes even when Chrome never settles callbacks", async () => {
  const queue = new RequestQueue({ parallel:8, timeoutMs:20 });
  const held = Array.from({ length:8 }, (_, tabId) => queue.submit(String(tabId), {
    check() {}, prepare(context) { context.tabId = tabId; return tabId; },
    async run(context) { context.dispatch(); await new Promise(() => {}); context.check(); },
  }));
  const outcomes = await Promise.allSettled(held);
  assert.equal(outcomes.filter((value) => value.reason?.delivery === "unknown").length, 8);
  assert.equal(queue.active, 8);
  for (let tabId = 0; tabId < 8; tabId++) queue.detached(tabId);
  assert.equal(queue.active, 0);
  assert.equal(await queue.submit("fresh", { check() {}, prepare:() => 0, run:() => "recovered" }), "recovered");
});


test("deadline checks fence a resumed microtask before the timeout callback runs", async () => {
  const queue = new RequestQueue({ timeoutMs:1000 });
  const now = Date.now;
  let resume;
  let dispatched = false;
  const result = queue.submit(700, { check() {}, prepare() { return 7; },
    async run(context) {
      await new Promise(resolve => { resume = resolve; });
      context.dispatch(); dispatched = true;
    } });
  while (!resume) await new Promise(resolve => setImmediate(resolve));
  try {
    Date.now = () => now() + 2000;
    resume();
    await assert.rejects(result, error => error.code === "browser_timeout" && error.delivery === "refused");
    assert.equal(dispatched, false);
  } finally { Date.now = now; }
});

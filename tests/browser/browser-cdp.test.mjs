import test from "node:test";
import assert from "node:assert/strict";
import { BrowserCdp } from "../../providers/chrome-extension/browser_cdp.js";

const event = () => ({ listeners: [], addListener(fn) { this.listeners.push(fn); }, emit(...args) { for (const fn of this.listeners) fn(...args); } });

test("browser facade routes targets, child sessions, lifecycles and authority", async () => {
  const tabs = new Map([[1, { id: 1, url: "https://fixture.invalid/", title: "First" }],
    [2, { id: 2, url: "chrome://settings/" }], [3, { id: 3, url: "https://chromewebstore.google.com/" }],
    [4, { id: 4, url: "https://fixture.invalid/private", incognito: true }]]);
  const frames = [], commands = [], held = new Set();
  let authority = "first", nextTab = 5, pending;
  const chrome = {
    tabs: {
      onCreated: event(), onUpdated: event(), onRemoved: event(),
      async query() { return [...tabs.values()]; },
      async create(params) { const tab = { ...params, id: nextTab++ }; tabs.set(tab.id, tab); this.onCreated.emit(tab); return tab; },
      async update(id, changes) { Object.assign(tabs.get(id), changes); this.onUpdated.emit(id, changes); },
      async remove(id) { tabs.delete(id); held.delete(id); this.onRemoved.emit(id); },
    },
    debugger: {
      onEvent: event(), onDetach: event(),
      async getTargets() { return [...tabs.values()].map((tab) => ({ id: "native-" + tab.id, tabId: tab.id, type: "page" })); },
      async sendCommand(target, method, params) {
        commands.push({ target, method, params });
        if (method === "Runtime.fixturePending") return new Promise((resolve) => { pending = resolve; });
        return { echoed: target };
      },
    },
  };
  const cdp = new BrowserCdp({ chrome, ensureAttached: async (tab) => held.add(tab),
    releaseTab: async (tab) => { if (!cdp.usesTab(tab)) held.delete(tab); },
    trackNewTab: async (tab) => held.add(tab), authority: () => authority, post: (frame) => frames.push(frame) });
  const flush = async () => { await cdp.serial; await new Promise((resolve) => setImmediate(resolve)); await cdp.serial; };
  let id = 0;
  async function call(method, params = {}, sessionId) {
    const cmdId = ++id;
    await cdp.command({ id: "root", cmdId, method, params, ...(sessionId ? { sessionId } : {}) });
    return frames.find((frame) => frame.type === "session.result" && frame.cmdId === cmdId);
  }
  authority = null;
  await assert.rejects(cdp.open("denied", 0), /DevTools/);
  authority = "first";
  await cdp.open("root", 0);
  await assert.rejects(cdp.open("other", 1), /exclusive/);
  const infos = (await call("Target.getTargets")).result.targetInfos;
  assert.deepEqual(infos.map((info) => info.targetId), ["native-1"]);
  const discovered = await call("Target.setDiscoverTargets", { discover: true, filter: [{}] });
  assert.deepEqual(discovered.result, {});
  assert.ok(frames.some((frame) => frame.method === "Target.targetCreated" && frame.params.targetInfo.type === "browser"));
  assert.equal((await call("Target.createBrowserContext")).error.code, -32601);
  assert.equal((await call("Browser.close")).error.code, -32601);
  assert.equal((await call("Browser.setDownloadBehavior")).error.code, -32601);
  assert.equal((await call("Target.createTarget", { url: "about:blank", browserContextId: "isolated" })).error.code, -32000);
  assert.equal((await call("Target.createTarget", { url: "chrome://settings" })).error.code, -32000);
  assert.equal((await call("Target.setAutoAttach", { autoAttach: true, flatten: false, waitForDebuggerOnStart: true })).error.code, -32602);
  assert.equal((await call("Target.setAutoAttach", { autoAttach: true, flatten: true, waitForDebuggerOnStart: true, filter: [{ exclude: "yes" }] })).error.code, -32602);
  await call("Target.setAutoAttach", { autoAttach: true, flatten: true, waitForDebuggerOnStart: true });
  const page = frames.find((frame) => frame.method === "Target.attachedToTarget" && frame.params.targetInfo.targetId === "native-1").params.sessionId;
  assert.deepEqual((await call("Runtime.enable", {}, page)).result.echoed, { tabId: 1 });
  assert.equal((await call("Runtime.enable", {}, "native-session-forged")).error.code, -32000);
  assert.equal(commands.length, 1);
  chrome.debugger.onEvent.emit({ tabId: 1 }, "Target.attachedToTarget", {
    sessionId: "native-child", targetInfo: { targetId: "iframe", type: "iframe", url: "https://other.invalid" }, waitingForDebugger: true });
  const child = frames.at(-1).params.sessionId;
  assert.notEqual(child, "native-child");
  assert.equal(frames.at(-1).sessionId, page);
  assert.deepEqual((await call("Runtime.enable", {}, child)).result.echoed, { tabId: 1, sessionId: "native-child" });
  chrome.debugger.onEvent.emit({ tabId: 1, sessionId: "native-child" }, "Runtime.consoleAPICalled", { type: "log" });
  assert.equal(frames.at(-1).sessionId, child);
  await call("Target.detachFromTarget", { sessionId: child }, page);
  assert.deepEqual(commands.at(-1).params, { sessionId: "native-child" });
  assert.equal((await call("Runtime.enable", {}, child)).error.code, -32000);
  const created = (await call("Target.createTarget", { url: "about:blank", background: true })).result.targetId;
  await flush();
  assert.equal(tabs.get(5).active, false);
  assert.ok(frames.some((frame) => frame.method === "Target.targetCreated" && frame.params.targetInfo.targetId === created));
  await call("Target.activateTarget", { targetId: created });
  assert.equal(tabs.get(5).active, true);
  await call("Target.closeTarget", { targetId: created }); await flush();
  assert.ok(frames.some((frame) => frame.method === "Target.targetDestroyed" && frame.params.targetId === created));
  const pendingId = ++id;
  const pendingCall = cdp.command({ id: "root", cmdId: pendingId, method: "Runtime.fixturePending", sessionId: page });
  await new Promise((resolve) => setImmediate(resolve));
  authority = "second";
  chrome.debugger.onEvent.emit({ tabId: 1 }, "Runtime.consoleAPICalled", { secret: "stale" });
  pending({ secret: "stale" }); await pendingCall;
  assert.equal(frames.some((frame) => frame.params?.secret || frame.result?.secret), false);
  await cdp.closeAll("revoked"); assert.equal(held.size, 0);
  await cdp.open("root", 0);
  // Current Puppeteer attaches synthetic tab wrappers, then their real page.
  await call("Target.setAutoAttach", { autoAttach: true, flatten: true, waitForDebuggerOnStart: true,
    filter: [{ type: "page", exclude: true }, {}] });
  const wrapper = frames.filter((frame) => frame.method === "Target.attachedToTarget" && frame.params.targetInfo.type === "tab").at(-1).params.sessionId;
  await call("Target.setAutoAttach", { autoAttach: true, flatten: true, waitForDebuggerOnStart: true }, wrapper);
  const wrapped = frames.at(-2);
  assert.equal(wrapped.method, "Target.attachedToTarget"); assert.equal(wrapped.sessionId, wrapper);
  assert.equal(wrapped.params.targetInfo.type, "page");
  await call("Target.setAutoAttach", { autoAttach: false, flatten: true, waitForDebuggerOnStart: false });
  assert.equal(held.size, 0);
  await call("Target.setAutoAttach", { autoAttach: true, flatten: true, waitForDebuggerOnStart: false });
  chrome.debugger.onDetach.emit({ tabId: 1 }, "canceled_by_user");
  await flush();
  assert.equal(cdp.sessions.has("root"), false);
  chrome.tabs.onUpdated.emit(1, { title: "Indicator cleanup" }); await flush();
  assert.equal(held.size, 0);
  assert.ok(frames.some((frame) => frame.type === "session.closed" && frame.reason === "native_debugger_detached"));
  await cdp.closeAll("finished");
});

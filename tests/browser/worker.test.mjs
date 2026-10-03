import assert from "node:assert/strict";
import { test } from "node:test";

test("real worker cleans markers on resident revocation, release and disconnect", async () => {
  const event = () => {
    const listeners = new Set();
    return { addListener(fn) { listeners.add(fn); }, removeListener(fn) { listeners.delete(fn); },
      emit(...args) { for (const fn of listeners) fn(...args); } };
  };
  const native = { onMessage: event(), onDisconnect: event(), postMessage(message) { replies.push(message); } };
  const replies = [];
  const tabs = new Map();
  const groups = new Map();
  const attached = new Set();
  const markers = new Map();
  const storage = {};
  let next = 1;
  const originalInterval = globalThis.setInterval;
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  globalThis.setInterval = () => 0;
  Object.defineProperty(globalThis, "navigator", { value: { userAgent: "fixture" }, configurable: true });
  globalThis.chrome = {
    action: { setBadgeText() {}, setBadgeBackgroundColor() {}, setTitle() {} },
    runtime: { getManifest: () => ({ version: "fixture" }), connectNative: () => native,
      onStartup: event(), onInstalled: event() },
    alarms: { create() {}, onAlarm: event() },
    storage: { local: { async get() { return storage; },
      async set(value) { Object.assign(storage, structuredClone(value)); },
      async remove(key) { delete storage[key]; } } },
    tabs: {
      onUpdated: event(), onRemoved: event(),
      async query() { return [...tabs.values()]; },
      async get(id) { return tabs.get(id); },
      async create({ url }) { const tab = { id: next++, url, windowId: 1, groupId: -1, status: "complete" };
        tabs.set(tab.id, tab); return tab; },
      async update(id, changes) { Object.assign(tabs.get(id), changes); return tabs.get(id); },
      async group({ groupId, tabIds }) {
        const id = groupId ?? next++;
        if (!groups.has(id)) groups.set(id, { id });
        for (const tabId of tabIds) tabs.get(tabId).groupId = id;
        return id;
      },
      async ungroup(ids) { for (const id of ids) tabs.get(id).groupId = -1; },
    },
    tabGroups: { async get(id) { return groups.get(id); }, async update(id, value) { Object.assign(groups.get(id), value); } },
    debugger: {
      onEvent: event(), onDetach: event(),
      async attach({ tabId }) { assert.ok(!attached.has(tabId)); attached.add(tabId); },
      async detach({ tabId }) { attached.delete(tabId); chrome.debugger.onDetach.emit({ tabId }); },
      async sendCommand({ tabId }, method, params) {
        assert.ok(attached.has(tabId));
        if (method === "Page.getFrameTree") return { frameTree: { frame: { id: String(tabId) } } };
        if (method === "Page.createIsolatedWorld") return { executionContextId: tabId };
        if (method === "Runtime.callFunctionOn") {
          markers.set(tabId, params.arguments[0].value !== null);
          return { result: { value: { visible: markers.get(tabId) } } };
        }
        return {};
      },
    },
  };
  const tick = () => new Promise((resolve) => setImmediate(resolve));
  async function wait(fn) {
    for (let i = 0; i < 100; i++) { const value = fn(); if (value) return value; await tick(); }
    throw new Error("Worker did not settle");
  }
  let id = 0;
  async function request(operation, params = {}) {
    const current = ++id;
    native.onMessage.emit({ type: "request", id: current, operation, params });
    return wait(() => replies.find((reply) => reply.type === "response" && reply.id === current));
  }
  try {
    await import("../../providers/chrome-extension/service_worker.js");
    await wait(() => replies.some((message) => message.type === "hello"));
    native.onMessage.emit({ type: "grant", browser: true, devtools: false, grantGeneration: "first" });
    const created = await request("browser.navigate", { newTab: true, url: "about:blank" });
    assert.equal(created.ok, true);
    const tab = created.data.tab.tabId;
    assert.equal(markers.get(tab), true);
    // Same scopes with a new resident grant must clear prior control state.
    native.onMessage.emit({ type: "grant", browser: true, devtools: true, grantGeneration: "second" });
    await request("browser.tabs");
    assert.equal(markers.get(tab), false);
    assert.equal(tabs.get(tab).groupId, -1);
    assert.equal((await request("browser.capture", { tabId: tab })).ok, true);
    assert.equal(markers.get(tab), true);
    assert.equal(tabs.get(tab).groupId, -1);
    native.onMessage.emit({ type: "grant", browser: false, devtools: false });
    await wait(() => markers.get(tab) === false && !attached.has(tab));
    assert.equal(tabs.get(tab).groupId, -1);
    // A following grant/request must wait for the preceding cleanup.
    native.onMessage.emit({ type: "grant", browser: true, devtools: true });
    assert.equal((await request("browser.capture", { tabId: tab })).ok, true);
    assert.equal(markers.get(tab), true);
    assert.equal((await request("browser.release")).ok, true);
    assert.equal(markers.get(tab), false);
    assert.equal((await request("browser.capture", { tabId: tab })).ok, true);
    assert.equal(markers.get(tab), true);
    native.onDisconnect.emit();
    await wait(() => markers.get(tab) === false && !attached.has(tab));
  } finally {
    globalThis.setInterval = originalInterval;
    if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator);
    else delete globalThis.navigator;
  }
});

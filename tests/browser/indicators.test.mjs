import assert from "node:assert/strict";
import { test } from "node:test";
import { TabIndicators } from "../../providers/chrome-extension/indicators.js";

function fixture() {
  const tabs = new Map([[1, { id: 1, windowId: 7, groupId: -1, url: "about:blank" }],
    [2, { id: 2, windowId: 7, groupId: -1, url: "about:blank" }]]);
  const groups = new Map();
  const rendered = new Map();
  const detached = [];
  const stored = {};
  let next = 100;
  globalThis.chrome = {
    storage: { local: {
      async get() { return stored; },
      async set(value) { Object.assign(stored, structuredClone(value)); },
      async remove(key) { delete stored[key]; },
    } },
    debugger: { async attach() {}, async detach({ tabId }) { detached.push(tabId); } },
    tabs: {
      async get(id) { assert.ok(tabs.has(id)); return tabs.get(id); },
      async group(params) {
        const id = params.groupId ?? next++;
        if (!groups.has(id)) groups.set(id, { id, windowId: params.createProperties.windowId });
        for (const tab of params.tabIds) tabs.get(tab).groupId = id;
        return id;
      },
      async ungroup(ids) { for (const id of ids) tabs.get(id).groupId = -1; },
    },
    tabGroups: {
      async get(id) { assert.ok(groups.has(id)); return groups.get(id); },
      async update(id, value) { Object.assign(groups.get(id), value); },
    },
  };
  const indicators = new TabIndicators(async (tab, method, params) => {
    if (method === "Page.getFrameTree") return { frameTree: { frame: { id: String(tab) } } };
    if (method === "Page.createIsolatedWorld") {
      assert.equal(params.worldName, "machine-control-indicator");
      return { executionContextId: tab };
    }
    assert.equal(method, "Runtime.callFunctionOn");
    rendered.set(tab, params.arguments[0].value);
    return { result: { value: { visible: params.arguments[0].value !== null } } };
  });
  return { indicators, tabs, groups, rendered, stored, detached };
}

test("new tabs share a named group; existing tabs retain user grouping", async () => {
  const f = fixture();
  await f.indicators.track(1, true);
  await f.indicators.track(2, true);
  assert.equal(f.tabs.get(1).groupId, f.tabs.get(2).groupId);
  assert.equal(f.groups.get(f.tabs.get(1).groupId).title, "Machine Control");
  assert.equal(f.groups.get(f.tabs.get(1).groupId).color, "blue");
  assert.equal(f.indicators.status(1), "active");
  const group = f.tabs.get(1).groupId;
  f.tabs.set(3, { id: 3, windowId: 7, groupId: 44, url: "about:blank" });
  await f.indicators.track(3);
  assert.equal(f.tabs.get(3).groupId, 44);
  await f.indicators.releaseAll();
  assert.equal(f.tabs.get(1).groupId, -1);
  assert.equal(f.tabs.get(3).groupId, 44);
  assert.equal(f.rendered.get(1), null);
  assert.equal(f.indicators.status(1), "none");
  assert.equal(f.groups.get(group).title, "Machine Control");
});

test("release preserves renamed groups and a person's added tab", async () => {
  const f = fixture();
  await f.indicators.track(1, true);
  const id = f.tabs.get(1).groupId;
  f.tabs.get(2).groupId = id;
  await f.indicators.release(1);
  assert.equal(f.tabs.get(2).groupId, id);
  await f.indicators.track(1, true);
  f.groups.get(f.tabs.get(1).groupId).title = "My work";
  await f.indicators.releaseAll();
  assert.notEqual(f.tabs.get(1).groupId, -1);
});

test("pinned tabs and groups in another window are never moved", async () => {
  const f = fixture();
  await f.indicators.track(1, true);
  f.tabs.get(2).windowId = 8;
  await f.indicators.track(2, true);
  assert.notEqual(f.tabs.get(1).groupId, f.tabs.get(2).groupId);
  f.tabs.set(3, { id: 3, windowId: 7, groupId: -1, pinned: true, url: "about:blank" });
  await f.indicators.track(3, true);
  assert.equal(f.tabs.get(3).groupId, -1);
});

test("revocation fences an in-flight icon fetch and queued heartbeat", async () => {
  const f = fixture();
  let finish;
  let started;
  const ready = new Promise((resolve) => { started = resolve; });
  f.indicators.icon = () => { started(); return new Promise((resolve) => { finish = resolve; }); };
  const track = f.indicators.track(1, true);
  await ready;
  const heartbeat = f.indicators.heartbeat();
  const release = f.indicators.releaseAll();
  finish("missing");
  await Promise.all([track, heartbeat, release]);
  assert.equal(f.rendered.get(1), null);
  assert.equal(f.tabs.get(1).groupId, -1);
  assert.equal(f.indicators.status(1), "none");
});

test("fresh-worker recovery restores recorded state without granting control", async () => {
  const f = fixture();
  await f.indicators.track(1, true);
  const fresh = new TabIndicators(f.indicators.command);
  await fresh.recover();
  assert.equal(f.rendered.get(1), null);
  assert.equal(f.tabs.get(1).groupId, -1);
  assert.deepEqual(f.detached, [1]);
  assert.equal(fresh.status(1), "none");
  assert.equal(f.stored.controlledTabs, undefined);
});

test("unavailable page marker reports the omission without losing group cleanup", async () => {
  const f = fixture();
  f.indicators.command = async () => { throw new Error("restricted page"); };
  await f.indicators.track(1, true);
  assert.equal(f.indicators.status(1), "unavailable");
  await f.indicators.releaseAll();
  assert.equal(f.tabs.get(1).groupId, -1);
});

test("moving an owned group to another window preserves the user's move", async () => {
  const f = fixture();
  await f.indicators.track(1, true);
  const group = f.tabs.get(1).groupId;
  f.tabs.get(1).windowId = 9;
  f.groups.get(group).windowId = 9;
  await f.indicators.releaseAll();
  assert.equal(f.tabs.get(1).groupId, group);
});

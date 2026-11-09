import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const tick = () => new Promise(resolve => setImmediate(resolve));

test("late tab metadata cannot repaint access withdrawn by a newer state", async () => {
  class Element {
    constructor() { this.children = []; this.hidden = false; this.classList = { toggle() {} }; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener() {}
  }
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  let receive, finishMetadata;
  const heldMetadata = new Promise(resolve => { finishMetadata = resolve; });
  const port = { onMessage: { addListener(fn) { receive = fn; } },
    onDisconnect: { addListener() {} }, postMessage() {} };
  const context = vm.createContext({ URL, URLSearchParams, Date, Promise,
    navigator: { platform: "fixture" }, location: { search: "" }, setTimeout,
    document: { body: new Element(), activeElement: null,
      getElementById: element, createElement: () => new Element() },
    chrome: { runtime: { getManifest: () => ({ version: "fixture" }), connect: () => port },
      tabs: { get: () => heldMetadata, onUpdated: { addListener() {} } } },
  });
  vm.runInContext(await readFile(new URL("../../providers/chrome-extension/panel.js", import.meta.url), "utf8"), context);
  const state = { type: "state", connected: true, granted: true, devtools: false,
    profileAware: false, controlledTabs: [1],
    activity: [{ operation: "browser.click", tabId: 1, count: 1, ok: true, at: 0 }] };
  receive(state);
  receive({ ...state, granted: false, controlledTabs: [], activity: [] });
  await tick();
  assert.equal(element("no-tabs").hidden, false);
  finishMetadata({ id: 1, title: "Previously controlled", url: "about:blank" });
  await tick();
  assert.equal(element("no-tabs").hidden, false);
  assert.equal(element("tabs").children.length, 0);
  assert.equal(element("activity").children.length, 0);
  assert.equal(element("access-summary").textContent, "No agent has browser access right now.");
});

test("controlled tabs show the claim and agent that attached them", async () => {
  class Element {
    constructor() { this.children = []; this.hidden = false; this.classList = { toggle() {} }; }
    append(...nodes) { this.children.push(...nodes); }
    replaceChildren(...nodes) { this.children = nodes; }
    addEventListener() {}
  }
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, new Element());
    return elements.get(id);
  };
  let receive;
  const port = { onMessage: { addListener(fn) { receive = fn; } },
    onDisconnect: { addListener() {} }, postMessage() {} };
  const context = vm.createContext({ URL, URLSearchParams, Date, Promise,
    navigator: { platform: "fixture" }, location: { search: "" }, setTimeout,
    document: { body: new Element(), activeElement: null,
      getElementById: element, createElement: () => new Element() },
    chrome: { runtime: { getManifest: () => ({ version: "fixture" }), connect: () => port },
      tabs: { get: async id => ({ id, title: `Tab ${id}`, url: "https://example.test/" }), onUpdated: { addListener() {} } } },
  });
  vm.runInContext(await readFile(new URL("../../providers/chrome-extension/panel.js", import.meta.url), "utf8"), context);
  const claimId = `c-${"a".repeat(24)}`;
  receive({ type: "state", connected: true, granted: true, devtools: false, profileAware: false,
    controlledTabs: [1, 2, 3], activity: [],
    tabOwners: { 1: { claimId, sessionRef: "f00dcafe-1234-5678", claimEnded: false, releaseAt: 0 },
      3: { claimId, sessionRef: null, claimEnded: true, releaseAt: null } } });
  await tick(); await tick();
  const ownerLine = item => item.children[1].children[2];
  const [owned, unowned, ended] = element("tabs").children;
  assert.match(ownerLine(owned).textContent, new RegExp(`^Claim ${claimId} · agent f00dcafe · until `));
  assert.equal(ownerLine(owned).title, "Agent session f00dcafe-1234-5678");
  assert.equal(ownerLine(unowned).textContent, "No claim; held until release or Stop");
  assert.equal(ownerLine(ended).textContent, `Claim ${claimId} · claim ended; releasing`);
});

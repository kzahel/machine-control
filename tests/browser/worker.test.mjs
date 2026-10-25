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
  let releaseHeld;
  let heldStarted = false;
  let holdQuads = false;
  let releaseQuads;
  let presses = 0;
  let failDetach = false;
  let holdLookup = false;
  let releaseLookup;
  let holdAttach = false;
  let releaseAttach;
  let failAttach = false;
  let failPageEnable = false;
  let holdPageEnable = false;
  let releasePageEnable;
  let declineDialog = false;
  let handledDialogs = 0;
  let dialogDuringDetach = null;
  let reportAbsent = false;
  const detachAttempts = new Map();
  let delayAttachEffect = false;
  let rejectAbsentDetaches = false;
  const heldAttachments = new Map();
  const inserted = [];
  const originalInterval = globalThis.setInterval;
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, "navigator");
  globalThis.setInterval = () => 0;
  Object.defineProperty(globalThis, "navigator", { value: { userAgent: "fixture" }, configurable: true });
  globalThis.chrome = {
    action: { setBadgeText() {}, setBadgeBackgroundColor() {}, setTitle() {} },
    runtime: { id: "fixture-extension", getManifest: () => ({ version: "fixture" }), connectNative: () => native,
      onStartup: event(), onInstalled: event(), onConnect: event() },
    alarms: { create() {}, onAlarm: event() },
    storage: { local: { async get() { return storage; },
      async set(value) { Object.assign(storage, structuredClone(value)); },
      async remove(key) { delete storage[key]; } } },
    tabs: {
      onCreated: event(), onUpdated: event(), onRemoved: event(),
      async query() { return [...tabs.values()]; },
      async get(id) { if (holdLookup) return new Promise(resolve => { releaseLookup = () => resolve(tabs.get(id)); }); return tabs.get(id); },
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
      async attach({ tabId }) {
        if (failAttach) throw new Error("Fixture attach refusal");
        assert.ok(!attached.has(tabId));
        const delayed = delayAttachEffect;
        if (!delayed) attached.add(tabId);
        if (holdAttach) await new Promise(resolve => {
          releaseAttach = () => { if (delayed) attached.add(tabId); heldAttachments.delete(tabId); resolve(); };
          heldAttachments.set(tabId, releaseAttach);
        });
        else if (delayed) attached.add(tabId);
      },
      async detach({ tabId }) {
        detachAttempts.set(tabId, (detachAttempts.get(tabId) || 0) + 1);
        if (dialogDuringDetach === tabId) {
          dialogDuringDetach = null;
          chrome.debugger.onEvent.emit({ tabId }, "Page.javascriptDialogOpening", { type:"beforeunload" });
        }
        if (reportAbsent || (rejectAbsentDetaches && !attached.has(tabId))) {
          attached.delete(tabId); throw new Error("Debugger is not attached to the tab with id: " + tabId);
        }
        if (failDetach) throw new Error("Fixture unconfirmed detach");
        attached.delete(tabId); chrome.debugger.onDetach.emit({ tabId });
      },
      async sendCommand({ tabId }, method, params) {
        assert.ok(attached.has(tabId));
        if (method === "Page.enable" && failPageEnable) throw new Error("Fixture Page refusal");
        if (method === "Page.enable" && holdPageEnable) return new Promise(resolve => { releasePageEnable = resolve; });
        if (method === "Page.handleJavaScriptDialog") {
          handledDialogs++;
          if (declineDialog) throw new Error("No dialog is showing");
          if (releasePageEnable) releasePageEnable({});
        }
        if (method === "Accessibility.getFullAXTree") return { nodes: [
          { backendDOMNodeId: 7, role: { value: "button" }, name: { value: "Fixture" } },
        ] };
        if (method === "DOM.getContentQuads") {
          const result = { quads: [[0, 0, 20, 0, 20, 20, 0, 20]] };
          if (holdQuads) return new Promise((resolve) => { releaseQuads = () => resolve(result); });
          return result;
        }
        if (method === "Input.dispatchMouseEvent" && params.type === "mousePressed") presses++;
        if (method === "Input.insertText") inserted.push(params.text);
        if (method === "Runtime.fixturePending") {
          heldStarted = true;
          return new Promise((resolve) => { releaseHeld = resolve; });
        }
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
    for (let i = 0; i < 500; i++) { const value = fn(); if (value) return value; await new Promise(resolve => setTimeout(resolve, 10)); }
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
    // The side panel receives read-only state from its own extension only.
    const panelPort = (id) => {
      const states = [];
      return { states, name: "panel", sender: { id }, onDisconnect: event(), onMessage: event(),
        postMessage(message) { states.push(message); } };
    };
    const panel = panelPort("fixture-extension");
    const foreign = panelPort("other-extension");
    chrome.runtime.onConnect.emit(panel);
    chrome.runtime.onConnect.emit(foreign);
    assert.equal(foreign.states.length, 0);
    assert.equal(panel.states.at(-1).connected, true);
    assert.equal(panel.states.at(-1).granted, true);
    assert.deepEqual(panel.states.at(-1).controlledTabs, [tab]);
    await request("browser.type", { tabId: tab, text: "private words" });
    await new Promise((resolve) => setTimeout(resolve, 80));
    const [typed] = panel.states.at(-1).activity;
    assert.equal(typed.operation, "browser.type");
    assert.equal(typed.detail, "13 characters");
    assert.equal(JSON.stringify(panel.states).includes("private words"), false);
    native.onMessage.emit({ type: "session.open", id: "browser-only", tabId: tab });
    await wait(() => replies.find((reply) => reply.type === "session.failed" && reply.id === "browser-only"));
    const oldReference = (await request("browser.snapshot", { tabId: tab })).data.elements[0].reference;
    // Same scopes with a new resident grant must clear prior control state.
    native.onMessage.emit({ type: "grant", browser: true, devtools: true, grantGeneration: "second" });
    await request("browser.tabs");
    assert.equal(markers.get(tab), false);
    assert.equal(tabs.get(tab).groupId, -1);
    assert.equal((await request("browser.click", { reference: oldReference })).errorCode, "stale_reference");
    const freshReference = (await request("browser.snapshot", { tabId: tab })).data.elements[0].reference;
    assert.equal((await request("browser.click", { reference: oldReference })).errorCode, "stale_reference");
    assert.equal((await request("browser.click", { reference: freshReference })).ok, true);
    assert.equal(presses, 1);
    // Revoke while geometry is pending. Neither the in-flight click nor a
    // request queued under its old grant may resume with fresh authority.
    holdQuads = true;
    const pendingClick = request("browser.click", { reference: freshReference });
    await wait(() => releaseQuads);
    const queuedType = request("browser.type", { tabId: tab, text: "old grant" });
    native.onMessage.emit({ type: "grant", browser: true, devtools: true, grantGeneration: "third" });
    releaseQuads();
    assert.equal((await pendingClick).errorCode, "approval_required");
    assert.equal((await queuedType).errorCode, "approval_required");
    assert.equal(presses, 1, "revoked click must not press after its geometry reply");
    assert.equal(inserted.includes("old grant"), false, "queued old-grant text must not be inserted");
    holdQuads = false;
    assert.equal((await request("browser.capture", { tabId: tab })).ok, true);
    // A hung ordinary command occupies only its tab. Recovery and another tab
    // must progress, and a dialog must cancel old queued input before delivery.
    const hung = request("browser.cdp", { tabId:tab, method:"Runtime.fixturePending" });
    await wait(() => heldStarted);
    const secondTab = (await request("browser.navigate", { newTab:true, url:"about:blank" })).data.tab.tabId;
    assert.equal((await request("browser.type", { tabId:secondTab, text:"other tab" })).ok, true);
    assert.equal((await request("browser.tabs")).data.tabs.length, 2);
    const staleText = request("browser.type", { tabId:tab, text:"abandoned dialog text" });
    await tick(); await tick();
    chrome.debugger.onEvent.emit({ tabId:tab }, "Page.javascriptDialogOpening", { type:"beforeunload" });
    const interrupted = await hung;
    assert.equal(interrupted.errorCode, "dialog_open");
    assert.equal(interrupted.delivery, "unknown");
    assert.equal((await staleText).delivery, "refused");
    const dialog = (await request("browser.dialog", { tabId:tab })).data.dialog;
    assert.equal(dialog.type, "beforeunload");
    assert.equal((await request("browser.tabs")).data.tabs.find(item => item.tabId === tab).observedDialog.id, dialog.id);
    assert.equal((await request("browser.release")).errorCode, "dialog_open",
      "release must not abandon a dialog that Chrome will not give to a new session");
    assert.equal((await request("browser.dialog", { tabId:tab })).data.dialog.id, dialog.id);
    assert.equal((await request("browser.type", { tabId:secondTab, text:"dialog recovery remains independent" })).ok, true);
    holdLookup = true;
    const cancelledRecovery = request("browser.dialog", { tabId:tab, action:"dismiss", dialogId:dialog.id });
    const cancelledId = id;
    await wait(() => releaseLookup);
    native.onMessage.emit({ type:"cancel", id:cancelledId });
    holdLookup = false;
    releaseLookup();
    assert.equal((await cancelledRecovery).delivery, "refused");
    assert.equal((await request("browser.dialog", { tabId:tab })).data.dialog.id, dialog.id);
    assert.equal((await request("browser.dialog", { tabId:tab, action:"dismiss", dialogId:"old" })).errorCode, "stale_dialog");
    assert.equal((await request("browser.dialog", { tabId:tab, action:"dismiss", dialogId:dialog.id })).ok, true);
    releaseHeld({});
    await tick(); await tick();
    assert.equal(inserted.includes("abandoned dialog text"), false);
    heldStarted = false;
    native.onMessage.emit({ type: "session.open", id: "raw", tabId: tab });
    await wait(() => replies.find((reply) => reply.type === "session.opened" && reply.id === "raw"));
    native.onMessage.emit({ type:"session.command", id:"raw", cmdId:46, method:"Page.disable" });
    await wait(() => replies.find((reply) => reply.type === "session.result" && reply.cmdId === 46 && reply.error));
    native.onMessage.emit({ type: "session.command", id: "raw", cmdId: 42, method: "Runtime.enable", params: {} });
    await wait(() => replies.find((reply) => reply.type === "session.result" && reply.cmdId === 42 && reply.result));
    chrome.debugger.onEvent.emit({ tabId: tab }, "Runtime.consoleAPICalled", { type: "log" });
    assert.ok(replies.find((reply) => reply.type === "session.event" && reply.id === "raw" && reply.method === "Runtime.consoleAPICalled"));
    native.onMessage.emit({ type: "session.command", id: "raw", cmdId: 44, method: "Runtime.fixturePending" });
    await wait(() => heldStarted);
    native.onMessage.emit({ type: "session.command", id: "raw", cmdId: 45, method: "Runtime.enable" });
    await wait(() => replies.find((reply) => reply.type === "session.result" && reply.cmdId === 45));
    native.onMessage.emit({ type: "session.close", id: "raw" });
    await wait(() => replies.find((reply) => reply.type === "session.closed" && reply.id === "raw"));
    releaseHeld({ privateLateResult: true });
    await tick(); await tick();
    assert.equal(replies.some((reply) => reply.type === "session.result" && reply.cmdId === 44), false);
    assert.equal((await request("browser.capture", { tabId: tab })).ok, true);
    assert.equal(markers.get(tab), true);
    assert.equal(tabs.get(tab).groupId, -1);
    native.onMessage.emit({ type: "grant", browser: false, devtools: false });
    native.onMessage.emit({ type: "session.command", id: "raw", cmdId: 43, method: "Runtime.enable" });
    await wait(() => replies.find((reply) => reply.type === "session.result" && reply.cmdId === 43 && reply.error));
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
    // Linux-style false/true grant publication and an explicit release share
    // one ordered cleanup barrier. New work cannot race an older detach.
    native.onMessage.emit({ type:"grant", browser:false, devtools:false, grantGeneration:"paired" });
    native.onMessage.emit({ type:"grant", browser:true, devtools:true, grantGeneration:"paired" });
    assert.equal((await request("browser.capture", { tabId:tab })).ok, true);
    chrome.debugger.onEvent.emit({ tabId:tab }, "Page.javascriptDialogOpening", { type:"alert", message:"Fixture alert" });
    assert.equal((await request("browser.dialog", { tabId:tab })).data.dialog.message, "Fixture alert");
    await chrome.debugger.detach({ tabId:tab });
    assert.equal((await request("browser.dialog", { tabId:tab })).data.dialog, null);
    assert.equal((await request("browser.capture", { tabId:tab })).ok, true);
    failDetach = true;
    const incompleteRelease = await request("browser.release");
    assert.equal(incompleteRelease.ok, true);
    assert.ok(incompleteRelease.health.blockedTabs > 0);
    assert.equal(incompleteRelease.data.released, false);
    assert.equal((await request("browser.capture", { tabId:tab })).errorCode, "browser_recovery_pending");
    failDetach = false;
    assert.equal((await request("browser.release")).ok, true);
    assert.equal((await request("browser.capture", { tabId:tab })).ok, true);
    const streamOnlyTab = await chrome.tabs.create({ url:"about:blank" });
    native.onMessage.emit({ type:"session.open", id:"modal-stream", tabId:streamOnlyTab.id });
    await wait(() => replies.find(reply => reply.type === "session.opened" && reply.id === "modal-stream"));
    chrome.debugger.onEvent.emit({ tabId:streamOnlyTab.id }, "Page.javascriptDialogOpening", { type:"alert" });
    const streamDialog = (await request("browser.tabs")).data.tabs.find(item => item.tabId === streamOnlyTab.id).observedDialog;
    native.onMessage.emit({ type:"session.close", id:"modal-stream" });
    await wait(() => replies.find(reply => reply.type === "session.closed" && reply.id === "modal-stream"));
    await new Promise(resolve => setTimeout(resolve, 50));
    assert.equal(attached.has(streamOnlyTab.id), true, "stream close must retain an observed dialog for explicit handling");
    assert.equal(detachAttempts.has(streamOnlyTab.id), false);
    assert.equal((await request("browser.dialog", { tabId:streamOnlyTab.id, action:"dismiss", dialogId:streamDialog.id })).ok, true);
    assert.equal((await request("browser.release")).ok, true);
    const uncertainTab = await chrome.tabs.create({ url:"about:blank" });
    native.onMessage.emit({ type:"session.open", id:"uncertain-stream", tabId:uncertainTab.id });
    await wait(() => replies.find(reply => reply.type === "session.opened" && reply.id === "uncertain-stream"));
    failDetach = true; dialogDuringDetach = uncertainTab.id;
    native.onMessage.emit({ type:"session.close", id:"uncertain-stream" });
    await wait(() => detachAttempts.has(uncertainTab.id)); await tick();
    assert.equal((await request("browser.dialog", { tabId:uncertainTab.id })).errorCode, "browser_recovery_pending");
    failDetach = false;
    const abandoned = await request("browser.release");
    assert.equal(abandoned.ok, true);
    assert.equal(abandoned.data.released, true);
    assert.deepEqual(abandoned.data.abandonedDialogs, [uncertainTab.id]);
    assert.equal(attached.has(uncertainTab.id), false, "uncertain detach and a dialog must not form a release cycle");
    const absentTab = await chrome.tabs.create({ url:"about:blank" });
    assert.equal((await request("browser.capture", { tabId:absentTab.id })).ok, true);
    reportAbsent = true;
    assert.equal((await request("browser.release")).data.released, true);
    reportAbsent = false;
    assert.equal((await request("browser.capture", { tabId:absentTab.id })).ok, true, "definite debugger absence completes recovery even without an event");
    const refusedTab = await chrome.tabs.create({ url:"about:blank" });
    failAttach = true;
    assert.equal((await request("browser.capture", { tabId:refusedTab.id })).errorCode, "debugger_attach_failed");
    failAttach = false;
    failPageEnable = true;
    assert.equal((await request("browser.capture", { tabId:refusedTab.id })).errorCode, "browser_observer_unavailable");
    failPageEnable = false;
    assert.equal((await request("browser.type", { tabId:refusedTab.id, text:"unobserved" })).ok, false);
    assert.equal(inserted.includes("unobserved"), false);
    assert.equal((await request("browser.release")).ok, true);
    assert.equal((await request("browser.capture", { tabId:refusedTab.id })).ok, true);
    const modalTab = await chrome.tabs.create({ url:"about:blank" });
    holdPageEnable = true;
    const unobserved = await request("browser.dialog", { tabId:modalTab.id });
    assert.equal(unobserved.ok, true);
    assert.equal(unobserved.data.observerState, "pending");
    assert.equal(unobserved.data.state, "not_observed");
    assert.ok(unobserved.health.blockedTabs > 0, "pending event readiness must appear in sanitized route health");
    assert.equal((await request("browser.type", { tabId:modalTab.id, text:"blocked modal" })).errorCode, "browser_observer_unavailable");
    assert.equal(inserted.includes("blocked modal"), false);
    holdPageEnable = false;
    assert.equal((await request("browser.cdp", { tabId:modalTab.id, method:"Page.handleJavaScriptDialog", params:{accept:false} })).ok, true,
      "explicit modal recovery must not wait for the Page.enable command it unblocks");
    assert.equal((await request("browser.capture", { tabId:modalTab.id })).ok, true);
    const inaccessibleModal = await chrome.tabs.create({ url:"about:blank" });
    holdPageEnable = true;
    const beforeHandling = handledDialogs;
    assert.equal((await request("browser.dialog", { tabId:inaccessibleModal.id })).data.observerState, "pending");
    assert.equal(handledDialogs, beforeHandling, "dialog discovery never accepts or dismisses implicitly");
    declineDialog = true;
    assert.equal((await request("browser.cdp", { tabId:inaccessibleModal.id, method:"Page.handleJavaScriptDialog", params:{accept:false} })).errorCode, "stale_dialog");
    assert.equal((await request("browser.dialog", { tabId:inaccessibleModal.id })).data.observerState, "pending");
    assert.equal((await request("browser.navigate", { tabId:inaccessibleModal.id, url:"https://example.invalid" })).errorCode, "browser_observer_unavailable");
    assert.equal(tabs.get(inaccessibleModal.id).url, "about:blank", "unobserved route must refuse navigation before the effect");
    assert.equal(handledDialogs, beforeHandling + 1, "only the explicit handling request is dispatched");
    assert.equal((await request("browser.release")).ok, true);
    holdPageEnable = false; declineDialog = false;
    const lateObserverTab = await chrome.tabs.create({ url:"about:blank" });
    holdPageEnable = true;
    assert.equal((await request("browser.dialog", { tabId:lateObserverTab.id })).data.observerState, "pending");
    const releaseOldObserver = releasePageEnable;
    assert.equal((await request("browser.release")).ok, true);
    holdPageEnable = false;
    assert.equal((await request("browser.capture", { tabId:lateObserverTab.id })).ok, true);
    releaseOldObserver({}); await tick(); await tick();
    assert.equal((await request("browser.dialog", { tabId:lateObserverTab.id })).data.observerState, "ready");
    const attachingTab = await chrome.tabs.create({ url:"about:blank" });
    holdAttach = true;
    const oldAttach = request("browser.capture", { tabId:attachingTab.id });
    await wait(() => releaseAttach);
    assert.equal((await request("browser.release")).ok, true);
    assert.equal((await oldAttach).ok, false);
    holdAttach = false;
    assert.equal((await request("browser.capture", { tabId:attachingTab.id })).errorCode, "browser_recovery_pending");
    releaseAttach();
    await new Promise(resolve => setTimeout(resolve, 30));
    assert.equal((await request("browser.capture", { tabId:attachingTab.id })).ok, true);
    assert.equal(attached.has(attachingTab.id), true, "a fresh route waits until every old attachment callback is retired");
    assert.equal(markers.get(attachingTab.id), true);
    const delayedTabs = await Promise.all(Array.from({length:8}, () => chrome.tabs.create({url:"about:blank"})));
    holdAttach = true; delayAttachEffect = true; rejectAbsentDetaches = true;
    const delayedResults = await Promise.all(delayedTabs.map(item => request("browser.capture", {tabId:item.id})));
    assert.equal(delayedResults.every(reply => !reply.ok), true);
    const releaseBeforeEffect = await request("browser.release");
    assert.equal(releaseBeforeEffect.data.released, false);
    assert.equal(releaseBeforeEffect.data.pendingAttachments.length, 8,
      "not-attached is not final while the raw attach can still take effect");
    assert.equal((await request("browser.capture", {tabId:delayedTabs[0].id})).errorCode, "browser_recovery_pending");
    const capacityTab = await chrome.tabs.create({url:"about:blank"});
    assert.equal((await request("browser.capture", {tabId:capacityTab.id})).errorCode, "browser_busy");
    holdAttach = false; delayAttachEffect = false;
    for (const resolve of [...heldAttachments.values()]) resolve();
    await new Promise(resolve => setTimeout(resolve, 40));
    assert.equal(delayedTabs.every(item => !attached.has(item.id)), true, "late attachment effects must be detached before permitting new work");
    assert.equal((await request("browser.capture", {tabId:capacityTab.id})).ok, true);
    assert.equal((await request("browser.capture", {tabId:attachingTab.id})).ok, true);
    chrome.debugger.onEvent.emit({ tabId:attachingTab.id }, "Page.javascriptDialogOpening", { type:"beforeunload" });
    native.onMessage.emit({ type:"grant", browser:false, devtools:false, grantGeneration:"stopped" });
    await wait(() => !attached.has(attachingTab.id));
    assert.equal(attached.has(attachingTab.id), false, "authority loss detaches even with an observed dialog");
    native.onDisconnect.emit();
    await wait(() => markers.get(tab) === false && !attached.has(tab));
  } finally {
    globalThis.setInterval = originalInterval;
    if (originalNavigator) Object.defineProperty(globalThis, "navigator", originalNavigator);
    else delete globalThis.navigator;
  }
});

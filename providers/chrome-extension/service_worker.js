// Machine Control browser provider. The resident on this computer owns
// authorization: it forwards a request only while a person has granted the
// browser scope, and tells this worker when that grant ends.
import { TabIndicators } from "./indicators.js";
import { BrowserCdp } from "./browser_cdp.js";
import { RequestQueue, bounded } from "./requests.js";
import { presentationParams } from "./presentation.js";

const HOST = "org.machine_control.browser";
const PROTOCOL_VERSION = 1;
const INTERACTIVE_ROLES = new Set([
  "button", "link", "textbox", "searchbox", "combobox", "checkbox", "radio",
  "menuitem", "menuitemcheckbox", "menuitemradio", "tab", "switch", "slider",
  "option", "listbox", "spinbutton", "treeitem",
]);
const SKIPPED_ROLES = new Set(["InlineTextBox", "none", "generic", "LineBreak"]);
const KEYS = {
  Enter: { code: "Enter", keyCode: 13, text: "\r" },
  Tab: { code: "Tab", keyCode: 9 },
  Escape: { code: "Escape", keyCode: 27 },
  Backspace: { code: "Backspace", keyCode: 8 },
  Delete: { code: "Delete", keyCode: 46 },
  Home: { code: "Home", keyCode: 36 },
  End: { code: "End", keyCode: 35 },
  PageUp: { code: "PageUp", keyCode: 33 },
  PageDown: { code: "PageDown", keyCode: 34 },
  ArrowUp: { code: "ArrowUp", keyCode: 38 },
  ArrowDown: { code: "ArrowDown", keyCode: 40 },
  ArrowLeft: { code: "ArrowLeft", keyCode: 37 },
  ArrowRight: { code: "ArrowRight", keyCode: 39 },
};
// Common names an agent might use for the keys above.
const KEY_ALIASES = {
  return: "Enter", enter: "Enter", tab: "Tab", esc: "Escape", escape: "Escape",
  backspace: "Backspace", back: "Backspace", del: "Delete", delete: "Delete",
  home: "Home", end: "End", pageup: "PageUp", pagedown: "PageDown",
  up: "ArrowUp", down: "ArrowDown", left: "ArrowLeft", right: "ArrowRight",
  arrowup: "ArrowUp", arrowdown: "ArrowDown", arrowleft: "ArrowLeft", arrowright: "ArrowRight",
};

let port = null;
let granted = false;
let devtools = false;
let lastDisconnect = "";
let retryDelayMs = 1000;
let retryTimer = null;
const attached = new Set();
const ordinaryTabs = new Set();
const unconfirmedDetaches = new Set();
const generations = new Map();
let referenceEpoch = crypto.randomUUID();
let authorityGeneration = 0;
const dialogs = new Map();
const blockedTabs = new Map();
const recoveries = new Map();
const requests = new RequestQueue({ abandoned:(context, code) => {
  if (context.tabId != null) blockedTabs.set(context.tabId, code);
} });
let grantGeneration = null;
const attaching = new Map();
const attachmentOwners = new Map();
const pageObservers = new Map();
const pendingAttachments = new Map();
const virtualFocus = new Map();
const unconfirmedFocusReset = new Set();
function providerCommand(target, method, params = {}) {
  const owner = attachmentOwners.get(target.tabId);
  if (method === "Emulation.setFocusEmulationEnabled" && params.enabled === true)
    virtualFocus.set(target.tabId, owner);
  return chrome.debugger.sendCommand(target, method, params).then(result => {
    if (method === "Emulation.setFocusEmulationEnabled" && params.enabled === false
        && attachmentOwners.get(target.tabId) === owner) {
      virtualFocus.delete(target.tabId);
      unconfirmedFocusReset.delete(target.tabId);
    }
    return result;
  });
}
const indicators = new TabIndicators((tabId, method, params = {}) =>
  chrome.debugger.sendCommand({ tabId }, method, params));
const streaming = new BrowserCdp({ chrome, ensureAttached,
  sendCommand:providerCommand,
  releaseTab: async (tabId) => {
    if (streaming.usesTab(tabId) || ordinaryTabs.has(tabId) || requests.lanes.has(tabId) || dialogs.has(tabId)) return;
    const token = attachmentOwners.get(tabId);
    const decoration = indicators.release(tabId);
    await bounded(() => decoration, 750).catch(() => {});
    if (dialogs.has(tabId)) return;
    await detachAttachment(tabId, token);
  },
  trackNewTab: (tabId) => ensureAttached(tabId, true),
  authority: () => devtools && port ? `${grantGeneration}:${authorityGeneration}` : null,
  post: (frame) => port?.postMessage(frame),
});
const initialized = indicators.recover();
let disconnectCleanup = Promise.resolve();


class ProviderError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

// The native host exits whenever the Machine Control app restarts, updates,
// or is not running. That is expected: record why and reconnect with
// backoff; the alarm below is the fallback if this worker was suspended.
function scheduleReconnect() {
  clearTimeout(retryTimer);
  retryTimer = setTimeout(connect, retryDelayMs);
  retryDelayMs = Math.min(retryDelayMs * 2, 60000);
}

async function connect() {
  await initialized;
  await disconnectCleanup;
  if (port) return;
  clearTimeout(retryTimer);
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (error) {
    port = null;
    lastDisconnect = String(error.message || error);
    updateBadge();
    scheduleReconnect();
    return;
  }
  const connection = port;
  port.onMessage.addListener((message) => {
    if (port !== connection) return;
    // Any message means the resident accepted this connection.
    retryDelayMs = 1000;
    lastDisconnect = "";
    // Authority changes and recovery never queue behind page work.
    if (message?.type === "grant") {
      const changed = (grantGeneration !== null && typeof message.grantGeneration === "string"
        && grantGeneration !== message.grantGeneration)
        || granted !== (message.browser === true) || devtools !== (message.devtools === true);
      if (typeof message.grantGeneration === "string") grantGeneration = message.grantGeneration;
      if (changed) disconnectCleanup = detachAll();
      granted = message.browser === true;
      devtools = message.devtools === true;
      if (!devtools) streaming.closeAll("devtools_grant_ended").catch(() => {});
      updateBadge();
      return;
    }
    if (message?.type === "cancel") {
      requests.cancel(message.id);
      const recovery = recoveries.get(message.id);
      if (recovery) recovery.cancelled = true;
      return;
    }
    onResidentMessage(message, connection).catch(() => {});
  });
  port.onDisconnect.addListener(() => {
    if (port !== connection) return;
    // Reading lastError marks it handled, so Chrome does not report it.
    lastDisconnect = chrome.runtime.lastError?.message || "disconnected";
    port = null;
    granted = false;
    devtools = false;
    authorityGeneration += 1;
    grantGeneration = null;
    disconnectCleanup = detachAll();
    updateBadge();
    scheduleReconnect();
  });
  port.postMessage({
    type: "hello",
    protocolVersion: PROTOCOL_VERSION,
    extensionVersion: chrome.runtime.getManifest().version,
    userAgent: navigator.userAgent,
  });
  updateBadge();
}

// The side panel is a read-only view of connection, access, controlled tabs
// and recent operations. It holds no authority: the resident grants and ends
// access. Activity stays in this worker's memory and omits typed text,
// scripts, CDP parameters and page content.
const ACTIVITY_LIMIT = 200;
const activity = [];
const panels = new Set();
let panelTimer = null;

function panelState() {
  return {
    type: "state", connected: port !== null, lastDisconnect, granted, devtools,
    controlledTabs: [...attached], streams: streaming.sessions.size, activity,
  };
}

function notifyPanels() {
  if (!panels.size || panelTimer) return;
  panelTimer = setTimeout(() => {
    panelTimer = null;
    const state = panelState();
    for (const panel of panels) panel.postMessage(state);
  }, 50);
}

function activityDetail(operation, params, data) {
  switch (operation) {
    case "browser.navigate":
      try { return new URL(params.url).host || params.url; } catch { return ""; }
    case "browser.type": return `${String(params.text || "").length} characters`;
    case "browser.key": return String(params.key || "");
    case "browser.upload": return `${Array.isArray(params.files) ? params.files.length : 0} file(s)`;
    case "browser.cdp": return typeof params.method === "string" ? params.method : "";
    case "browser.tabs": return `${data?.tabs?.length ?? 0} tabs`;
    default: return "";
  }
}

function recordActivity(operation, params, reply, startedAt) {
  const tabId = reply.data?.tabId ?? reply.data?.tab?.tabId ?? (Number.isInteger(params.tabId) ? params.tabId : null);
  const entry = {
    at: startedAt, operation, tabId, ok: reply.ok === true, errorCode: reply.errorCode || "",
    detail: activityDetail(operation, params, reply.data), ms: Date.now() - startedAt, count: 1,
  };
  const last = activity[0];
  if (last && last.operation === entry.operation && last.tabId === entry.tabId && last.ok === entry.ok
      && last.detail === entry.detail && entry.at - last.at < 60000) {
    last.count += 1;
    last.at = entry.at;
    last.ms = entry.ms;
  } else {
    activity.unshift(entry);
    activity.length = Math.min(activity.length, ACTIVITY_LIMIT);
  }
  notifyPanels();
}

chrome.runtime.onConnect.addListener((panel) => {
  if (panel.name !== "panel" || panel.sender?.id !== chrome.runtime.id) return;
  panels.add(panel);
  panel.onDisconnect.addListener(() => panels.delete(panel));
  panel.onMessage.addListener((message) => {
    if (message?.type === "clearActivity") {
      activity.length = 0;
      notifyPanels();
    }
  });
  panel.postMessage(panelState());
});

function updateBadge() {
  notifyPanels();
  const text = !port ? "!" : devtools ? "DEV" : granted ? "ON" : "";
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color: granted ? "#c62828" : "#757575" });
  chrome.action.setTitle({
    title: !port ? `Machine Control: not connected to the app (${lastDisconnect || "starting"}); retrying`
      : devtools ? "Machine Control: an agent has full DevTools access"
      : granted ? "Machine Control: an agent may control Chrome"
        : "Machine Control: no browser access granted",
  });
}

async function onResidentMessage(message, connection) {
  if (message?.type === "session.open") {
    const startedAt = Date.now();
    const authority = authorityGeneration;
    try {
      await disconnectCleanup;
      if (port !== connection || authority !== authorityGeneration) throw new ProviderError("approval_required", "Browser access changed before session attachment");
      await streaming.open(message.id, message.tabId);
      port?.postMessage({ type: "session.opened", id: message.id });
      recordActivity("session.open", { tabId: message.tabId }, { ok: true }, startedAt);
    } catch (error) {
      recordActivity("session.open", { tabId: message.tabId }, { ok: false, errorCode: "session_failed" }, startedAt);
      port?.postMessage({ type: "session.failed", id: message.id, message: String(error.message || error) });
    }
    return;
  }
  if (message?.type === "session.command") {
    // A CDP awaitPromise must not hold the resident queue: close/revocation
    // and other correlated commands need to progress while it is pending.
    streaming.command(message).catch(() => {});
    return;
  }
  if (message?.type === "session.close") return streaming.close(message.id, "closed");
  if (message?.type !== "request") return;
  const reply = { type: "response", id: message.id };
  const startedAt = Date.now();
  const authority = authorityGeneration;
  const check = () => {
    if (port !== connection || authority !== authorityGeneration || (!granted && !devtools))
      throw new ProviderError("approval_required", "Browser access changed; issue a fresh request");
  };
  const params = { ...(message.params || {}) };
  const recovery = ["browser.tabs", "browser.release", "browser.dialog"].includes(message.operation)
    || (message.operation === "browser.cdp" && params.method === "Page.handleJavaScriptDialog");
  try {
    if (recovery) {
      if (recoveries.has(message.id) || recoveries.size >= 8) throw new ProviderError("browser_busy", "Browser recovery capacity exceeded");
      const budget = Number.isFinite(message.timeoutMs) ? Math.min(5000, Math.max(100, message.timeoutMs)) : 5000;
      const deadline = Date.now() + budget;
      const context = { dispatched:false, cancelled:false,
        check() {
          check();
          if (this.cancelled || Date.now() >= deadline) throw new ProviderError("browser_timeout", "Browser recovery expired");
        },
        dispatch() { this.check(); this.dispatched = true; },
      };
      recoveries.set(message.id, context);
      try {
        if (message.operation !== "browser.release") await disconnectCleanup;
        context.check();
        reply.data = await bounded(() => createOperations(context).perform(message.operation, params), budget);
        if (message.operation !== "browser.release") check();
      } catch (error) {
        context.cancelled = true;
        error.delivery = context.dispatched ? "unknown" : "refused";
        throw error;
      } finally { if (recoveries.get(message.id) === context) recoveries.delete(message.id); }
    } else {
      reply.data = await requests.submit(message.id, { check,
        timeoutMs:Number.isFinite(message.timeoutMs) ? Math.min(30000, Math.max(100, message.timeoutMs)) : 30000,
        prepare:async (context) => {
          await disconnectCleanup;
          context.check();
          const operations = createOperations(context);
          const key = await operations.prepare(message.operation, params);
          context.check();
          return key;
        },
        run:(context) => createOperations(context).perform(message.operation, params),
      });
    }
    reply.ok = true;
  } catch (error) {
    reply.ok = false;
    reply.errorCode = error.code || "browser_operation_failed";
    reply.message = String(error.message || error);
    reply.delivery = error.delivery || "refused";
    if (reply.delivery === "unknown") reply.uncertainty = "browser_command_may_have_executed";
  }
  reply.health = { blockedTabs:new Set([...blockedTabs.keys(), ...unconfirmedDetaches, ...pendingAttachments.keys(),
    ...[...pageObservers].filter(([, observer]) => !observer.ready).map(([tabId]) => tabId)]).size,
    openDialogs:dialogs.size };
  if (port === connection) connection.postMessage(reply);
  recordActivity(message.operation, message.params || {}, reply, startedAt);
}

// These closures carry one request's authority through every await. Never
// share mutable current-request authority between concurrent tabs.
function createOperations(context) {
function requireRequestAuthority() { context.check(); }
async function prepare(operation, params) {
  if (operation === "browser.navigate" && params.newTab === true) return "new_tabs";
  const tabId = params.reference ? (await resolveReference(params.reference)).tabId : (await resolveTab(params)).id;
  requireRequestAuthority();
  params.tabId = tabId; context.tabId = tabId;
  return tabId;
}
async function perform(operation, params) {
  requireRequestAuthority();
  if (!["browser.dialog", "browser.release", "browser.tabs"].includes(operation) &&
      !(operation === "browser.cdp" && params.method === "Page.handleJavaScriptDialog") &&
      context.tabId != null && (dialogs.has(context.tabId) || blockedTabs.has(context.tabId)))
    throw new ProviderError(dialogs.has(context.tabId) ? "dialog_open" : "browser_tab_blocked", "Inspect the dialog or release this browser route before continuing");
  switch (operation) {
    case "browser.tabs": return listTabs();
    case "browser.wait": return waitReady(params);
    case "browser.navigate": return navigate(params);
    case "browser.snapshot": return snapshot(params);
    case "browser.click": return click(params);
    case "browser.type": return type(params);
    case "browser.key": return key(params);
    case "browser.capture": return capture(params);
    case "browser.upload": return upload(params);
    case "browser.cdp": return cdp(params);
    case "browser.eval": return evaluate(params);
    case "browser.release": {
      const recoverable = [...dialogs.keys()].filter(tabId => attached.has(tabId)
        && attachmentOwners.has(tabId) && !unconfirmedDetaches.has(tabId));
      if (recoverable.length) throw new ProviderError("dialog_open",
        `Handle the observed dialog before releasing its debugger; inspect browser.dialog for tab(s) ${recoverable.slice(0,8).join(", ")}`);
      const abandonedDialogs = [...dialogs.keys()];
      context.dispatch(); await detachAll();
      return { released:unconfirmedDetaches.size === 0 && pendingAttachments.size === 0,
        unconfirmedDetaches:[...unconfirmedDetaches], pendingAttachments:[...pendingAttachments.keys()],
        ...(unconfirmedFocusReset.size ? { virtualFocusResetUnconfirmed:[...unconfirmedFocusReset] } : {}),
        ...(abandonedDialogs.length ? { abandonedDialogs } : {}) };
    }
    case "browser.dialog": return dialog(params);
    default: throw new ProviderError("unsupported_operation", `Unsupported ${operation}`);
  }
}

function tabJSON(tab) {
  return {
    tabId: tab.id, windowId: tab.windowId, active: tab.active,
    groupId: tab.groupId, controlIndicator: indicators.status(tab.id),
    virtualFocus:virtualFocus.has(tab.id) ? "enabled" : unconfirmedFocusReset.has(tab.id) ? "reset_unconfirmed" : "none",
    observedDialog:dialogs.has(tab.id) ? { id:dialogs.get(tab.id).id, type:dialogs.get(tab.id).type } : null,
    title: tab.title || "", url: tab.url || "", status: tab.status || "",
    // A discarded (memory-unloaded) tab reloads when the debugger attaches,
    // so it is not immediately ready to read or drive.
    discarded: tab.discarded === true,
  };
}

async function listTabs() {
  const tabs = await chrome.tabs.query({});
  return { tabs: tabs.map(tabJSON) };
}

async function resolveTab(params) {
  if (Number.isInteger(params.tabId)) {
    try {
      return await chrome.tabs.get(params.tabId);
    } catch {
      throw new ProviderError("tab_not_found", `Tab ${params.tabId} does not exist`);
    }
  }
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  if (!tab) throw new ProviderError("tab_not_found", "No active tab");
  return tab;
}

function checkURL(value) {
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new ProviderError("invalid_request", "url must be absolute");
  }
  if (!["http:", "https:"].includes(url.protocol) && value !== "about:blank") {
    throw new ProviderError("url_not_permitted", "Only http, https, and about:blank are permitted");
  }
  return url.href;
}

function waitForLoad(tabId, timeoutMs = 20000) {
  return new Promise((resolve) => {
    let finished = false;
    const timer = setTimeout(() => finish(false), timeoutMs);
    function listener(id, change) {
      if (id === tabId && change.status === "complete") finish(true);
    }
    function finish(loaded) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(loaded);
    }
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId).then((tab) => {
      if (tab.status === "complete") finish(true);
    }).catch(() => finish(false));
  });
}

async function navigate(params) {
  const url = checkURL(params.url);
  let tab;
  if (params.newTab === true) {
    requireRequestAuthority();
    context.dispatch();
    tab = await chrome.tabs.create({ url, active: params.active === true });
    context.tabId = tab.id;
    requireRequestAuthority();
    await ensureAttached(tab.id, true, true);
  } else {
    const current = await resolveTab(params);
    await ensureAttached(current.id, false, true);
    requireRequestAuthority();
    context.dispatch();
    tab = await chrome.tabs.update(current.id, { url });
  }
  context.tabId = tab.id;
  const loaded = await waitForLoad(tab.id);
  requireRequestAuthority();
  return { tab: tabJSON(await chrome.tabs.get(tab.id)), loaded };
}

async function send(tabId, method, params = {}, expectedDialogId) {
  requireRequestAuthority();
  const handlingDialog = method === "Page.handleJavaScriptDialog";
  if (method === "Page.disable") throw new ProviderError("operation_not_permitted", "Page events are required for dialog recovery");
  if (!handlingDialog && (dialogs.has(tabId) || blockedTabs.has(tabId)))
    throw new ProviderError(dialogs.has(tabId) ? "dialog_open" : "browser_tab_blocked",
      "Inspect browser dialog state or release browser control before retrying this tab");
  await ensureAttached(tabId, false, true, !handlingDialog);
  requireRequestAuthority();
  if (expectedDialogId !== undefined && dialogs.get(tabId)?.id !== expectedDialogId)
    throw new ProviderError("stale_dialog", "The observed dialog changed before dispatch; inspect again");
  // Chrome can acknowledge input on an inactive tab without delivering its
  // page effect. Emulate page focus instead of selecting a tab or raising its
  // window. Release explicitly resets this override. Refuse if unavailable; never
  // silently fall back to foreground or desktop input.
  if (method.startsWith("Input.")) {
    try { await send(tabId, "Emulation.setFocusEmulationEnabled", { enabled:true }); }
    catch (error) {
      if (error.code !== "cdp_command_failed") throw error;
      throw new ProviderError("background_input_unavailable", "Chrome could not prepare background input; foreground control was not attempted");
    }
    requireRequestAuthority();
  }
  try {
    context.dispatch();
    const result = await providerCommand({ tabId }, method, params);
    requireRequestAuthority();
    if (handlingDialog) { dialogs.delete(tabId); blockedTabs.delete(tabId); }
    return result;
  } catch (error) {
    if (handlingDialog && /no (?:javascript )?dialog|not (?:currently )?showing/i.test(String(error.message || error))) {
      dialogs.delete(tabId); blockedTabs.delete(tabId);
      throw new ProviderError("stale_dialog", "This debugger session could not handle the dialog; inspect again or use the browser UI");
    }
    if (error instanceof ProviderError) throw error;
    throw new ProviderError("cdp_command_failed", `${method}: ${error.message || error}`);
  }
}

function propertyMap(node) {
  const values = {};
  for (const property of node.properties || []) {
    values[property.name] = property.value?.value;
  }
  return values;
}

function clip(text, limit = 160) {
  const value = String(text ?? "").replace(/\s+/g, " ").trim();
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

async function snapshot(params) {
  const tab = await resolveTab(params);
  const limit = Math.min(Math.max(Number(params.maxElements) || 200, 1), 1000);
  const generation = (generations.get(tab.id) || 0) + 1;
  generations.set(tab.id, generation);
  const { nodes } = await send(tab.id, "Accessibility.getFullAXTree");
  const elements = [];
  let truncated = false;
  for (const node of nodes) {
    if (node.ignored || !node.backendDOMNodeId) continue;
    const role = node.role?.value || "";
    if (SKIPPED_ROLES.has(role)) continue;
    const name = clip(node.name?.value);
    const value = clip(node.value?.value);
    const interactive = INTERACTIVE_ROLES.has(role);
    if (!interactive && !name && !value) continue;
    if (params.interactiveOnly === true && !interactive) continue;
    if (elements.length >= limit) {
      truncated = true;
      break;
    }
    const properties = propertyMap(node);
    const element = {
      reference: `${tab.id}:${referenceEpoch}:${generation}:${node.backendDOMNodeId}`,
      role, name, interactive,
    };
    if (value) element.value = value;
    for (const field of ["focused", "disabled", "checked", "expanded", "selected"]) {
      if (properties[field] !== undefined) element[field] = properties[field];
    }
    elements.push(element);
  }
  return { tab: tabJSON(tab), generation, elements, truncated };
}

async function resolveReference(reference) {
  const match = /^(\d+):([a-f0-9-]{36}):(\d+):(\d+)$/.exec(String(reference || ""));
  if (!match) throw new ProviderError("invalid_reference", "reference is malformed");
  const [, rawTab, epoch, rawGeneration, rawNode] = match;
  const [tabId, generation, backendNodeId] = [rawTab, rawGeneration, rawNode].map(Number);
  if (epoch !== referenceEpoch || generations.get(tabId) !== generation) {
    throw new ProviderError("stale_reference", "The page changed since this snapshot; take a new one");
  }
  return { tabId, backendNodeId };
}

async function click(params) {
  const { tabId, backendNodeId } = await resolveReference(params.reference);
  await send(tabId, "DOM.scrollIntoViewIfNeeded", { backendNodeId });
  const { quads } = await send(tabId, "DOM.getContentQuads", { backendNodeId });
  if (!quads?.length) throw new ProviderError("element_not_visible", "Element has no visible box");
  const quad = quads[0];
  const x = (quad[0] + quad[2] + quad[4] + quad[6]) / 4;
  const y = (quad[1] + quad[3] + quad[5] + quad[7]) / 4;
  await send(tabId, "Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  await send(tabId, "Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await send(tabId, "Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  return { tabId, point: { x, y }, coordinateSpace: "viewport_css_pixels" };
}

async function type(params) {
  if (typeof params.text !== "string" || !params.text) {
    throw new ProviderError("invalid_request", "text is required");
  }
  let tabId;
  if (params.reference) {
    const resolved = await resolveReference(params.reference);
    tabId = resolved.tabId;
    await send(tabId, "DOM.focus", { backendNodeId: resolved.backendNodeId });
  } else {
    tabId = (await resolveTab(params)).id;
  }
  await send(tabId, "Input.insertText", { text: params.text });
  return { tabId, characters: params.text.length };
}

async function key(params) {
  const name = KEYS[params.key] ? params.key : KEY_ALIASES[String(params.key || "").toLowerCase()];
  const spec = KEYS[name];
  if (!spec) throw new ProviderError("invalid_request",
    `key must name one of: ${Object.keys(KEYS).join(", ")} (to type characters use browser type)`);
  const tabId = (await resolveTab(params)).id;
  const base = { key: name, code: spec.code, windowsVirtualKeyCode: spec.keyCode };
  await send(tabId, "Input.dispatchKeyEvent", { type: "keyDown", ...base, text: spec.text });
  await send(tabId, "Input.dispatchKeyEvent", { type: "keyUp", ...base });
  return { tabId, key: name };
}

// Waits until a tab finishes loading (and is no longer discarded), so a
// caller can act on a page that is ready rather than sleeping.
async function waitReady(params) {
  const timeoutMs = Math.min(Math.max(Number(params.timeoutMs) || 15000, 500), 60000);
  const deadline = Math.min(Date.now() + timeoutMs, (context.deadline || Infinity) - 50);
  let tab = await resolveTab(params);
  while (Date.now() < deadline) {
    requireRequestAuthority();
    tab = await chrome.tabs.get(tab.id);
    if (tab.status === "complete" && !tab.discarded) {
      return { tab: tabJSON(tab), ready: true };
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  return { tab: tabJSON(tab), ready: false };
}

function waitForEvent(tabId, method, timeoutMs) {
  return new Promise((resolve) => {
    const timer = setTimeout(() => finish(null), timeoutMs);
    function listener(source, eventMethod, params) {
      if (source.tabId === tabId && eventMethod === method) finish(params);
    }
    function finish(value) {
      clearTimeout(timer);
      chrome.debugger.onEvent.removeListener(listener);
      resolve(value);
    }
    chrome.debugger.onEvent.addListener(listener);
  });
}

// Attaches local files without the operating system's file dialog. A file
// input receives them directly; any other element is clicked while Chrome's
// file chooser is intercepted, and the chooser's input receives them. The
// resident has already checked that every path is a readable regular file.
async function upload(params) {
  const files = params.files;
  if (!Array.isArray(files) || files.length === 0) {
    throw new ProviderError("invalid_request", "files must list at least one path");
  }
  const { tabId, backendNodeId } = await resolveReference(params.reference);
  const { node } = await send(tabId, "DOM.describeNode", { backendNodeId });
  const attributes = node.attributes || [];
  const typeIndex = attributes.indexOf("type");
  const isFileInput = node.nodeName === "INPUT" && typeIndex >= 0 &&
    String(attributes[typeIndex + 1]).toLowerCase() === "file";
  if (isFileInput) {
    await setFiles(tabId, backendNodeId, files);
    return { tabId, files: files.length, route: "file_input" };
  }
  await send(tabId, "Page.enable");
  await send(tabId, "Page.setInterceptFileChooserDialog", { enabled: true });
  try {
    const opened = waitForEvent(tabId, "Page.fileChooserOpened", 8000);
    await click({ reference: params.reference });
    const chooser = await opened;
    if (!chooser?.backendNodeId) {
      throw new ProviderError("file_chooser_not_opened",
        "Clicking the element did not open a file chooser; snapshot the page for a file input or upload button");
    }
    if (chooser.mode === "selectSingle" && files.length > 1) {
      throw new ProviderError("file_chooser_single", "This file chooser accepts one file");
    }
    await setFiles(tabId, chooser.backendNodeId, files);
    return { tabId, files: files.length, route: "intercepted_file_chooser", mode: chooser.mode };
  } finally {
    await send(tabId, "Page.setInterceptFileChooserDialog", { enabled: false }).catch(() => {});
  }
}

async function setFiles(tabId, backendNodeId, files) {
  try {
    await send(tabId, "DOM.setFileInputFiles", { files, backendNodeId });
  } catch (error) {
    const allowed = await chrome.extension.isAllowedFileSchemeAccess();
    if (!allowed) {
      throw new ProviderError("file_access_not_allowed",
        "Turn on \"Allow access to file URLs\" for Machine Control in chrome://extensions");
    }
    throw error;
  }
}

// Raw DevTools protocol access under the separate devtools grant. Chrome
// still refuses the few domains it withholds from extensions.
async function cdp(params) {
  if (typeof params.method !== "string" || !/^[A-Z][A-Za-z]*\.[a-zA-Z]+$/.test(params.method)) {
    throw new ProviderError("invalid_request", "method must look like Domain.method");
  }
  const commandParams = presentationParams(params.method, params.params || {}, params.allowForeground === true);
  const tab = await resolveTab(params);
  const result = await send(tab.id, params.method, commandParams);
  return { tabId: tab.id, method: params.method, result: result ?? {} };
}

async function evaluate(params) {
  if (typeof params.expression !== "string" || !params.expression) {
    throw new ProviderError("invalid_request", "expression is required");
  }
  const tab = await resolveTab(params);
  const { result, exceptionDetails } = await send(tab.id, "Runtime.evaluate", {
    expression: params.expression,
    awaitPromise: params.awaitPromise !== false,
    returnByValue: true,
    userGesture: true,
  });
  if (exceptionDetails) {
    const text = exceptionDetails.exception?.description || exceptionDetails.text || "exception";
    throw new ProviderError("script_exception", text);
  }
  return { tabId: tab.id, type: result?.type, value: result?.value ?? null };
}

async function capture(params) {
  const tab = await resolveTab(params);
  const { data } = await send(tab.id, "Page.captureScreenshot", { format: "png" });
  return { tab: tabJSON(tab), png: data };
}

async function dialog(params) {
  const tab = await resolveTab(params);
  requireRequestAuthority();
  context.tabId = tab.id;
  context.dispatch();
  await ensureAttached(tab.id, false, true, false);
  await observePage(tab.id, 200, false);
  requireRequestAuthority();
  const current = dialogs.get(tab.id);
  const action = params.action || "status";
  if (action === "status") {
    const observer = pageObservers.get(tab.id);
    return { tabId:tab.id, observed:!!current || observer?.ready === true,
      observerState:observer?.ready ? "ready" : observer?.error ? "failed" : "pending",
      state:current ? "open" : "not_observed", dialog:current || null };
  }
  if (params.promptText !== undefined && (typeof params.promptText !== "string" || params.promptText.length > 10000))
    throw new ProviderError("invalid_request", "Prompt text must be a string of at most 10000 characters");
  if (!["accept", "dismiss"].includes(action) || !current || params.dialogId !== current.id)
    throw new ProviderError("stale_dialog", "Inspect the current dialog and supply its id and accept or dismiss");
  await send(tab.id, "Page.handleJavaScriptDialog", { accept:action === "accept",
    ...(typeof params.promptText === "string" ? { promptText:params.promptText } : {}) }, params.dialogId);
  return { tabId:tab.id, handled:true, action };
}
return { perform, prepare };
}

async function ensureAttached(tabId, newTab = false, ordinary = false, observe = true) {
  if (!granted && !devtools) throw new ProviderError("approval_required", "Browser access ended");
  const unresolved = pendingAttachments.get(tabId);
  if (unresolved && (unresolved.abandoned || unresolved.authority !== authorityGeneration
      || attachmentOwners.get(tabId) !== unresolved))
    throw new ProviderError("browser_recovery_pending", "A previous debugger attachment has not settled; this tab remains fenced");
  if (unconfirmedDetaches.has(tabId)) throw new ProviderError("browser_recovery_pending", "Debugger detach is unconfirmed; release browser control again before retrying");
  if (attached.has(tabId)) {
    if (ordinary) ordinaryTabs.add(tabId);
    if (observe) await observePage(tabId);
    return;
  }
  const generation = authorityGeneration;
  if (!attaching.has(tabId)) {
    if (pendingAttachments.size >= 8) throw new ProviderError("browser_busy", "Debugger attachment capacity exceeded");
    const token = { newTab, authority:generation, abandoned:false };
    attachmentOwners.set(tabId, token);
    const owns = () => attachmentOwners.get(tabId) === token;
    const valid = () => owns() && !token.abandoned && generation === authorityGeneration && (granted || devtools);
    const pending = (async () => {
      // Keep the raw callback accounted for after a bounded reply. A detach
      // can report absence before a slow attach actually takes effect. Until
      // that raw result settles, no fresh owner may reuse this tab.
      pendingAttachments.set(tabId, token);
      const raw = Promise.resolve().then(() => {
        if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
        return chrome.debugger.attach({ tabId }, "1.3");
      });
      raw.then(async () => {
        if (!valid()) {
          token.abandoned = true;
          // pendingAttachments excludes every fresh attach while cleanup
          // finishes, so this can only detach the abandoned attachment.
          if (!attachmentOwners.has(tabId)) attachmentOwners.set(tabId, token);
          await detachAttachment(tabId, token);
        }
      }, () => {
        if (token.abandoned && owns()) clearTab(tabId);
      }).finally(() => {
        if (pendingAttachments.get(tabId) === token) pendingAttachments.delete(tabId);
      }).catch(() => {});
      try {
        await bounded(() => raw);
      } catch (error) {
        if (owns() && error.code === "browser_cleanup_timeout") {
          token.abandoned = true; unconfirmedDetaches.add(tabId);
          detachAttachment(tabId, token).catch(() => {});
        } else if (owns()) attachmentOwners.delete(tabId);
        throw new ProviderError("debugger_attach_failed", String(error.message || error));
      }
      // A confirmed detach retires this attachment token. A late callback
      // must neither claim the tab nor detach a newer attachment.
      if (!owns()) throw new ProviderError("approval_required", "Browser attachment ended");
      if (!valid()) {
        await detachAttachment(tabId, token);
        throw new ProviderError("approval_required", "Browser access ended during attachment");
      }
      attached.add(tabId);
      notifyPanels();

    })();
    attaching.set(tabId, pending);
    pending.finally(() => { if (attaching.get(tabId) === pending) attaching.delete(tabId); }).catch(() => {});
  }
  const pending = attaching.get(tabId);
  await pending;
  if (generation !== authorityGeneration || (!granted && !devtools) || !attached.has(tabId)) {
    throw new ProviderError("approval_required", "Browser access ended during attachment");
  }
  if (ordinary) ordinaryTabs.add(tabId);
  if (observe) await observePage(tabId);
}

// Page.enable itself can wait behind an already-open modal after reattach.
// Attachment and event readiness are separate: explicit dialog recovery must
// not depend on the event command that it is needed to unblock.
async function observePage(tabId, budget = 2000, required = true) {
  const token = attachmentOwners.get(tabId);
  const authority = authorityGeneration;
  const valid = () => token && attachmentOwners.get(tabId) === token && attached.has(tabId)
    && authority === authorityGeneration && (granted || devtools);
  if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
  let observer = pageObservers.get(tabId);
  if (!observer || observer.token !== token) {
    observer = { token, ready:false, error:null, marked:false };
    pageObservers.set(tabId, observer);
    observer.promise = Promise.resolve().then(() => {
      if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
      return chrome.debugger.sendCommand({ tabId }, "Page.enable");
    }).then(() => {
      if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
      observer.ready = true;
      if (blockedTabs.get(tabId) === "browser_observer_unavailable") blockedTabs.delete(tabId);
    }).catch((error) => { observer.error = error; throw error; });
    observer.promise.catch(() => {});
  }
  try { await bounded(() => observer.promise, budget); }
  catch (error) {
    if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
    if (required) {
      blockedTabs.set(tabId, "browser_observer_unavailable");
      throw new ProviderError("browser_observer_unavailable", "Page events are unavailable; inspect dialog state, explicitly handle a modal with DevTools, or release this route");
    }
  }
  if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
  if (required && observer.ready && !observer.marked) {
    observer.marked = true;
    await bounded(() => indicators.track(tabId, token.newTab), 750).catch(() => {});
    if (!valid()) throw new ProviderError("approval_required", "Browser attachment ended");
  }
  return observer.ready;
}

// A detach reply or event belongs to one attachment, not a later owner of
// the same tab. Definite absence is also confirmation, even if its event was
// lost; repeated recovery must not get stuck on "not attached" forever.
async function detachAttachment(tabId, token = attachmentOwners.get(tabId)) {
  if (attachmentOwners.get(tabId) !== token) return true;
  if (!token) { unconfirmedDetaches.delete(tabId); return true; }
  const retire = () => {
    if (attachmentOwners.get(tabId) !== token) return;
    attached.delete(tabId);
    generations.set(tabId, (generations.get(tabId) || 0) + 1);
    clearTab(tabId);
  };
  try {
    if (virtualFocus.get(tabId) === token || unconfirmedFocusReset.has(tabId)) {
      try { await bounded(() => providerCommand({tabId}, "Emulation.setFocusEmulationEnabled", {enabled:false}), 500); }
      catch { unconfirmedFocusReset.add(tabId); }
      if (attachmentOwners.get(tabId) !== token) return true;
    }
    await bounded(() => chrome.debugger.detach({ tabId }));
    retire(); return true;
  } catch (error) {
    if (/Debugger is not attached|No tab with given id|No target with given id/i.test(String(error.message || error))) {
      retire(); return true;
    }
    if (attachmentOwners.get(tabId) !== token) return true;
    unconfirmedDetaches.add(tabId); return false;
  }
}

async function detachAll() {
  authorityGeneration += 1;
  referenceEpoch = crypto.randomUUID();
  generations.clear();
  requests.cancelAll();
  const tabs = [...new Set([...attached, ...unconfirmedDetaches, ...attaching.keys(), ...pendingAttachments.keys()])]
    .map(tabId => ({ tabId, token:attachmentOwners.get(tabId) }));
  attached.clear();
  ordinaryTabs.clear();
  blockedTabs.clear(); dialogs.clear(); pageObservers.clear();
  notifyPanels();
  // The fence above is immediate; asynchronous cleanup is strictly ordered.
  // A previous grant/release can never erase a newer tab's dialog or marker.
  const cleanup = disconnectCleanup.catch(() => {}).then(async () => {
    const streams = streaming.closeAll("access_ended");
    const decoration = indicators.releaseAll();
    await bounded(() => decoration, 750).catch(() => {});
    await Promise.all(tabs.map(({ tabId, token }) => detachAttachment(tabId, token)));
    await bounded(() => Promise.all([streams, decoration])).catch(() => {});
  });
  disconnectCleanup = cleanup;
  return cleanup;
}

function clearTab(tabId) {
  if (virtualFocus.has(tabId)) unconfirmedFocusReset.add(tabId);
  virtualFocus.delete(tabId);
  // A raw attach callback can still arrive after a detach event. Only its
  // own completion may remove pendingAttachments and permit a fresh owner.
  attachmentOwners.delete(tabId); attaching.delete(tabId); pageObservers.delete(tabId);
  unconfirmedDetaches.delete(tabId);
  dialogs.delete(tabId); blockedTabs.delete(tabId); ordinaryTabs.delete(tabId);
  requests.detached(tabId);
}

chrome.debugger.onEvent.addListener(({ tabId }, method, params) => {
  if (!attached.has(tabId) || (!granted && !devtools)) return;
  if (method === "Page.javascriptDialogOpening") {
    dialogs.set(tabId, { id:crypto.randomUUID(), type:params.type, message:String(params.message || "").slice(0,2000),
      defaultPrompt:String(params.defaultPrompt || "").slice(0,1000), url:String(params.url || "").slice(0,4096) });
    requests.cancelTab(tabId, "dialog_open");
  } else if (method === "Page.javascriptDialogClosed") {
    dialogs.delete(tabId);
    if (blockedTabs.get(tabId) === "dialog_open") blockedTabs.delete(tabId);
  }
});
chrome.debugger.onDetach.addListener(({ tabId }) => {
  clearTab(tabId);
  attached.delete(tabId);
  generations.set(tabId, (generations.get(tabId) || 0) + 1);
  notifyPanels();
  indicators.release(tabId).catch(() => {});
});
chrome.tabs.onRemoved.addListener((tabId) => {
  clearTab(tabId);
  unconfirmedFocusReset.delete(tabId);
  attached.delete(tabId);
  notifyPanels();
  generations.delete(tabId);
  indicators.release(tabId).catch(() => {});
});
chrome.tabs.onUpdated.addListener((tabId, change) => {
  // A navigation invalidates element references for that tab.
  if (change.status === "loading") generations.set(tabId, (generations.get(tabId) || 0) + 1);
  if (change.status === "complete" && attached.has(tabId) && pageObservers.get(tabId)?.ready && (granted || devtools)) {
    indicators.track(tabId).catch(() => {});
  }
});
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
// A Web Store install opens setup once; unpacked development and
// policy-installed (appliance) copies stay quiet.
chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  if (reason !== "install") return;
  const self = await chrome.management?.getSelf?.().catch(() => null);
  if (self?.installType === "normal") chrome.tabs.create({ url: "panel.html?welcome" }).catch(() => {});
});
chrome.sidePanel?.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
chrome.alarms.create("reconnect", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(connect);
// Chrome keeps a debugger-owning MV3 worker alive. The page marker expires
// independently if this worker disappears or the user cancels attachment.
setInterval(() => {
  if (port && (granted || devtools)) indicators.heartbeat().catch(() => {});
}, 3000);
connect().catch(() => {});

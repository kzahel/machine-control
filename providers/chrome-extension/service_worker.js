// Machine Control browser provider. The resident on this computer owns
// authorization: it forwards a request only while a person has granted the
// browser scope, and tells this worker when that grant ends.

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
const generations = new Map();
// Raw DevTools sessions opened for the WebSocket bridge: id -> tabId.
const sessions = new Map();

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

function connect() {
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
  port.onMessage.addListener((message) => {
    // Any message means the resident accepted this connection.
    retryDelayMs = 1000;
    lastDisconnect = "";
    onResidentMessage(message);
  });
  port.onDisconnect.addListener(() => {
    // Reading lastError marks it handled, so Chrome does not report it.
    lastDisconnect = chrome.runtime.lastError?.message || "disconnected";
    port = null;
    granted = false;
    devtools = false;
    detachAll();
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

function updateBadge() {
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

async function onResidentMessage(message) {
  if (message?.type === "grant") {
    granted = message.browser === true;
    devtools = message.devtools === true;
    if (!devtools) await closeAllSessions("devtools_grant_ended");
    if (!granted && !devtools) await detachAll();
    updateBadge();
    return;
  }
  if (message?.type === "session.open") return openSession(message);
  if (message?.type === "session.command") return sessionCommand(message);
  if (message?.type === "session.close") return closeSession(message.id, "closed");
  if (message?.type !== "request") return;
  const reply = { type: "response", id: message.id };
  try {
    reply.data = await perform(message.operation, message.params || {});
    reply.ok = true;
  } catch (error) {
    reply.ok = false;
    reply.errorCode = error.code || "browser_operation_failed";
    reply.message = String(error.message || error);
  }
  port?.postMessage(reply);
}

async function perform(operation, params) {
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
    case "browser.release": await detachAll(); return { released: true };
    default: throw new ProviderError("unsupported_operation", `Unsupported ${operation}`);
  }
}

function tabJSON(tab) {
  return {
    tabId: tab.id, windowId: tab.windowId, active: tab.active,
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
    const timer = setTimeout(() => finish(false), timeoutMs);
    function listener(id, change) {
      if (id === tabId && change.status === "complete") finish(true);
    }
    function finish(loaded) {
      clearTimeout(timer);
      chrome.tabs.onUpdated.removeListener(listener);
      resolve(loaded);
    }
    chrome.tabs.onUpdated.addListener(listener);
  });
}

async function navigate(params) {
  const url = checkURL(params.url);
  let tab;
  if (params.newTab === true) {
    tab = await chrome.tabs.create({ url, active: params.active !== false });
  } else {
    const current = await resolveTab(params);
    tab = await chrome.tabs.update(current.id, { url });
  }
  const loaded = await waitForLoad(tab.id);
  return { tab: tabJSON(await chrome.tabs.get(tab.id)), loaded };
}

async function ensureAttached(tabId) {
  if (attached.has(tabId)) return;
  try {
    await chrome.debugger.attach({ tabId }, "1.3");
  } catch (error) {
    throw new ProviderError("debugger_attach_failed", String(error.message || error));
  }
  attached.add(tabId);
}

async function send(tabId, method, params = {}) {
  await ensureAttached(tabId);
  try {
    return await chrome.debugger.sendCommand({ tabId }, method, params);
  } catch (error) {
    throw new ProviderError("cdp_command_failed", `${method}: ${error.message || error}`);
  }
}

async function detachAll() {
  const tabs = [...attached];
  attached.clear();
  await Promise.all(tabs.map((tabId) => chrome.debugger.detach({ tabId }).catch(() => {})));
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
      reference: `${tab.id}:${generation}:${node.backendDOMNodeId}`,
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
  const match = /^(\d+):(\d+):(\d+)$/.exec(String(reference || ""));
  if (!match) throw new ProviderError("invalid_reference", "reference is malformed");
  const [tabId, generation, backendNodeId] = match.slice(1).map(Number);
  if (generations.get(tabId) !== generation) {
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
  const deadline = Date.now() + timeoutMs;
  let tab = await resolveTab(params);
  while (Date.now() < deadline) {
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

async function openSession(message) {
  const { id, tabId } = message;
  try {
    await ensureAttached(tabId);
    sessions.set(id, tabId);
    port?.postMessage({ type: "session.opened", id });
  } catch (error) {
    port?.postMessage({ type: "session.failed", id, message: String(error.message || error) });
  }
}

async function sessionCommand(message) {
  const tabId = sessions.get(message.id);
  if (tabId === undefined) {
    port?.postMessage({ type: "session.result", id: message.id, cmdId: message.cmdId,
      error: { code: -32000, message: "session closed" } });
    return;
  }
  try {
    const result = await chrome.debugger.sendCommand({ tabId }, message.method, message.params || {});
    port?.postMessage({ type: "session.result", id: message.id, cmdId: message.cmdId, result: result ?? {} });
  } catch (error) {
    port?.postMessage({ type: "session.result", id: message.id, cmdId: message.cmdId,
      error: { code: -32000, message: String(error.message || error) } });
  }
}

async function closeSession(id, reason) {
  const tabId = sessions.get(id);
  if (tabId === undefined) return;
  sessions.delete(id);
  // Detach only when no session or other work holds the tab.
  if (![...sessions.values()].includes(tabId)) {
    await chrome.debugger.detach({ tabId }).catch(() => {});
    attached.delete(tabId);
  }
  port?.postMessage({ type: "session.closed", id, reason });
}

async function closeAllSessions(reason) {
  for (const id of [...sessions.keys()]) await closeSession(id, reason);
}

// Forward every debugger event to each session on that tab.
chrome.debugger.onEvent.addListener((source, method, params) => {
  for (const [id, tabId] of sessions) {
    if (tabId === source.tabId) port?.postMessage({ type: "session.event", id, method, params });
  }
});

// Raw DevTools protocol access under the separate devtools grant. Chrome
// still refuses the few domains it withholds from extensions.
async function cdp(params) {
  if (typeof params.method !== "string" || !/^[A-Z][A-Za-z]*\.[a-zA-Z]+$/.test(params.method)) {
    throw new ProviderError("invalid_request", "method must look like Domain.method");
  }
  const tab = await resolveTab(params);
  const result = await send(tab.id, params.method, params.params || {});
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

chrome.debugger.onDetach.addListener(({ tabId }) => attached.delete(tabId));
chrome.tabs.onRemoved.addListener((tabId) => {
  attached.delete(tabId);
  generations.delete(tabId);
  for (const [id, sessionTab] of sessions) {
    if (sessionTab === tabId) { sessions.delete(id); port?.postMessage({ type: "session.closed", id, reason: "tab_closed" }); }
  }
});
chrome.debugger.onDetach.addListener((source) => {
  for (const [id, tabId] of sessions) {
    if (tabId === source.tabId) { sessions.delete(id); port?.postMessage({ type: "session.closed", id, reason: "detached" }); }
  }
});
chrome.tabs.onUpdated.addListener((tabId, change) => {
  // A navigation invalidates element references for that tab.
  if (change.status === "loading") generations.set(tabId, (generations.get(tabId) || 0) + 1);
});
chrome.runtime.onStartup.addListener(connect);
chrome.runtime.onInstalled.addListener(connect);
chrome.alarms.create("reconnect", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(connect);
connect();

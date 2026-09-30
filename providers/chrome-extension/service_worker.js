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
  ArrowUp: { code: "ArrowUp", keyCode: 38 },
  ArrowDown: { code: "ArrowDown", keyCode: 40 },
  ArrowLeft: { code: "ArrowLeft", keyCode: 37 },
  ArrowRight: { code: "ArrowRight", keyCode: 39 },
};

let port = null;
let granted = false;
const attached = new Set();
const generations = new Map();

class ProviderError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function connect() {
  if (port) return;
  try {
    port = chrome.runtime.connectNative(HOST);
  } catch (error) {
    port = null;
    updateBadge();
    return;
  }
  port.onMessage.addListener(onResidentMessage);
  port.onDisconnect.addListener(() => {
    port = null;
    granted = false;
    detachAll();
    updateBadge();
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
  const text = !port ? "!" : granted ? "ON" : "";
  chrome.action.setBadgeText({ text });
  chrome.action.setBadgeBackgroundColor({ color: granted ? "#c62828" : "#757575" });
  chrome.action.setTitle({
    title: !port ? "Machine Control: resident not connected"
      : granted ? "Machine Control: an agent may control Chrome"
        : "Machine Control: no browser access granted",
  });
}

async function onResidentMessage(message) {
  if (message?.type === "grant") {
    granted = message.browser === true;
    if (!granted) await detachAll();
    updateBadge();
    return;
  }
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
    case "browser.navigate": return navigate(params);
    case "browser.snapshot": return snapshot(params);
    case "browser.click": return click(params);
    case "browser.type": return type(params);
    case "browser.key": return key(params);
    case "browser.capture": return capture(params);
    case "browser.release": await detachAll(); return { released: true };
    default: throw new ProviderError("unsupported_operation", `Unsupported ${operation}`);
  }
}

function tabJSON(tab) {
  return {
    tabId: tab.id, windowId: tab.windowId, active: tab.active,
    title: tab.title || "", url: tab.url || "", status: tab.status || "",
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
  const spec = KEYS[params.key];
  if (!spec) throw new ProviderError("invalid_request", `key must be one of ${Object.keys(KEYS).join(", ")}`);
  const tabId = (await resolveTab(params)).id;
  const base = { key: params.key, code: spec.code, windowsVirtualKeyCode: spec.keyCode };
  await send(tabId, "Input.dispatchKeyEvent", { type: "keyDown", ...base, text: spec.text });
  await send(tabId, "Input.dispatchKeyEvent", { type: "keyUp", ...base });
  return { tabId, key: params.key };
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

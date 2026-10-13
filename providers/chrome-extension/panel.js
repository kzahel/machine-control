// Read-only side panel. The service worker pushes connection, access,
// controlled-tab and activity state; nothing here can grant access.
const $ = (id) => document.getElementById(id);
const welcome = new URLSearchParams(location.search).has("welcome");
const LABELS = {
  "browser.tabs": "Listed tabs",
  "browser.wait": "Waited for page",
  "browser.navigate": "Opened",
  "browser.snapshot": "Read page structure",
  "browser.click": "Clicked",
  "browser.type": "Typed",
  "browser.key": "Pressed",
  "browser.capture": "Took screenshot",
  "browser.upload": "Attached",
  "browser.cdp": "DevTools command",
  "browser.eval": "Ran script",
  "browser.release": "Released tabs",
  "session.open": "Opened DevTools stream",
};
// Chrome's native-messaging errors, in terms a person can act on.
const DISCONNECTS = [
  ["not found", "The Machine Control app is not installed, or its browser setup has not run."],
  ["forbidden", "The installed Machine Control app does not recognize this copy of the extension. Update the app and run its browser setup again."],
  ["exited", "The Machine Control app is not running."],
  ["communicating", "The Machine Control app is not running."],
];
const tabCache = new Map();
let state = null;

document.body.classList.toggle("page", welcome);
$("welcome").hidden = !welcome;
$("version").textContent = `v${chrome.runtime.getManifest().version}`;

function setupReason(lastDisconnect) {
  const text = String(lastDisconnect || "").toLowerCase();
  if (!text || text === "starting") return "Connecting to the Machine Control app…";
  return DISCONNECTS.find(([match]) => text.includes(match))?.[1]
    ?? `Chrome could not reach the Machine Control app (${lastDisconnect}).`;
}

async function tabInfo(tabId) {
  if (!Number.isInteger(tabId)) return null;
  try {
    const tab = await chrome.tabs.get(tabId);
    tabCache.set(tabId, tab);
    return tab;
  } catch {
    return tabCache.get(tabId) ?? null;
  }
}

function host(url) {
  try { return new URL(url).host || url; } catch { return url || ""; }
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

async function renderTabs(ids) {
  const list = $("tabs");
  const tabs = (await Promise.all(ids.map(tabInfo))).filter(Boolean);
  list.replaceChildren(...tabs.map((tab) => {
    const item = element("li");
    const icon = element("img");
    icon.alt = "";
    icon.src = tab.favIconUrl?.startsWith("data:") || tab.favIconUrl?.startsWith("http")
      ? tab.favIconUrl : "icons/16.png";
    const text = element("div", "tab-text");
    text.append(element("div", "tab-title", tab.title || "Untitled"), element("div", "tab-host", host(tab.url)));
    item.append(icon, text);
    item.title = "Show this tab";
    item.addEventListener("click", async () => {
      await chrome.tabs.update(tab.id, { active: true }).catch(() => {});
      await chrome.windows.update(tab.windowId, { focused: true }).catch(() => {});
    });
    return item;
  }));
  $("tab-count").textContent = tabs.length ? String(tabs.length) : "";
  $("no-tabs").hidden = tabs.length > 0;
}

function timeOf(at) {
  return new Date(at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit", second: "2-digit" });
}

async function renderActivity(entries) {
  const list = $("activity");
  const items = await Promise.all(entries.slice(0, 100).map(async (entry) => {
    const item = element("li", entry.ok ? "" : "failed");
    const main = element("div", "entry-main");
    const label = [LABELS[entry.operation] ?? entry.operation, entry.detail].filter(Boolean).join(" ");
    main.append(element("div", "", entry.count > 1 ? `${label} ×${entry.count}` : label));
    const tab = await tabInfo(entry.tabId);
    if (tab) main.append(element("div", "entry-tab", tab.title || host(tab.url)));
    if (!entry.ok) main.append(element("div", "entry-error", entry.errorCode || "failed"));
    item.append(element("span", "dot"), main, element("span", "entry-time", timeOf(entry.at)));
    return item;
  }));
  list.replaceChildren(...items);
  $("no-activity").hidden = items.length > 0;
}

async function render() {
  if (!state) return;
  const live = state.granted || state.devtools;
  const status = $("status");
  status.textContent = !state.connected ? "Not connected" : state.devtools ? "DevTools access"
    : state.granted ? "Agent may control" : "Connected";
  status.className = `pill ${!state.connected ? "disconnected" : live ? "live" : "connected"}`;
  $("setup").hidden = state.connected;
  $("setup-reason").textContent = setupReason(state.lastDisconnect);
  $("access").hidden = !state.connected;
  const summary = $("access-summary");
  summary.textContent = state.devtools
    ? "An agent has full DevTools access: it can run scripts and read data on any site."
    : state.granted ? "An agent may control Chrome tabs."
      : "No agent has browser access right now.";
  summary.classList.toggle("live", live);
  $("tabs-card").hidden = !state.connected;
  $("activity-card").hidden = !state.connected && !state.activity.length;
  await Promise.all([renderTabs(state.controlledTabs), renderActivity(state.activity)]);
}

function connect() {
  const port = chrome.runtime.connect({ name: "panel" });
  port.onMessage.addListener((message) => {
    if (message?.type !== "state") return;
    state = message;
    render();
  });
  // The worker can restart; reconnect so the panel stays live.
  port.onDisconnect.addListener(() => setTimeout(connect, 500));
  $("clear").onclick = () => port.postMessage({ type: "clearActivity" });
}

const platform = navigator.userAgentData?.platform || navigator.platform || "";
if (/cros|chrome os/i.test(platform)) {
  $("download").href = "https://github.com/kzahel/machine-control/tree/main/platforms/chromeos";
}
chrome.tabs.onUpdated.addListener((tabId, change) => {
  if (state?.controlledTabs.includes(tabId) && (change.title || change.favIconUrl || change.url)) render();
});
connect();

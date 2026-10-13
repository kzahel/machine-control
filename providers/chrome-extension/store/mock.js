// Stand-in extension APIs so the real side panel renders fixed, fictional
// scenes for Web Store screenshots. Nothing here ships in the extension.
const scene = new URLSearchParams(location.search).get("scene") || "live";
const at = (h, m, s) => new Date(2026, 9, 13, h, m, s).getTime();
const pointer = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><path d="M7 4 L25 17 L17 19 L14 27 Z" fill="#2563eb" stroke="white" stroke-width="2" stroke-linejoin="round"/></svg>');
const TABS = {
  101: { id: 101, windowId: 1, title: "Checkout — Acme Outfitters", url: "https://shop.example.com/checkout", favIconUrl: pointer },
  102: { id: 102, windowId: 1, title: "Order history — Acme Outfitters", url: "https://shop.example.com/orders", favIconUrl: pointer },
};
const STATES = {
  live: {
    connected: true, granted: true, devtools: false, controlledTabs: [101, 102], activity: [
      { at: at(10, 42, 31), operation: "browser.click", tabId: 101, ok: true, count: 1, detail: "" },
      { at: at(10, 42, 29), operation: "browser.snapshot", tabId: 101, ok: true, count: 2, detail: "" },
      { at: at(10, 42, 22), operation: "browser.type", tabId: 101, ok: true, count: 1, detail: "18 characters" },
      { at: at(10, 42, 19), operation: "browser.click", tabId: 101, ok: false, count: 1, detail: "", errorCode: "stale_reference" },
      { at: at(10, 42, 12), operation: "browser.navigate", tabId: 101, ok: true, count: 1, detail: "shop.example.com" },
      { at: at(10, 41, 58), operation: "browser.capture", tabId: 102, ok: true, count: 1, detail: "" },
      { at: at(10, 41, 51), operation: "browser.tabs", tabId: null, ok: true, count: 1, detail: "4 tabs" },
    ],
  },
  devtools: {
    connected: true, granted: true, devtools: true, controlledTabs: [101], activity: [
      { at: at(11, 5, 8), operation: "browser.cdp", tabId: 101, ok: true, count: 3, detail: "Network.getResponseBody" },
      { at: at(11, 5, 2), operation: "session.open", tabId: 101, ok: true, count: 1, detail: "" },
    ],
  },
  setup: {
    connected: false, lastDisconnect: "Specified native messaging host not found.",
    granted: false, devtools: false, controlledTabs: [], activity: [],
  },
};

const listeners = { addListener() {} };
globalThis.chrome = {
  runtime: {
    getManifest: () => ({ version: "0.8.0" }),
    connect: () => ({
      onMessage: { addListener(fn) { setTimeout(() => fn({ type: "state", ...STATES[scene] })); } },
      onDisconnect: listeners,
      postMessage() {},
    }),
  },
  tabs: {
    async get(id) { if (!TABS[id]) throw new Error("No tab"); return TABS[id]; },
    async update() {},
    onUpdated: listeners,
  },
  windows: { async update() {} },
};

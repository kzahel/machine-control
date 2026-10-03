// Owned tab indicators. The resident remains the authorization authority.
// Use the already authorized per-tab debugger to enter an isolated world;
// no broad scripting or host permissions are needed just to show a marker.
const STORAGE_KEY = "controlledTabs";
const GROUP_TITLE = "Machine Control";
const GROUP_COLOR = "blue";

// Runs inside a page's isolated world. Keep it self-contained for CDP.
export function pageIndicator(icon) {
  const key = "__machineControlIndicator";
  const attribute = "data-machine-control-icon";
  const original = "data-machine-control-original-icon";
  const created = "data-machine-control-created-icon";
  const selector = 'link[rel~="icon"]';
  const previous = globalThis[key];
  if (icon && previous?.icon === icon) {
    previous.touch();
    return { visible: true };
  }
  previous?.stop();

  function restore(link) {
    // Preserve a site's replacement rather than blindly restoring old state.
    if (link.getAttribute("href") === link.getAttribute(attribute)) {
      if (link.hasAttribute(created)) {
        // Chrome retains its last favicon when the only link is removed.
        // Load a neutral icon first, then remove our temporary link. Leave a
        // site adoption during that interval untouched.
        const neutral = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32"><g fill="none" stroke="#80868b" stroke-width="2"><circle cx="16" cy="16" r="11"/><ellipse cx="16" cy="16" rx="5" ry="11"/><path d="M5 16h22"/></g></svg>');
        for (const name of [attribute, original, created]) link.removeAttribute(name);
        link.setAttribute("href", neutral);
        setTimeout(() => { if (link.getAttribute("href") === neutral) link.remove(); }, 250);
        return;
      }
      const saved = JSON.parse(link.getAttribute(original) || "null");
      if (saved === null) link.removeAttribute("href");
      else link.setAttribute("href", saved);
    }
    for (const name of [attribute, original, created]) link.removeAttribute(name);
  }
  for (const link of document.querySelectorAll(`link[${attribute}]`)) restore(link);
  delete globalThis[key];
  if (!icon) return { visible: false };

  const escape = (value) => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  // Original artwork: a white-outlined blue pointer, with a site icon beneath.
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">`
    + (icon === "missing" ? '<rect width="32" height="32" rx="7" fill="#dbeafe"/>'
      : `<image href="${escape(icon)}" width="32" height="32" opacity="0.35"/>`)
    + '<path d="M7 4 L25 17 L17 19 L14 27 Z" fill="#2563eb" stroke="white" stroke-width="2" stroke-linejoin="round"/>'
    + '</svg>';
  const href = `data:image/svg+xml,${encodeURIComponent(svg)}`;
  const observer = new MutationObserver((changes) => {
    if (changes.some((change) => change.target instanceof HTMLLinkElement
      || [...change.addedNodes, ...change.removedNodes].some((node) =>
        node instanceof HTMLLinkElement || node.querySelector?.(selector)))) refresh();
  });
  function refresh() {
    observer.disconnect();
    for (const link of document.querySelectorAll(`link[${attribute}]`)) {
      if (!link.matches(selector)) restore(link);
    }
    const links = [...document.querySelectorAll(selector)];
    if (!links.length) {
      const link = document.createElement("link");
      link.rel = "icon";
      link.setAttribute(created, "true");
      (document.head || document.documentElement).appendChild(link);
      links.push(link);
    }
    for (const link of links) {
      if (link.getAttribute("href") !== href) {
        // A site may adopt our fallback link for its own newly supplied icon.
        if (link.hasAttribute(attribute)) link.removeAttribute(created);
        link.setAttribute(original, JSON.stringify(link.getAttribute("href")));
        link.setAttribute(attribute, href);
        link.setAttribute("href", href);
      }
    }
    observer.observe(document.documentElement, {
      subtree: true, childList: true, attributes: true, attributeFilter: ["href", "rel"],
    });
  }
  let expiry;
  const state = { icon, touch() {
    clearTimeout(expiry);
    expiry = setTimeout(() => { state.stop(); delete globalThis[key]; }, 10000);
  }, stop() {
    clearTimeout(expiry);
    observer.disconnect();
    for (const link of document.querySelectorAll(`link[${attribute}]`)) restore(link);
  } };
  globalThis[key] = state;
  state.touch();
  refresh();
  return { visible: true };
}

export class TabIndicators {
  constructor(command) {
    this.command = command;
    this.tabs = new Map();
    this.epoch = 0;
    this.queue = Promise.resolve();
  }

  enqueue(work) {
    const result = this.queue.then(work, work);
    this.queue = result.catch(() => {});
    return result;
  }

  async save() {
    await chrome.storage.local.set({ [STORAGE_KEY]: [...this.tabs.entries()].map(([tabId, state]) =>
      [tabId, { groupId: state.groupId, windowId: state.windowId }]) });
  }

  // A fresh worker has no grant. Recover only our recorded DOM/group changes,
  // then detach. Never infer authorization from persisted indicator metadata.
  async recover() {
    const saved = (await chrome.storage.local.get(STORAGE_KEY))[STORAGE_KEY] || [];
    for (const [tabId, state] of saved) {
      try {
        await chrome.debugger.attach({ tabId }, "1.3");
        try { await this.render(tabId, null); }
        finally { await chrome.debugger.detach({ tabId }).catch(() => {}); }
      } catch { /* Closed or restricted tabs cannot be restored through CDP. */ }
      await this.ungroup(tabId, state);
    }
    await chrome.storage.local.remove(STORAGE_KEY);
  }

  status(tabId) {
    const state = this.tabs.get(tabId);
    return state ? (state.visible ? "active" : "unavailable") : "none";
  }

  async track(tabId, newTab = false) {
    const epoch = this.epoch;
    return this.enqueue(async () => {
      if (epoch !== this.epoch) return;
      let state = this.tabs.get(tabId);
      if (!state) {
        state = { visible: false, groupId: null };
        this.tabs.set(tabId, state);
      }
      // Only group a freshly created, ungrouped, unpinned tab. Group per window.
      if (newTab) {
        try {
          const tab = await chrome.tabs.get(tabId);
          if (!tab.pinned && tab.groupId === -1) {
            const peer = [...this.tabs.entries()].find(([id, item]) =>
              id !== tabId && item.windowId === tab.windowId && item.groupId != null);
            let group = peer && await chrome.tabGroups.get(peer[1].groupId).catch(() => null);
            if (group?.shared || group?.title !== GROUP_TITLE || group?.color !== GROUP_COLOR) group = null;
            const groupId = await chrome.tabs.group(group
              ? { groupId: group.id, tabIds: [tabId] }
              : { createProperties: { windowId: tab.windowId }, tabIds: [tabId] });
            state.groupId = groupId;
            state.windowId = tab.windowId;
            await this.save();
            if (!group) await chrome.tabGroups.update(groupId, { title: GROUP_TITLE, color: GROUP_COLOR });
          }
        } catch { /* An optional marker must not turn delivery into a failure. */ }
      }
      await this.save();
      if (epoch !== this.epoch) return;
      try {
        const icon = await this.icon(tabId);
        if (epoch !== this.epoch) return;
        state.visible = (await this.render(tabId, icon)).visible;
        state.icon = icon;
      } catch { state.visible = false; }
    });
  }

  async icon(tabId) {
    const tab = await chrome.tabs.get(tabId);
    if (!tab.url?.startsWith("http:") && !tab.url?.startsWith("https:")) return "missing";
    const url = new URL(chrome.runtime.getURL("/_favicon/"));
    url.searchParams.set("pageUrl", tab.url);
    url.searchParams.set("size", "32");
    try {
      const response = await fetch(url.href, { signal: AbortSignal.timeout(2000) });
      const data = new Uint8Array(await response.arrayBuffer());
      const type = response.headers.get("content-type");
      if (!response.ok || !type?.startsWith("image/") || data.length > 65536) return "missing";
      // Avoid a stale icon after navigation. No requests go to the website.
      if ((await chrome.tabs.get(tabId)).url !== tab.url) return "missing";
      return `data:${type};base64,${btoa(Array.from(data, (byte) => String.fromCharCode(byte)).join(""))}`;
    } catch { return "missing"; }
  }

  async render(tabId, icon) {
    const { frameTree } = await this.command(tabId, "Page.getFrameTree");
    const { executionContextId } = await this.command(tabId, "Page.createIsolatedWorld", {
      frameId: frameTree.frame.id, worldName: "machine-control-indicator",
    });
    const response = await this.command(tabId, "Runtime.callFunctionOn", {
      executionContextId, functionDeclaration: pageIndicator.toString(),
      arguments: [{ value: icon }], returnByValue: true,
    });
    if (response.exceptionDetails) throw new Error("Indicator could not be rendered");
    return response.result?.value || { visible: false };
  }

  heartbeat() {
    const epoch = this.epoch;
    return this.enqueue(async () => {
      for (const [tabId, state] of this.tabs) {
        if (epoch !== this.epoch) return;
        try { state.visible = (await this.render(tabId, state.icon || "missing")).visible; }
        catch { state.visible = false; }
      }
    });
  }

  async ungroup(tabId, state) {
    if (state.groupId == null) return;
    try {
      const tab = await chrome.tabs.get(tabId);
      const group = await chrome.tabGroups.get(state.groupId);
      // Preserve moves, renamed/recolored groups, and shared groups.
      if (tab.groupId === state.groupId && tab.windowId === state.windowId && !group.shared
        && group.title === GROUP_TITLE && group.color === GROUP_COLOR) await chrome.tabs.ungroup([tabId]);
    } catch { /* A closed tab/group is already clean. */ }
  }

  release(tabId) {
    return this.enqueue(async () => {
      const state = this.tabs.get(tabId);
      if (!state) return;
      await this.render(tabId, null).catch(() => {});
      await this.ungroup(tabId, state);
      this.tabs.delete(tabId);
      await this.save();
    });
  }

  releaseAll() {
    // Fence pending icon fetches and queued tracking before cleanup.
    this.epoch += 1;
    return this.enqueue(async () => {
      for (const [tabId, state] of this.tabs) {
        await this.render(tabId, null).catch(() => {});
        await this.ungroup(tabId, state);
      }
      this.tabs.clear();
      await this.save();
    });
  }
}

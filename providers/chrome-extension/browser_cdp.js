// Owned browser-level CDP facade over extension APIs. Default-profile pages
// are real debugger targets; browser/tab targets and their sessions are facade
// identities. No isolated context, download policy or browser shutdown is faked.
const DEFAULT_CONTEXT = "mc-default";
const BROWSER = "mc-browser";
const MAX_TARGETS = 256;
const DEFAULT_FILTER = [{ type: "browser", exclude: true }, { type: "tab", exclude: true }, {}];
const fail = (message, code = -32000) => { throw Object.assign(new Error(message), { cdpCode: code }); };
const accepts = (filter, type) => {
  const rule = (filter ?? DEFAULT_FILTER).find((item) => !item.type || item.type === type);
  return !!rule && !rule.exclude;
};
const allowedTab = (tab) => !tab.incognito && /^(https?:|file:|about:blank(?:$|[?#]))/.test(tab.url || "")
  && !/^https:\/\/(chromewebstore\.google\.com|chrome\.google\.com\/webstore)(\/|$)/.test(tab.url || "");

export class BrowserCdp {
  constructor({ chrome, ensureAttached, releaseTab, trackNewTab, authority, post }) {
    Object.assign(this, { chrome, ensureAttached, releaseTab, trackNewTab, authority, post });
    this.sessions = new Map();
    this.serial = Promise.resolve();
    this.nextSession = 0;
    chrome.tabs.onCreated.addListener(() => this.refresh());
    chrome.tabs.onUpdated.addListener(() => this.refresh());
    chrome.tabs.onRemoved.addListener((tabId) => { this.detached(tabId, "tab_closed"); this.refresh(); });
    chrome.debugger.onDetach.addListener(({ tabId }, reason) =>
      this.detached(tabId, reason === "target_closed" ? "tab_closed" : "detached"));
    chrome.debugger.onEvent.addListener((source, method, params) => this.event(source, method, params));
  }

  enqueue(work) {
    const result = this.serial.then(work);
    this.serial = result.catch(() => {});
    return result;
  }

  usesTab(tabId) {
    return [...this.sessions.values()].some((state) => state.tabId === tabId ||
      state.ownedTabs.has(tabId) ||
      [...state.routes.values()].some((route) => route.native?.tabId === tabId));
  }

  async open(id, tabId) {
    if (!this.authority()) fail("DevTools access is not enabled");
    if (this.sessions.has(id)) fail("Duplicate session");
    if (tabId === 0 ? this.sessions.size : [...this.sessions.values()].some((state) => state.tabId === 0))
      fail("Browser and per-tab connections require exclusive attachment");
    const authority = this.authority();
    const state = { id, tabId, authority, routes: new Map(), targets: new Map(), ownedTabs: new Set(), auto: null, discover: null };
    this.sessions.set(id, state);
    try {
      if (tabId !== 0) await this.ensureAttached(tabId);
      this.check(state);
    } catch (error) {
      this.sessions.delete(id);
      if (tabId !== 0) await this.releaseTab(tabId);
      throw error;
    }
  }

  current(state) { return this.sessions.get(state.id) === state && !!state.authority && state.authority === this.authority(); }
  check(state) { if (!this.current(state)) fail("DevTools session ended"); }
  emit(state, method, params = {}, sessionId) {
    if (this.current(state)) this.post({ type: "session.event", id: state.id, method, params,
      ...(sessionId ? { sessionId } : {}) });
  }

  async command(message) {
    const state = this.sessions.get(message.id);
    if (!state || !this.current(state)) {
      this.post({ type: "session.result", id: message.id, cmdId: message.cmdId,
        ...(message.sessionId ? { sessionId: message.sessionId } : {}), error: { code: -32000, message: "session closed" } });
      return;
    }
    const { method, params = {}, sessionId } = message;
    const reply = { type: "session.result", id: state.id, cmdId: message.cmdId,
      ...(sessionId ? { sessionId } : {}) };
    try {
      const route = sessionId ? state.routes.get(sessionId) : null;
      if (sessionId && !route) fail("Unknown or detached session");
      if (route?.kind === "browser" || (!sessionId && state.tabId === 0)) {
        reply.result = await this.enqueue(() => {
          this.check(state);
          if (sessionId && state.routes.get(sessionId) !== route) fail("Detached browser session");
          return this.rootCommand(state, method, params);
        });
      } else if (route?.kind === "tab") {
        reply.result = await this.enqueue(() => {
          this.check(state);
          if (state.routes.get(sessionId) !== route) fail("Detached tab session");
          return this.tabCommand(state, route, method, params);
        });
      } else {
        const native = route?.native ?? { tabId: state.tabId };
        // Never accept an arbitrary native sessionId from a caller. Each child
        // route is learned from this connection's own attachment events.
        if (method === "Target.detachFromTarget") {
          const child = state.routes.get(params.sessionId);
          if (!child || child.parent !== sessionId) fail("Unknown child session");
          await this.detach(state, params.sessionId); reply.result = {};
        } else reply.result = await this.chrome.debugger.sendCommand(native, method, params);
      }
    } catch (error) {
      reply.error = { code: error.cdpCode ?? -32000, message: String(error.message || error) };
    }
    if (this.current(state)) {
      if (sessionId && !state.routes.has(sessionId)) {
        delete reply.result; reply.error = { code: -32000, message: "Unknown or detached session" };
      }
      this.post(reply);
    }
  }

  browserInfo() { return { targetId: BROWSER, type: "browser", title: "", url: "", attached: true }; }
  async targets() {
    const [tabs, native] = await Promise.all([this.chrome.tabs.query({}), this.chrome.debugger.getTargets()]);
    const pages = tabs.filter(allowedTab).flatMap((tab) => {
      const target = native.find((item) => item.tabId === tab.id && item.type === "page");
      if (!target) return [];
      return [{ targetId: target.id, type: "page", title: tab.title || "", url: tab.url || "", attached: false,
        browserContextId: DEFAULT_CONTEXT, ...(tab.openerTabId ? {
          openerId: native.find((item) => item.tabId === tab.openerTabId)?.id, canAccessOpener: true } : {}),
        tabId: tab.id }];
    });
    if (pages.length > MAX_TARGETS) fail("Browser target capacity exceeded");
    return [this.browserInfo(), ...pages.flatMap((page) => [page,
      { ...page, targetId: "mc-tab-" + page.targetId, type: "tab" }])];
  }

  info(state, target) {
    const { tabId, ...info } = target;
    info.attached = info.type === "browser" || [...state.routes.values()].some((route) => route.target.targetId === info.targetId);
    return info;
  }

  async sync(state) {
    const targets = await this.targets(); this.check(state);
    const previous = state.targets;
    state.targets = new Map(targets.map((target) => [target.targetId, target]));
    for (const [id, route] of [...state.routes]) if (state.routes.has(id) && route.target.tabId && !state.targets.has(route.target.targetId))
      await this.detach(state, id);
    if (state.discover) {
      for (const target of targets) {
        if (!accepts(state.discover.filter, target.type)) continue;
        if (!previous.has(target.targetId)) this.emit(state, "Target.targetCreated", { targetInfo: this.info(state, target) });
        else if (JSON.stringify(target) !== JSON.stringify(previous.get(target.targetId)))
          this.emit(state, "Target.targetInfoChanged", { targetInfo: this.info(state, target) });
      }
      for (const target of previous.values()) if (!state.targets.has(target.targetId) && accepts(state.discover.filter, target.type))
        this.emit(state, "Target.targetDestroyed", { targetId: target.targetId });
    }
    if (state.auto) for (const target of targets) if (accepts(state.auto.filter, target.type) && target.type !== "browser")
      await this.attach(state, target);
    return targets;
  }

  refresh() {
    if (![...this.sessions.values()].some((state) => state.tabId === 0)) return;
    if (this.refreshQueued) { this.refreshAgain = true; return; }
    this.refreshQueued = true;
    this.enqueue(async () => {
      for (const state of [...this.sessions.values()]) if (state.tabId === 0 && this.current(state)) {
        try { await this.sync(state); }
        catch { await this.close(state.id, "target_discovery_failed"); }
      }
    }).catch(() => {}).finally(() => {
      this.refreshQueued = false;
      if (this.refreshAgain) { this.refreshAgain = false; this.refresh(); }
    });
  }

  async attach(state, target, parent) {
    this.check(state);
    const existing = [...state.routes.entries()].find(([, route]) => route.target.targetId === target.targetId && route.parent === parent);
    if (existing) return existing[0];
    if (state.routes.size >= MAX_TARGETS) fail("Attached session capacity exceeded");
    const sessionId = "mc-session-" + (++this.nextSession);
    const route = { kind: target.type, target, parent,
      ...(target.type === "page" ? { native: { tabId: target.tabId } } : {}) };
    state.routes.set(sessionId, route);
    try {
      if (route.native) await this.ensureAttached(target.tabId);
      this.check(state);
    } catch (error) {
      state.routes.delete(sessionId);
      if (route.native) await this.releaseTab(target.tabId);
      throw error;
    }
    this.emit(state, "Target.attachedToTarget", { sessionId, targetInfo: this.info(state, target), waitingForDebugger: false }, parent);
    return sessionId;
  }

  async rootCommand(state, method, params) {
    switch (method) {
      case "Browser.getVersion": {
        const values = await globalThis.navigator?.userAgentData?.getHighEntropyValues(["fullVersionList"]);
        this.check(state);
        const version = values?.fullVersionList?.find((brand) => /Chromium|Google Chrome/.test(brand.brand))?.version
          ?? globalThis.navigator?.userAgent?.match(/(?:Chrome|Chromium)\/([\d.]+)/)?.[1] ?? "unknown";
        return { protocolVersion: "1.3", product: "Chrome/" + version,
          userAgent: globalThis.navigator?.userAgent ?? "", revision: "", jsVersion: "" };
      }
      case "Target.getBrowserContexts": return { browserContextIds: [] };
      case "Target.getTargets":
        this.validateFilter(params.filter);
        return { targetInfos: (await this.targets()).filter((target) => accepts(params.filter, target.type))
          .map((target) => this.info(state, target)) };
      case "Target.getTargetInfo": {
        const target = params.targetId ? (await this.targets()).find((item) => item.targetId === params.targetId) : this.browserInfo();
        if (!target) fail("Unknown target");
        return { targetInfo: this.info(state, target) };
      }
      case "Target.setDiscoverTargets":
        this.validateFilter(params.filter);
        if (typeof params.discover !== "boolean") fail("discover must be boolean", -32602);
        state.discover = params.discover ? { filter: params.filter } : null;
        state.targets.clear(); await this.sync(state); return {};
      case "Target.setAutoAttach":
        this.validateAuto(params);
        state.auto = params.autoAttach ? { filter: params.filter } : null;
        if (!state.auto) {
          for (const [id, route] of [...state.routes]) if (!route.parent && route.kind !== "browser") await this.detach(state, id);
        } else await this.sync(state);
        return {};
      case "Target.attachToBrowserTarget": return { sessionId: await this.attach(state, this.browserInfo()) };
      case "Target.attachToTarget": {
        if (params.flatten !== true) fail("Only flattened sessions are supported", -32602);
        const target = (await this.targets()).find((item) => item.targetId === params.targetId);
        if (!target) fail("Unknown or unavailable target");
        return { sessionId: await this.attach(state, target) };
      }
      case "Target.detachFromTarget": await this.detach(state, params.sessionId); return {};
      case "Target.createTarget": {
        this.defaultContext(params);
        if (Object.keys(params).some((key) => !["url", "browserContextId", "background"].includes(key)))
          fail("Only default-profile tabs are supported", -32602);
        if (typeof params.url !== "string" || (params.background !== undefined && typeof params.background !== "boolean"))
          fail("Invalid new tab parameters", -32602);
        if (!allowedTab({ url: params.url })) fail("Restricted or unsupported tab URL");
        const tab = await this.chrome.tabs.create({ url: params.url, active: params.background !== true });
        if (!this.current(state)) fail("Session ended during tab creation; do not replay creation");
        state.ownedTabs.add(tab.id);
        await this.trackNewTab(tab.id);
        if (!this.current(state)) { await this.releaseTab(tab.id); fail("Session ended during tab attachment"); }
        const targets = await this.sync(state);
        const target = targets.find((item) => item.tabId === tab.id && item.type === "page");
        if (!target) fail("New tab target unavailable; do not replay creation");
        return { targetId: target.targetId };
      }
      case "Target.closeTarget":
      case "Target.activateTarget": {
        const target = (await this.targets()).find((item) => item.targetId === params.targetId);
        if (!target?.tabId) fail("Unknown or unsupported target");
        this.check(state);
        if (method === "Target.closeTarget") { await this.chrome.tabs.remove(target.tabId); await this.sync(state); return { success: true }; }
        await this.chrome.tabs.update(target.tabId, { active: true }); return {};
      }
      default: fail("Unsupported browser-level operation: " + method, -32601);
    }
  }

  defaultContext(params) {
    if (params.browserContextId !== undefined && params.browserContextId !== DEFAULT_CONTEXT)
      fail("Isolated browser contexts are unavailable");
  }
  validateFilter(filter) {
    if (filter !== undefined && (!Array.isArray(filter) || filter.length > 32 || filter.some((rule) =>
      !rule || typeof rule !== "object" || Object.keys(rule).some((key) => !["type", "exclude"].includes(key)) ||
      (rule.type !== undefined && typeof rule.type !== "string") || (rule.exclude !== undefined && typeof rule.exclude !== "boolean"))))
      fail("Invalid target filter", -32602);
  }
  validateAuto(params) {
    this.validateFilter(params.filter);
    if (typeof params.autoAttach !== "boolean" || params.flatten !== true || typeof params.waitForDebuggerOnStart !== "boolean")
      fail("Only flattened auto-attachment is supported", -32602);
  }

  async tabCommand(state, route, method, params) {
    if (method === "Runtime.runIfWaitingForDebugger") return {}; // A facade tab wrapper never pauses a renderer.
    if (method === "Target.getTargetInfo") return { targetInfo: this.info(state, route.target) };
    if (method === "Target.detachFromTarget") { await this.detach(state, params.sessionId); return {}; }
    if (method !== "Target.setAutoAttach") fail("Unsupported tab-wrapper operation: " + method, -32601);
    this.validateAuto(params);
    const parent = [...state.routes.entries()].find(([, value]) => value === route)?.[0];
    if (params.autoAttach && accepts(params.filter, "page")) {
      const page = (await this.targets()).find((target) => target.tabId === route.target.tabId && target.type === "page");
      if (page) await this.attach(state, page, parent);
    } else for (const [id, child] of [...state.routes]) if (child.parent === parent) await this.detach(state, id);
    return {};
  }

  async detach(state, id) {
    const route = state.routes.get(id);
    if (!route) fail("Unknown or detached session");
    for (const [childId, child] of [...state.routes]) if (child.parent === id) await this.detach(state, childId);
    const nativeParent = state.routes.get(route.parent)?.native ?? { tabId: route.native?.tabId };
    state.routes.delete(id);
    if (route.native?.sessionId) {
      await this.chrome.debugger.sendCommand(nativeParent, "Target.detachFromTarget",
        { sessionId: route.native.sessionId }).catch(() => {});
    } else if (route.native) await this.releaseTab(route.native.tabId);
    this.emit(state, "Target.detachedFromTarget", { sessionId: id, targetId: route.target.targetId }, route.parent);
  }

  async close(id, reason) {
    const state = this.sessions.get(id);
    if (!state) return;
    this.sessions.delete(id); // Fence pending results before asynchronous cleanup.
    const tabs = new Set([...(state.tabId ? [state.tabId] : []),
      ...state.ownedTabs, ...[...state.routes.values()].flatMap((route) => route.native ? [route.native.tabId] : [])]);
    state.routes.clear();
    await Promise.all([...tabs].map((tab) => this.releaseTab(tab)));
    this.post({ type: "session.closed", id, reason });
  }
  async closeAll(reason) { await Promise.all([...this.sessions.keys()].map((id) => this.close(id, reason))); }

  detached(tabId, reason) {
    for (const state of [...this.sessions.values()]) {
      state.ownedTabs.delete(tabId);
      if (state.tabId === tabId) { this.close(state.id, reason).catch(() => {}); continue; }
      const removed = [...state.routes].filter(([, route]) => route.native?.tabId === tabId || route.target.tabId === tabId);
      // Respect Chrome's own Cancel/DevTools takeover. Otherwise indicator
      // cleanup can produce a tab update and auto-attach the canceled page.
      if (reason === "detached" && removed.length) {
        this.close(state.id, "native_debugger_detached").catch(() => {}); continue;
      }
      for (const [id] of removed) state.routes.delete(id);
      for (const [id, route] of removed) this.emit(state, "Target.detachedFromTarget",
        { sessionId: id, targetId: route.target.targetId }, route.parent);
    }
  }

  event(source, method, params = {}) {
    for (const state of this.sessions.values()) {
      if (!this.current(state)) continue;
      const parents = source.sessionId
        ? [...state.routes].filter(([, route]) => route.native?.tabId === source.tabId && route.native.sessionId === source.sessionId)
        : [...state.routes].filter(([, route]) => route.kind === "page" && route.native?.tabId === source.tabId && !route.native.sessionId);
      if (!source.sessionId && state.tabId === source.tabId) parents.push([undefined, { native: { tabId: source.tabId } }]);
      for (const [parent] of parents) {
        let forwarded = params;
        if (method === "Target.attachedToTarget") {
          if (state.routes.size >= MAX_TARGETS) { this.close(state.id, "attached_session_capacity").catch(() => {}); break; }
          const id = "mc-session-" + (++this.nextSession);
          const target = { ...params.targetInfo, browserContextId: DEFAULT_CONTEXT };
          state.routes.set(id, { kind: target.type, target, parent,
            native: { tabId: source.tabId, sessionId: params.sessionId } });
          forwarded = { ...params, sessionId: id, targetInfo: target };
        } else if (method === "Target.detachedFromTarget") {
          const child = [...state.routes].find(([, route]) => route.parent === parent && route.native?.tabId === source.tabId &&
            route.native.sessionId === params.sessionId);
          if (!child) continue;
          const forget = (id) => {
            for (const [childId, route] of [...state.routes]) if (route.parent === id) forget(childId);
            state.routes.delete(id);
          };
          forget(child[0]); forwarded = { ...params, sessionId: child[0], targetId: child[1].target.targetId };
        }
        this.emit(state, method, forwarded, parent);
        // Native child methods are addressed with the child native sessionId,
        // while wire frames retain this connection's facade session identity.
      }
    }
  }
}

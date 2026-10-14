#!/usr/bin/env node
// Experimental persistent JavaScript interface to the local Machine Control
// resident, served to an agent as a stdio MCP tool. It tests whether a
// Computer Use-style session (persistent handles, compact numbered trees,
// observation returned with each action, inline images) helps agents compared
// with one CLI process per call. It talks to the resident socket directly and
// skips claims and controller audit: use it only in a dedicated experiment VM.
import fs from "node:fs";
import net from "node:net";
import os from "node:os";
import path from "node:path";
import readline from "node:readline";
import vm from "node:vm";

const SOCKET = process.env.MACHINE_CONTROL_HOST_SOCKET ||
  path.join(os.homedir(), "Library/Application Support/MachineControl/control.sock");
const SETTLE_MS = 400;
const TREE_LIMIT = 12000;

function resident(request, timeoutMs = 120000) {
  return new Promise((resolve, reject) => {
    const client = net.createConnection(SOCKET);
    let data = "";
    const timer = setTimeout(() => { client.destroy(); reject(new Error("resident timed out")); }, timeoutMs);
    client.on("connect", () => client.end(JSON.stringify(request) + "\n"));
    client.on("data", (chunk) => { data += chunk; });
    client.on("error", (error) => { clearTimeout(timer); reject(error); });
    client.on("close", () => {
      clearTimeout(timer);
      try { resolve(JSON.parse(data.trim().split("\n")[0])); }
      catch { reject(new Error("unreadable resident reply")); }
    });
  });
}

class ControlError extends Error {}

async function call(request) {
  const reply = await resident(request);
  if (reply.accepted !== true) {
    throw new ControlError(`${request.operation} refused: ${reply.errorCode}${reply.message ? ` (${reply.message})` : ""}`);
  }
  return reply;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function line(element, number, base) {
  const role = String(element.role || "").replace(/^AX/, "").toLowerCase();
  const label = element.label ? ` "${element.label}"` : "";
  const value = element.value !== undefined && element.value !== null && element.value !== "" &&
    element.value !== element.label ? ` = ${JSON.stringify(String(element.value).slice(0, 80))}` : "";
  const flags = [element.enabled === false && "disabled", element.focused && "focused",
    element.identifier && `id:${element.identifier}`].filter(Boolean);
  const indent = "  ".repeat(Math.max(0, (element.depth || 0) - base));
  return `${indent}[${number}] ${role}${label}${value}${flags.length ? ` (${flags.join(", ")})` : ""}`;
}

class App {
  constructor(session, target, name) {
    this.session = session;
    this.target = target;
    this.name = name;
    this.refs = new Map();
    this.elements = new Map();
    this.generation = 0;
    this.previous = null;
  }

  // Compact accessibility tree with small numbers valid until the next read.
  async tree({ query, depth = 30, max = 400, full = false } = {}) {
    const request = { operation: "snapshot", target: this.target, projection: full ? "full" : "compact",
      maxDepth: depth, maxElements: max };
    if (query) request.query = query;
    const reply = await call(request);
    let elements = reply.data.elements || [];
    if (!query) {
      // Menus dominate whole-app trees; keep one menubar line and use find().
      const kept = [];
      let skipBelow = null;
      for (const element of elements) {
        if (skipBelow !== null && (element.depth || 0) > skipBelow) continue;
        skipBelow = element.role === "AXMenuBar" ? (element.depth || 0) : null;
        kept.push(element.role === "AXMenuBar" ? { ...element, label: "menu bar (search with find)" } : element);
      }
      elements = kept;
    }
    this.generation += 1;
    this.refs = new Map();
    this.elements = new Map();
    const base = Math.min(...elements.map((e) => e.depth || 0));
    const lines = elements.map((element, index) => {
      this.refs.set(index + 1, element.reference);
      this.elements.set(index + 1, element);
      return line(element, index + 1, base);
    });
    const body = lines.join("\n");
    const unnumbered = body.replace(/\[\d+\] /g, "");
    if (!query && this.previous === unnumbered) {
      return `No change in ${this.name}. Numbers are refreshed; use them.`;
    }
    if (!query) this.previous = unnumbered;
    const header = `${this.name}${query ? ` matching "${query}"` : ""}: ${elements.length} elements`;
    return body.length > TREE_LIMIT ?
      `${header} (truncated; use find)\n${body.slice(0, TREE_LIMIT)}` : `${header}\n${body}`;
  }

  find(text) { return this.tree({ query: text }); }

  reference(number) {
    const reference = this.refs.get(number);
    if (!reference) throw new ControlError(`[${number}] is not in the latest tree of ${this.name}; read it again`);
    return reference;
  }

  async act(description, request, observe) {
    const reply = await call(request);
    this.session.emit(`${description}: delivery ${reply.delivery}, effect ${reply.effect}`);
    if (observe === false) return reply;
    await sleep(SETTLE_MS);
    this.session.emit(await this.tree());
    return reply;
  }

  describe(number) {
    const element = this.elements.get(number);
    return element ? `[${number}] ${String(element.role).replace(/^AX/, "").toLowerCase()} "${element.label || element.value || ""}"` : `[${number}]`;
  }

  press(number, { observe } = {}) {
    return this.act(`pressed ${this.describe(number)}`,
      { operation: "action", reference: this.reference(number), action: "press" }, observe);
  }
  setValue(number, text, { observe } = {}) {
    return this.act(`set ${this.describe(number)}`,
      { operation: "action", reference: this.reference(number), action: "set_value", text }, observe);
  }
  focus(number, { observe } = {}) {
    return this.act(`focused ${this.describe(number)}`,
      { operation: "action", reference: this.reference(number), action: "focus" }, observe);
  }
  key(chord, { observe } = {}) {
    return this.act(`key ${chord}`, { operation: "input.key", key: chord.replaceAll("+", "-"), target: this.target }, observe);
  }
  type(text, { observe } = {}) {
    return this.act(`typed ${text.length} characters`, { operation: "input.text", text, target: this.target }, observe);
  }
  click(x, y, { observe } = {}) {
    return this.act(`clicked ${x},${y}`, { operation: "input.click", x, y, target: this.target }, observe);
  }
  // Choose a location in this app's open native Open or Save panel.
  async choose(location, { confirm = true, observe } = {}) {
    const reply = await this.act(`chose ${location}`,
      { operation: "dialog.choose", target: this.target, path: location, confirm }, observe);
    const dialog = reply.data?.dialog || {};
    if (dialog.followUp?.length) this.session.emit(`Follow-up prompt left open: ${dialog.followUp.join(" ")}`);
    return reply;
  }
  async screenshot() {
    const reply = await call({ operation: "capture", scope: "window", target: this.target });
    const file = reply.data?.artifactPath;
    if (!file) throw new ControlError("capture returned no artifact");
    this.session.image(fs.readFileSync(file).toString("base64"));
    fs.rmSync(file, { force: true });
    return `screenshot of ${this.name} attached`;
  }
}

class Session {
  constructor() { this.output = []; this.images = []; }
  emit(text) { this.output.push(String(text)); }
  image(data) { this.images.push(data); }

  api() {
    const session = this;
    return {
      async apps() {
        const reply = await call({ operation: "applications" });
        return (reply.data.applications || []).map((a) => `${a.name} (${a.bundleId || a.processId})`).join("\n");
      },
      async app(query, { observe = true } = {}) {
        const reply = await call({ operation: "applications" });
        const wanted = String(query).toLowerCase();
        const match = (reply.data.applications || []).find((a) =>
          [a.name, a.bundleId].some((v) => v && v.toLowerCase() === wanted)) ||
          (reply.data.applications || []).find((a) => [a.name, a.bundleId].some((v) => v && v.toLowerCase().includes(wanted)));
        if (!match) throw new ControlError(`${query} is not running; use mc.launch`);
        const app = new App(session, match.bundleId || String(match.processId), match.name || query);
        if (observe) session.emit(await app.tree());
        return app;
      },
      async launch(bundleId) {
        await call({ operation: "application.launch", applicationId: bundleId });
        await sleep(1500);
        return this.app(bundleId);
      },
    };
  }
}

const HELP = `Persistent JavaScript with top-level await and an \`mc\` object for this Mac.
Assign handles without let/const so they persist between calls: app = await mc.app("TextEdit").
mc.apps(), mc.app(nameOrBundleId), mc.launch(bundleId)
app.tree({query}), app.find(text), app.press(n), app.setValue(n, text), app.focus(n),
app.key("cmd+s"), app.type(text), app.click(x, y), app.choose("/absolute/path"), app.screenshot()
Actions return delivery/effect and the refreshed tree automatically; numbers are valid only for the latest tree.
For native Open/Save panels use app.choose(path). Return or console.log values to see them.`;

let session = new Session();
let context = vm.createContext({ mc: session.api(), console: { log: (...a) => session.emit(a.join(" ")) },
  setTimeout, sleep });

async function evaluate(code) {
  session.output = [];
  session.images = [];
  let isError = false;
  try {
    const value = await vm.runInContext(`(async () => {\n${code}\n})()`, context, { timeout: 30000 });
    if (value !== undefined) session.emit(typeof value === "string" ? value : JSON.stringify(value, null, 1));
  } catch (error) {
    isError = true;
    session.emit(`${error instanceof ControlError ? "" : `${error.name}: `}${error.message}`);
  }
  const content = [{ type: "text", text: session.output.join("\n") || "(no output)" }];
  for (const data of session.images) content.push({ type: "image", data, mimeType: "image/png" });
  return { content, isError };
}

const TOOLS = [
  { name: "mc", description: HELP,
    inputSchema: { type: "object", properties: { code: { type: "string" } }, required: ["code"] } },
  { name: "mc_reset", description: "Discard all persistent JavaScript state.",
    inputSchema: { type: "object", properties: {} } },
];

const reply = (id, result) => process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n");
// Requests run strictly in order: one persistent context, one resident caller.
let queue = Promise.resolve();
readline.createInterface({ input: process.stdin }).on("line", (text) => {
  queue = queue.then(() => handle(text)).catch(() => {});
});

async function handle(text) {
  let message;
  try { message = JSON.parse(text); } catch { return; }
  const { id, method, params } = message;
  if (method === "initialize") {
    reply(id, { protocolVersion: params?.protocolVersion || "2025-06-18", capabilities: { tools: {} },
      serverInfo: { name: "mc-repl", version: "0.1.0" }, instructions: HELP });
  } else if (method === "tools/list") {
    reply(id, { tools: TOOLS });
  } else if (method === "tools/call") {
    if (params?.name === "mc_reset") {
      session = new Session();
      context = vm.createContext({ mc: session.api(), console: { log: (...a) => session.emit(a.join(" ")) }, setTimeout, sleep });
      reply(id, { content: [{ type: "text", text: "reset" }] });
    } else {
      reply(id, await evaluate(String(params?.arguments?.code || "")));
    }
  } else if (method === "ping") {
    reply(id, {});
  } else if (id !== undefined) {
    process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, error: { code: -32601, message: "Method not found" } }) + "\n");
  }
}

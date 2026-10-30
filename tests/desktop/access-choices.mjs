// Run after `pnpm --dir desktop build`; MC_PLAYWRIGHT_MODULE can override the
// pinned desktop dev dependency. Uses bundled headless Chromium.
// Native arming is mocked: this checks form persistence, never OS permission.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, extname } from "node:path";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../desktop/package.json", import.meta.url));
const { chromium } = require(process.env.MC_PLAYWRIGHT_MODULE ?? "playwright");
const root = resolve(fileURLToPath(new URL("../../desktop/dist/", import.meta.url)));
const server = createServer(async (request, response) => {
  const path = resolve(root, "." + new URL(request.url, "http://localhost").pathname);
  if (path !== root && !path.startsWith(root + "/")) { response.writeHead(403).end(); return; }
  try {
    const extension = extname(path);
    response.setHeader("Content-Type", extension === ".js" ? "text/javascript" : extension === ".css" ? "text/css" : "text/html");
    response.end(await readFile(extension ? path : resolve(root, "index.html")));
  } catch { response.writeHead(404).end(); }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    window.armCalls = 0;
    const state = {
      platform: "macos", manualUntilStoppedSupported: true,
      accessChoices: { scopes: ["observe", "control", "browser", "devtools"], duration: 0 },
      deployment: { policy: { preset: "workstation", grantMode: "approval" }, grant: null, pendingRequest: null },
      permissions: { accessibility: true, screenRecording: true },
      browser: { connected: true }, activity: [], version: "fixture", socket: "fixture",
    };
    window.__TAURI_INTERNALS__ = {
      transformCallback: () => 1,
      unregisterCallback: () => {},
      invoke: async (command, args) => {
        if (command !== "operator_command") return 1;
        const request = args.command;
        if (request.method === "arm") {
          window.armCalls++;
          state.deployment.grant = { scopes: request.scopes, lifetime: request.lifetime,
            remainingSeconds: null, requester: "local operator", origin: "person", reason: "fixture" };
          state.accessChoices = { scopes: request.scopes, duration: request.duration };
        }
        if (request.method === "stop") state.deployment.grant = null;
        return { state: structuredClone(state) };
      },
    };
    window.menuArm = () => {
      state.accessChoices = { scopes: ["observe","control","browser","devtools"], duration: 14400 };
      state.deployment.grant = { scopes: state.accessChoices.scopes, lifetime: "timed", origin: "person",
        remainingSeconds: 14400, requester: "local operator", reason: "menu fixture" };
    };
  });
  let page = await context.newPage();
  const url = `http://127.0.0.1:${server.address().port}/`;
  const ready = async () => page.getByRole("button", { name: "Enable access", exact: true }).waitFor();
  const selected = async () => ({
    scopes: await page.getByRole("group", { name: "Access scopes" }).getByRole("checkbox").evaluateAll((rows) => rows.map((row) => row.checked)),
    duration: await page.getByRole("combobox", { name: "Access duration" }).inputValue(),
  });
  await page.goto(url); await ready();
  assert.deepEqual(await selected(), { scopes: [true, true, true, true], duration: "0" });
  await page.getByRole("checkbox", { name: "Browser scripts and DevTools", exact: true }).uncheck();
  await page.getByRole("combobox", { name: "Access duration" }).selectOption("300");
  await page.close(); page = await context.newPage();
  await page.goto(url); await ready();
  assert.deepEqual(await selected(), { scopes: [true, true, true, false], duration: "300" });
  assert.equal(await page.evaluate(() => window.armCalls), 0, "Remembering selections must not arm access");
  await page.getByRole("combobox", { name: "Access duration" }).selectOption("0");
  await page.getByRole("button", { name: "Enable access", exact: true }).click();
  await page.getByRole("button", { name: "Stop access", exact: true }).click();
  await ready(); await page.reload(); await ready();
  assert.deepEqual(await selected(), { scopes: [true, true, true, false], duration: "0" });
  assert.equal(await page.evaluate(() => window.armCalls), 0);
  // A stale/malformed WebView preference cannot create scopes or authority.
  await page.evaluate(() => localStorage.setItem("machine-control.access-choices.v1", '{"scopes":["system"],"duration":0}'));
  await page.reload(); await ready();
  assert.deepEqual(await selected(), { scopes: [true, true, true, true], duration: "0" });
  assert.equal(await page.evaluate(() => window.armCalls), 0);
  await page.evaluate(() => window.menuArm());
  await page.getByRole("button", { name: "Stop access", exact: true }).click();
  await ready(); await page.reload(); await ready();
  assert.deepEqual(await selected(), { scopes: [true,true,true,true], duration: "14400" });
  assert.equal(await page.evaluate(() => window.armCalls), 0);
  await context.close();
  console.log("PASS: saved scopes/duration, Settings recreation, reload, Stop, migration and no automatic arming");
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}

// Build the UI first. Uses the project's separately identified Chromium and a
// mocked native inlet; this tests presentation and commands, not OS authority.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, extname } from "node:path";
import { createRequire } from "node:module";
const require = createRequire(new URL("../../desktop/package.json", import.meta.url));
const { chromium } = require("playwright");
const root = fileURLToPath(new URL("../../desktop/dist/", import.meta.url));
const server = createServer(async (request, response) => {
  const path = resolve(root, "." + new URL(request.url, "http://localhost").pathname);
  if (!path.startsWith(resolve(root) + "/") && path !== resolve(root)) { response.writeHead(403).end(); return; }
  try {
    const extension = extname(path);
    response.setHeader("Content-Type", extension === ".js" ? "text/javascript" : extension === ".css" ? "text/css" : "text/html");
    response.end(await readFile(extension ? path : resolve(root, "index.html")));
  } catch { response.writeHead(404).end(); }
});
await new Promise(done => server.listen(0, "127.0.0.1", done));
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 900, height: 1100 } });
  await context.addInitScript(() => {
    window.commands = [];
    const surface = () => ({ mode: "off", expired: false, consentRemainingSeconds: null, profileIds: [], ready: true, pauses: [] });
    const policy = { schema: "machine-control-admission/v2", noticeSeconds: 10, globalPauses: [], surfaces: { desktop: surface(), browser: surface() } };
    const state = { platform: "windows", deployment: { policy: { preset: "workstation", grantMode: "surface_modes" }, grant: null, pendingRequest: null },
      accessPolicy: policy, admission: { active: 0, waiting: 0, requests: [] }, permissions: { accessibility: true, screenRecording: true },
      browser: { connected: true, profiles: [{ profileId: "fixture:work", name: "Work", enabled: true, connected: true },
        { profileId: "fixture:personal", name: "Personal", enabled: true, connected: true }] }, activity: [], version: "fixture", socket: "fixture" };
    window.fixtureState = state;
    window.__TAURI_INTERNALS__ = { transformCallback: () => 1, unregisterCallback: () => {}, invoke: async (command, args) => {
      if (command !== "operator_command") return 1;
      const request = args.command;
      if (request.method === "state" && window.busyStatePoll) { window.busyPolls = (window.busyPolls ?? 0) + 1; return { ok: true, busy: true }; }
      if (request.method === "state" && window.failedStatePoll) throw "Resident unavailable";
      if (request.method !== "state" && request.method !== "update_sync") window.commands.push(request);
      if (request.method === "surface.configure") Object.assign(policy.surfaces[request.surface], { mode: request.mode,
        profileIds: request.browserProfileIds, consentRemainingSeconds: request.lifetime === "timed" ? request.duration : null });
      if (request.method === "stop") for (const surface of Object.values(policy.surfaces)) surface.mode = "off";
      if (request.method === "pause_surface") policy.surfaces[request.surface].pauses = [{ reason: "manual", scope: request.surface, remainingSeconds: request.duration ?? null }, ...policy.globalPauses.map(pause => ({ ...pause, scope: "all" }))];
      if (request.method === "resume_surface") policy.surfaces[request.surface].pauses = policy.globalPauses.map(pause => ({ ...pause, scope: "all" }));
      if (request.method === "pause") {
        policy.globalPauses = [{ reason: "manual", remainingSeconds: request.duration ?? null }];
        for (const surface of Object.values(policy.surfaces)) surface.pauses = [...surface.pauses.filter(pause => pause.scope !== "all"), ...policy.globalPauses.map(pause => ({ ...pause, scope: "all" }))];
      }
      if (request.method === "resume") {
        policy.globalPauses = [];
        for (const surface of Object.values(policy.surfaces)) surface.pauses = surface.pauses.filter(pause => pause.scope !== "all");
      }
      if (request.method === "control_notice") policy.noticeSeconds = request.noticeSeconds;
      return { ok: true, state: structuredClone(state) };
    } };
  });
  const page = await context.newPage(), errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const url = `http://127.0.0.1:${server.address().port}/`;
  await page.goto(url);
  await page.getByRole("heading", { name: "Computer access" }).waitFor();
  assert.equal(await page.getByRole("checkbox", { name: /scripts|devtools/i }).count(), 0);
  assert.equal(await page.getByRole("combobox", { name: "Desktop access mode" }).inputValue(), "off");
  assert.equal((await page.evaluate(() => window.commands)).filter(command => command.method === "surface.configure").length, 0);
  const browserMode = page.getByRole("combobox", { name: "Browser access mode" });
  assert.equal(await browserMode.locator('option[value="automatic"]').evaluate(option => option.disabled), true);
  await page.getByRole("checkbox", { name: "Allow profile Work", exact: true }).check();
  await page.evaluate(() => { window.busyStatePoll = true; });
  await page.waitForFunction(() => window.busyPolls > 0);
  assert.equal(await page.getByRole("checkbox", { name: "Allow profile Work", exact: true }).isChecked(), true,
    "a busy metadata poll must preserve an unarmed profile edit");
  assert.equal((await page.evaluate(() => window.commands)).filter(command => command.method === "surface.configure").length, 0);
  await page.evaluate(() => { window.busyStatePoll = false; });
  await page.getByRole("combobox", { name: "Desktop access mode" }).selectOption("ask");
  await browserMode.selectOption("automatic");
  let commands = await page.evaluate(() => window.commands);
  assert.deepEqual(commands.filter(command => command.method === "surface.configure").map(command => [command.surface, command.mode, command.browserProfileIds]),
    [["desktop", "ask", []], ["browser", "automatic", ["fixture:work"]]]);
  await page.evaluate(() => { window.fixtureState.accessPolicy.humanInputReady = false; });
  await page.getByText(/Disruptive control waits for native input observation/).waitFor();
  await page.evaluate(() => { window.fixtureState.accessPolicy.humanInputReady = true; });
  await page.getByRole("button", { name: "Pause desktop 30s", exact: true }).click();
  assert.equal(await page.getByRole("combobox", { name: "Browser access mode" }).inputValue(), "automatic");
  await page.getByRole("button", { name: "Resume desktop", exact: true }).click();
  await page.getByRole("button", { name: "Pause desktop until Resume", exact: true }).click();
  await page.getByRole("button", { name: "Pause all 30s", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Resume browser", exact: true }).count(), 0,
    "A global pause exposes its global Resume instead of an ineffective surface Resume");
  await page.getByRole("button", { name: "Resume global pause", exact: true }).click();
  assert.deepEqual(await page.evaluate(() => Object.values(window.fixtureState.accessPolicy.surfaces).map(surface => surface.pauses.length)), [1, 0],
    "Global Resume preserves an independently paused Desktop");
  await page.getByRole("button", { name: "Resume desktop", exact: true }).click();
  await page.getByRole("button", { name: "Stop all access", exact: true }).click();
  await page.getByRole("button", { name: "Enable Ask first for desktop", exact: true }).waitFor();
  await page.reload();
  await page.getByRole("button", { name: "Enable Ask first for desktop", exact: true }).waitFor();
  assert.equal((await page.evaluate(() => window.commands)).filter(command => command.method === "surface.configure").length, 0, "Remembering Ask is not arming after restart");
  await page.getByRole("button", { name: "Enable Ask first for desktop", exact: true }).click();
  await page.getByRole("button", { name: "Enable Automatic for browser", exact: true }).click();
  await page.evaluate(() => { window.fixtureState.admission.requests = [{ intentId: "fixture-task", surfaces: ["browser"], profileIds: ["fixture:work", "fixture:personal"], state: "waiting_for_approval", reason: "Fixture task", noticeRemainingSeconds: null }]; });
  await page.getByText(/Browser profiles: Work .*Personal /).waitFor();
  await page.getByRole("button", { name: "Allow this task", exact: true }).click();
  await page.getByRole("button", { name: "Pause 30 seconds", exact: true }).click();
  await page.getByRole("button", { name: "Pause 1 minute", exact: true }).click();
  await page.getByRole("button", { name: "Pause until Resume", exact: true }).click();
  await page.getByRole("button", { name: "Deny task", exact: true }).click();
  commands = await page.evaluate(() => window.commands);
  assert.deepEqual(commands.filter(command => command.method === "pause_request").map(command => command.duration ?? null), [30, 60, null]);
  assert.ok(commands.some(command => command.method === "approve_control" && command.intentId === "fixture-task"));
  assert.ok(commands.some(command => command.method === "cancel_control" && command.intentId === "fixture-task"));
  await page.setViewportSize({ width: 580, height: 500 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth &&
    [...document.querySelectorAll(".group")].every(group => group.scrollWidth <= group.clientWidth)), true, "controls fit the minimum Settings width");
  await page.screenshot({ path: resolve(".artifacts/surface-access-ui.png"), fullPage: true });
  await page.evaluate(() => { window.fixtureState.accessPolicy.available = false; });
  await page.getByRole("alert").filter({ hasText: "control engine is unavailable" }).waitFor();
  assert.equal(await page.getByRole("combobox", { name: "Desktop access mode" }).isDisabled(), true);
  await page.evaluate(() => { window.failedStatePoll = true; });
  await page.getByText("Resident unavailable", { exact: true }).waitFor();
  assert.equal(await page.getByRole("combobox", { name: "Desktop access mode" }).count(), 0,
    "a terminal transport failure must remove control widgets");
  assert.deepEqual(errors, []);
  console.log("Surface settings modes, exact profiles, remembered choices, task controls and independent pauses passed");
} finally { await browser.close(); await new Promise(done => server.close(done)); }

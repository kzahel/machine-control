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
      presentation: { profile: "personal", setting: false, temporaryOverride: false, diagnostic: null }, browser: { connected: true, profiles: [{ profileId: "fixture:work", name: "Work", enabled: true, connected: true },
        { profileId: "fixture:personal", name: "Personal", enabled: true, connected: true }] }, activity: [], version: "fixture", socket: "fixture" };
    window.fixtureState = state;
    window.__TAURI_INTERNALS__ = { transformCallback: () => 1, unregisterCallback: () => {}, invoke: async (command, args) => {
      if (command !== "operator_command") return 1;
      const request = args.command;
      if (request.method === "state" && window.busyStatePoll) { window.busyPolls = (window.busyPolls ?? 0) + 1; return { ok: true, busy: true }; }
      if (request.method === "state" && window.failedStatePoll) throw "Resident unavailable";
      if (request.method !== "state" && request.method !== "update_sync") window.commands.push(request);
      if (request.method === "surface.configure" && window.failSurface === request.surface) throw "Fixture configuration refused";
      if (request.method === "surface.configure") Object.assign(policy.surfaces[request.surface], { mode: request.mode,
        expired: false, profileIds: request.browserProfileIds, consentRemainingSeconds: request.lifetime === "timed" ? request.duration : null });
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
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.getByRole("heading", { name: "Agent access", exact: true }).waitFor();
  const calls = () => page.evaluate(() => window.commands);
  const desktop = page.getByRole("switch", { name: "Desktop access", exact: true });
  const browserSwitch = page.getByRole("switch", { name: "Browser access", exact: true });
  const master = page.getByRole("switch", { name: "Agent access", exact: true });
  const desktopMode = page.getByRole("combobox", { name: "Desktop before starting" });
  assert.equal(await desktop.getAttribute("aria-checked"), "false");
  assert.equal(await browserSwitch.isDisabled(), true);
  await master.click();
  await page.getByText("Turn on Desktop or Browser below to choose access.").waitFor();
  assert.equal((await calls()).length, 0, "master On never guesses a surface");
  await desktopMode.selectOption("ask");
  assert.equal((await calls()).length, 0, "editing a mode never grants access");
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  assert.equal((await calls()).length, 0, "Discard is local");
  await desktopMode.selectOption("ask");
  await desktop.click();
  assert.equal(await desktop.getAttribute("aria-checked"), "true");
  assert.equal(await page.getByRole("button", { name: "Apply changes" }).count(), 0, "On applies visible choices without leaving duplicate Apply");
  assert.equal((await calls()).at(-1).mode, "ask");
  await page.getByRole("checkbox", { name: "Allow profile Work", exact: true }).check();
  await browserSwitch.click();
  assert.equal(await browserSwitch.getAttribute("aria-checked"), "true");
  assert.deepEqual((await calls()).at(-1).browserProfileIds, ["fixture:work"]);
  await desktopMode.selectOption("automatic");
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await page.getByRole("button", { name: "Access", exact: true }).click();
  assert.equal(await desktopMode.inputValue(), "automatic", "draft survives navigation");
  await page.evaluate(() => { window.busyStatePoll = true; });
  await page.waitForFunction(() => window.busyPolls > 0);
  assert.equal(await desktopMode.inputValue(), "automatic");
  await page.evaluate(() => { window.busyStatePoll = false; });
  const before = (await calls()).length;
  await page.getByRole("button", { name: "Apply changes" }).click();
  await page.getByRole("button", { name: "Apply changes" }).waitFor({ state: "hidden" });
  assert.deepEqual((await calls()).slice(before).map(c => c.surface), ["desktop"], "Apply touches only the changed surface");
  await page.locator("summary").filter({ hasText: "More options" }).click();
  await page.getByRole("combobox", { name: "Access lifetime" }).selectOption("900");
  await page.getByRole("button", { name: "Apply changes" }).click();
  await page.getByRole("button", { name: "Apply changes" }).waitFor({ state: "hidden" });
  await desktopMode.selectOption("ask");
  await page.getByText(/renews access for 15 minutes/).waitFor();
  await desktop.click();
  assert.equal((await calls()).at(-1).mode, "off", "Off is immediate even while dirty");
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  await desktop.click();
  await page.getByRole("combobox", { name: "Access lifetime" }).selectOption("3600");
  await page.evaluate(() => { window.failSurface = "browser"; });
  await page.getByRole("button", { name: "Apply changes" }).click();
  await page.getByText(/Some changes were applied/).waitFor();
  assert.equal(await page.getByRole("button", { name: "Apply changes" }).isDisabled(), true, "partial apply requires explicit reconciliation");
  await page.evaluate(() => { window.failSurface = null; });
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  await desktopMode.selectOption("ask");
  await page.evaluate(() => { window.fixtureState.accessPolicy.surfaces.desktop.mode = "off"; });
  await page.getByText(/Access changed elsewhere/).waitFor();
  assert.equal(await page.getByRole("button", { name: "Apply changes" }).isDisabled(), true);
  await page.getByRole("button", { name: "Discard", exact: true }).click();
  await master.click();
  assert.equal((await calls()).at(-1).method, "stop");
  assert.equal(await master.getAttribute("aria-checked"), "false");
  await master.click();
  assert.equal((await calls()).at(-1).surface, "browser", "master restores the previous surface instead of guessing Desktop");
  await master.click();
  await page.reload();
  await master.waitFor();
  assert.equal((await calls()).filter(c => c.method === "surface.configure").length, 0, "saved preferences never arm access on reload");
  await page.evaluate(() => {
    window.fixtureState.accessPolicy.globalPauses = [{ reason: "manual", remainingSeconds: null }];
    window.fixtureState.admission.requests = [{ intentId: "fixture-task", surfaces: ["browser"], profileIds: ["fixture:work"], state: "waiting_for_approval", reason: "Edit a note in TextEdit", noticeRemainingSeconds: null }];
  });
  assert.equal(await page.getByText("Edit a note in TextEdit", { exact: true }).isVisible().catch(() => false), false);
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await page.getByText("Edit a note in TextEdit", { exact: true }).waitFor();
  await page.getByText("Work · …ure:work", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Allow task", exact: true }).click();
  assert.equal((await calls()).at(-1).method, "approve_control");
  await page.getByRole("button", { name: "Resume access", exact: true }).click();
  assert.equal((await calls()).at(-1).method, "resume");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const startup = page.getByRole("combobox", { name: "Startup behavior" });
  await startup.selectOption("minimal");
  assert.equal((await calls()).at(-1).method, "presentation");
  await page.getByRole("button", { name: "Access", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: /Pause|Resume/ }).count(), 0);
  await page.setViewportSize({ width: 580, height: 650 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && [...document.querySelectorAll(".group")].filter(g => g.offsetParent).every(g => g.scrollWidth <= g.clientWidth)), true);
  if (process.env.MC_SCREENSHOT_DIR) {
    const { mkdir } = await import("node:fs/promises"); await mkdir(process.env.MC_SCREENSHOT_DIR, { recursive: true });
    await page.screenshot({ path: resolve(process.env.MC_SCREENSHOT_DIR, "access.png"), fullPage: true });
    await desktopMode.selectOption("ask");
    await page.screenshot({ path: resolve(process.env.MC_SCREENSHOT_DIR, "access-unsaved.png"), fullPage: true });
    await page.getByRole("button", { name: "Activity", exact: true }).click();
    await page.screenshot({ path: resolve(process.env.MC_SCREENSHOT_DIR, "activity.png"), fullPage: true });
  }
  await page.evaluate(() => { window.failedStatePoll = true; });
  await page.getByText("Resident unavailable", { exact: true }).waitFor();
  assert.equal(await desktop.count(), 0, "transport failure removes authority controls");
  assert.deepEqual(errors, []);
  console.log("Access switches, dirty settings, partial failure, Activity, startup and minimum layout passed");
} finally { await browser.close(); await new Promise(done => server.close(done)); }

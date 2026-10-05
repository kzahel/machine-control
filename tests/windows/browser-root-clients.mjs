// Real clients against the target's owned extension bridge, never a browser
// remote-debugging port. Credentials/endpoint arrive only on standard input.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { resolve } from "node:path";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { endpoint, fixtureUrl } = JSON.parse(input);
const require = createRequire(resolve(process.argv[2], "package.json"));
const { chromium } = require("playwright-core");
const puppeteer = require("puppeteer-core");
const checks = [];
let playwright, browser;
try {
  playwright = await chromium.connectOverCDP(endpoint, { noDefaults: true, timeout: 20000 });
  const context = playwright.contexts()[0];
  const existing = context.pages().find((page) => page.url() === fixtureUrl);
  assert.ok(existing); assert.equal(await existing.title(), "Streaming CDP Fixture");
  checks.push("Playwright attaches existing default-profile page");
  const page = await context.newPage();
  await page.goto(fixtureUrl);
  await page.locator("#effect").evaluate((button) => { button.dataset.marker = "playwright"; });
  await page.locator("#effect").click();
  await page.waitForFunction(() => document.querySelector("#effect").dataset.done === "yes");
  checks.push("Playwright creates tab and clicks fixture button");
  assert.ok((await page.screenshot()).subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])));
  checks.push("Playwright captures real tab PNG");
  const popupEvent = page.waitForEvent("popup");
  await page.evaluate((url) => window.open(url, "_blank"), fixtureUrl + "?popup");
  const popup = await popupEvent;
  await popup.waitForLoadState(); assert.equal(await popup.title(), "Streaming CDP Fixture");
  checks.push("Playwright discovers and controls popup");
  await page.evaluate((url) => {
    const frame = document.createElement("iframe"); frame.src = url; document.body.append(frame);
  }, fixtureUrl.replace("127.0.0.1", "localhost") + "frame");
  await page.waitForFunction(() => document.querySelector("iframe")?.contentWindow !== null);
  const child = await new Promise((done, reject) => {
    const timer = setTimeout(() => reject(new Error("Child frame unavailable")), 15000);
    const poll = () => {
      const frame = page.frames().find((frame) => frame.url().endsWith("/frame"));
      if (frame) { clearTimeout(timer); done(frame); } else setTimeout(poll, 50);
    }; poll();
  });
  assert.equal(await child.locator("#frame").textContent(), "Cross-site child");
  checks.push("Playwright routes cross-site iframe commands");
  const workerEvent = page.waitForEvent("worker");
  await page.evaluate(() => {
    window.fixtureWorker = new Worker(URL.createObjectURL(new Blob(["self.fixtureValue = 42"], { type: "text/javascript" })));
  });
  const worker = await workerEvent;
  assert.equal(await worker.evaluate(() => self.fixtureValue), 42);
  checks.push("Playwright routes dedicated worker commands");
  await assert.rejects(playwright.newContext(), /Unsupported browser-level operation|Isolated/);
  checks.push("Playwright isolated context refuses explicitly");
  await page.evaluate(() => window.fixtureWorker.terminate());
  await popup.close(); await page.close();
  await playwright.close(); playwright = null; // CDP connection close leaves Chrome running.
  await new Promise((done) => setTimeout(done, 500));
  browser = await puppeteer.connect({ browserWSEndpoint: endpoint, defaultViewport: null, protocolTimeout: 20000 });
  assert.ok((await browser.pages()).some((page) => page.url() === fixtureUrl));
  checks.push("Puppeteer attaches through tab-wrapper and page sessions");
  const ppPage = await browser.newPage();
  await ppPage.goto(fixtureUrl);
  await ppPage.$eval("#effect", (button) => { button.dataset.marker = "puppeteer"; });
  await ppPage.click("#effect");
  await ppPage.waitForFunction(() => document.querySelector("#effect").dataset.done === "yes");
  checks.push("Puppeteer creates tab and clicks fixture button");
  assert.ok((await ppPage.screenshot()).length > 100);
  checks.push("Puppeteer captures real tab PNG");
  await assert.rejects(browser.createBrowserContext(), /Unsupported browser-level operation|Isolated/);
  checks.push("Puppeteer isolated context refuses explicitly");
  await ppPage.close(); await browser.disconnect(); browser = null;
  process.stdout.write(JSON.stringify({ passed: true, checks,
    versions: { playwright: require("playwright-core/package.json").version,
      puppeteer: require("puppeteer-core/package.json").version } }));
} catch (error) {
  process.stdout.write(JSON.stringify({ passed: false, checks,
    error: String(error.message).replace(/ws:\/\/\S+/g, "[endpoint]") }));
  process.exitCode = 1;
} finally {
  if (playwright) await playwright.close().catch(() => {});
  if (browser) await browser.disconnect().catch(() => {});
}
